from __future__ import annotations

import queue
import threading
from typing import Any, Callable, Dict, Optional, Tuple

from ..util.errors import CancelledError, DomainError
from ..util.logging import get_logger, redact
from ..storage.repos.jobs_repo import JobsRepo
from .cancel import CancelToken
from .events import EventBroker
from .job_store import JobStore

MAX_WORKERS = 2
QUEUE_CAPACITY = 64
FORCE_CANCEL_SECONDS = 4.2

Handler = Callable[[Dict[str, Any], CancelToken, Callable[[str, int, int, str], None], str], Any]


class JobQueue:
    def __init__(self, repo: JobsRepo, store: JobStore, events: EventBroker) -> None:
        self.repo = repo
        self.store = store
        self.events = events
        self._handlers: Dict[str, Handler] = {}
        self._queue: "queue.Queue[str]" = queue.Queue(maxsize=QUEUE_CAPACITY)
        self._tokens: Dict[str, CancelToken] = {}
        self._lock = threading.Lock()
        self._workers = []
        self._shutdown = threading.Event()
        self._logger = get_logger()
        self._started = False

    def register(self, job_type: str, handler: Handler) -> None:
        self._handlers[job_type] = handler

    def start(self) -> None:
        if self._started:
            return
        self._started = True
        for index in range(MAX_WORKERS):
            worker = threading.Thread(target=self._loop, name=f"job-worker-{index}", daemon=True)
            worker.start()
            self._workers.append(worker)

    def submit(self, job_type: str, params: Dict[str, Any]) -> str:
        if job_type not in self._handlers:
            raise DomainError("INVALID_ARGUMENT", f"任务类型未注册：{job_type}", "确认服务已启动对应模块")
        if self._queue.qsize() >= QUEUE_CAPACITY:
            raise DomainError("QUEUE_FULL", "任务队列已满", "等待当前任务完成或取消排队任务", 429)
        job = self.store.create(job_type, params)
        with self._lock:
            self._tokens[job.id] = CancelToken()
        try:
            self._queue.put_nowait(job.id)
        except queue.Full:
            self.repo.update_status(job.id, "cancelled", finished_at=None)
            raise DomainError("QUEUE_FULL", "任务队列已满", "等待当前任务完成或取消排队任务", 429)
        self.events.publish(job.id, "queued", 0, None, "任务已排队", force=True)
        return job.id

    def cancel(self, job_id: str) -> Dict[str, Any]:
        job = self.store.request_cancel(job_id)
        with self._lock:
            token = self._tokens.get(job_id)
        if token is not None:
            token.set()
        if job.status == "running":
            timer = threading.Timer(FORCE_CANCEL_SECONDS, self._force_cancel, args=(job_id,))
            timer.daemon = True
            timer.start()
        self.events.publish(job_id, "cancel", 0, None, "已请求取消", force=True)
        return self.store.as_dict(self.store.require(job_id))

    def _force_cancel(self, job_id: str) -> None:
        job = self.repo.get(job_id)
        if job is not None and job.status == "running":
            try:
                self.repo.update_status(job_id, "cancelled", finished_at=None)
                self.store.repo.finish(job_id, "cancelled", None, None)
            except Exception:
                pass
            self.events.publish(job_id, "cancelled", 0, None, "任务已取消", force=True)

    def _emit(self, job_id: str):
        def emit(phase: str, current: int, total: int, message: str) -> None:
            self.events.publish(job_id, phase, current, total, message)
            self.store.update_progress(
                job_id, {"phase": phase, "current": current, "total": total, "message": message}
            )
        return emit

    def _loop(self) -> None:
        while not self._shutdown.is_set():
            try:
                job_id = self._queue.get(timeout=0.5)
            except queue.Empty:
                continue
            try:
                self._run_job(job_id)
            except Exception as exc:  # noqa: BLE001
                self._logger.error("任务执行异常：%s", redact(str(exc)))
            finally:
                self._queue.task_done()

    def _run_job(self, job_id: str) -> None:
        job = self.repo.get(job_id)
        if job is None or job.status == "cancelled":
            return
        with self._lock:
            token = self._tokens.get(job_id) or CancelToken()
            self._tokens[job_id] = token
        if token.is_set():
            self.store.finish(job_id, "cancelled", None, None)
            return
        try:
            self.store.mark_running(job_id)
            self.events.publish(job_id, "start", 0, None, "任务开始", force=True)
            handler = self._handlers[job.type]
            params = job.params()
            result = handler(params, token, self._emit(job_id), job_id)
            if token.is_set() or (isinstance(result, dict) and result.get("cancelled")):
                self.store.finish(job_id, "cancelled", result, None)
                self.events.publish(job_id, "cancelled", 0, None, "任务已取消", force=True)
            else:
                self.store.finish(job_id, "succeeded", result, None)
                self.events.publish(job_id, "succeeded", 1, 1, "任务完成", force=True)
        except CancelledError:
            self.store.finish(job_id, "cancelled", None, None)
            self.events.publish(job_id, "cancelled", 0, None, "任务已取消", force=True)
        except DomainError as exc:
            self.store.finish(job_id, "failed", None, exc.to_dict())
            self.events.publish(job_id, "failed", 0, None, exc.message, force=True)
        except Exception as exc:  # noqa: BLE001
            error = {"code": "INTERNAL_ERROR", "message": "任务执行失败", "fix": "查看 stderr 日志后重试"}
            self.store.finish(job_id, "failed", None, error)
            self.events.publish(job_id, "failed", 0, None, str(exc), force=True)
            self._logger.error("任务 %s 失败：%s", job_id, redact(str(exc)))
        finally:
            with self._lock:
                self._tokens.pop(job_id, None)

    def stats(self) -> Dict[str, int]:
        queued = self._queue.qsize()
        running = sum(1 for job in self.repo.active() if job.status == "running")
        return {"queued": queued, "running": running}

    def get_token(self, job_id: str) -> Optional[CancelToken]:
        with self._lock:
            return self._tokens.get(job_id)

    def shutdown(self) -> None:
        self._shutdown.set()
        with self._lock:
            tokens = list(self._tokens.values())
        for token in tokens:
            token.set()
        for worker in self._workers:
            worker.join(timeout=2.0)