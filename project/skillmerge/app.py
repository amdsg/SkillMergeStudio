from __future__ import annotations

import atexit
import os
import signal
import sys
import threading
import time
from dataclasses import dataclass
from typing import Any, Optional

from . import __version__
from .api import health as health_api
from .api import artifacts_api, export_api, github_api, jobs_api, ops_api, skills_api, tasks_api
from .config import paths
from .services.github import GithubClient
from .config.loader import load_config
from .http.router import Router
from .http.server import create_server
from .jobs.events import EventBroker
from .jobs.job_store import JobStore
from .jobs.queue import JobQueue
from .security import SessionToken
from .services.classifier.classifier_service import ClassifierService
from .services.history.rebuild import RebuildService
from .services.exporter.batch import ExportBatch
from .services.exporter.export_service import ExportOptions, ExportService
from .services.exporter.registry import PlatformRegistry
from .services.merger.merge_service import MergeOptions, MergeService
from .services.scanner.scanner_service import ScanOptions, ScannerService
from .storage.db import Database
from .storage.repos.artifacts_repo import ArtifactsRepo
from .storage.repos.jobs_repo import JobsRepo
from .storage.repos.scans_repo import ScansRepo
from .storage.repos.skills_repo import SkillsRepo
from .util.audit import write_audit
from .util.errors import DomainError
from .util.logging import get_logger


@dataclass
class AppContext:
    config: Any
    data_dir: str
    db: Database
    token: SessionToken
    router: Optional[Router]
    jobs: JobQueue
    job_store: JobStore
    events: EventBroker
    scanner: ScannerService
    merge_service: MergeService
    export_service: ExportService
    registry: PlatformRegistry
    skills_repo: SkillsRepo
    scans_repo: ScansRepo
    jobs_repo: JobsRepo
    artifacts_repo: ArtifactsRepo
    started_at: float
    port: int = 0
    server: Any = None
    web_dir: str = ""
    github_client: Any = None


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        try:
            import ctypes

            handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, int(pid))
            if handle:
                ctypes.windll.kernel32.CloseHandle(handle)
                return True
            return False
        except Exception:
            return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def existing_instance(data_dir: str) -> Optional[str]:
    pid_file = paths.pid_path(data_dir)
    if not os.path.isfile(pid_file):
        return None
    try:
        pid = int(open(pid_file, "r", encoding="utf-8").read().strip())
    except (OSError, ValueError):
        return None
    if not _pid_alive(pid):
        return None
    port_file = paths.port_path(data_dir)
    url = ""
    if os.path.isfile(port_file):
        for line in open(port_file, "r", encoding="utf-8"):
            if line.startswith("url="):
                url = line.split("=", 1)[1].strip()
    return url or f"pid={pid}"


def _write_runtime_files(data_dir: str, port: int) -> None:
    os.makedirs(data_dir, exist_ok=True)
    with open(paths.port_path(data_dir), "w", encoding="utf-8", newline="\n") as handle:
        handle.write(f"port={port}\nurl=http://127.0.0.1:{port}\n")
    with open(paths.pid_path(data_dir), "w", encoding="utf-8", newline="\n") as handle:
        handle.write(str(os.getpid()) + "\n")


def _cleanup(data_dir: str, server, jobs: JobQueue, db: Database) -> None:
    if getattr(server, "_sms_cleaned", False):
        return
    server._sms_cleaned = True
    try:
        jobs.shutdown()
    except Exception:
        pass
    try:
        server.server_close()
    except Exception:
        pass
    try:
        db.close_all()
    except Exception:
        pass
    pid_file = paths.pid_path(data_dir)
    try:
        if os.path.isfile(pid_file):
            content = open(pid_file, "r", encoding="utf-8").read().strip()
            if content == str(os.getpid()):
                os.remove(pid_file)
        port_file = paths.port_path(data_dir)
        if os.path.isfile(port_file):
            os.remove(port_file)
    except OSError:
        pass


def build_router(ctx: AppContext) -> Router:
    router = Router()
    router.add("GET", "/api/health", health_api.health)
    router.add("GET", "/api/config", ops_api.get_config)
    router.add("POST", "/api/config", ops_api.save_config)
    router.add("GET", "/api/audit", ops_api.list_audit)
    router.add("POST", "/api/ai/test", ops_api.ai_test)
    router.add("GET", "/api/jobs", jobs_api.list_jobs)
    router.add("GET", "/api/jobs/{id}", jobs_api.get_job)
    router.add("GET", "/api/jobs/{id}/events", jobs_api.sse_stub, sse=True)
    router.add("POST", "/api/jobs/{id}/cancel", jobs_api.cancel_job)
    router.add("POST", "/api/scan", tasks_api.post_scan)
    router.add("POST", "/api/scan_all", tasks_api.post_scan_all)
    router.add("POST", "/api/classify", tasks_api.post_classify)
    router.add("GET", "/api/platforms", ops_api.list_platforms)
    router.add("GET", "/api/platforms/{id}", ops_api.get_platform)
    router.add("POST", "/api/preview", tasks_api.post_preview)
    router.add("POST", "/api/merge", tasks_api.post_merge)
    router.add("POST", "/api/export", tasks_api.post_export)
    router.add("POST", "/api/export/preview", export_api.preview)
    router.add("GET", "/api/artifacts/{id}/download", tasks_api.download_artifact, file=True)
    router.add("GET", "/api/history", artifacts_api.history)
    router.add("GET", "/api/artifacts/{id}", artifacts_api.get_artifact)
    router.add("POST", "/api/artifacts/{id}/undo", artifacts_api.undo)
    router.add("POST", "/api/artifacts/{id}/rebuild", artifacts_api.rebuild)
    router.add("POST", "/api/artifacts/{id}/ai-apply", artifacts_api.ai_apply)
    router.add("GET", "/api/skills/{id}/artifacts", artifacts_api.skill_artifacts)
    router.add("GET", "/api/skills", skills_api.list_skills)
    router.add("GET", "/api/skills/{id}", skills_api.get_skill)
    router.add("GET", "/api/categories", skills_api.categories)
    router.add("GET", "/api/duplicates", skills_api.duplicates)
    router.add("GET", "/api/github/health", github_api.health)
    router.add("POST", "/api/github/search", github_api.search)
    router.add("POST", "/api/github/trending", github_api.trending)
    router.add("POST", "/api/github/download", github_api.download)
    return router


def _register_scan(ctx: AppContext) -> None:
    def run_scan(params, cancel, progress, job_id):
        options = ScanOptions(**params)
        return ctx.scanner.scan(job_id=job_id, options=options, cancel_token=cancel, progress=progress)

    ctx.jobs.register("scan", run_scan)
    ctx.jobs.register("full_scan", run_scan)


def _register_merge(ctx: AppContext) -> None:
    def run_merge(params, cancel, progress, job_id):
        action = "rebuild" if params.get("action") == "rebuild" else "merge"
        target = str(params.get("artifact_id") or ",".join(params.get("sources", [])))
        try:
            if params.get("action") == "rebuild":
                artifact = ctx.artifacts_repo.get(params.get("artifact_id", ""))
                if artifact is None:
                    raise DomainError("NOT_FOUND", "产物不存在", "刷新历史列表后重试", 404)
                service = RebuildService(ctx.merge_service, ctx.skills_repo, ctx.artifacts_repo, ctx.registry)
                result = service.rebuild(
                    artifact,
                    bool(params.get("drop_missing_sources")),
                    job_id=job_id,
                    cancel_token=cancel,
                    progress=progress,
                )
            else:
                skills = []
                for skill_id in params.get("sources", []):
                    skill = ctx.skills_repo.get(skill_id)
                    if skill is None:
                        raise DomainError("NOT_FOUND", f"技能不存在：{skill_id}", "重新扫描后刷新列表", 404)
                    skills.append(skill)
                values = dict(params)
                values.pop("sources", None)
                options = MergeOptions(**values)
                result = ctx.merge_service.merge(
                    skills, options, job_id=job_id, cancel_token=cancel, progress=progress
                )
        except Exception as exc:
            write_audit(ctx.data_dir, action, target, f"failed:{type(exc).__name__}")
            raise
        final = str(result.get("dir_path") or (result.get("artifact") or {}).get("dir_path") or target)
        write_audit(ctx.data_dir, action, final, "ok")
        return result

    ctx.jobs.register("merge", run_merge)


def _register_export(ctx: AppContext) -> None:
    def run_export(params, cancel, progress, job_id):
        action = "install" if params.get("mode") == "install" else "export"
        target = str(params.get("artifact_id", ""))
        try:
            artifact = ctx.artifacts_repo.get(params.get("artifact_id", ""))
            if artifact is None:
                raise DomainError("NOT_FOUND", "产物不存在", "刷新历史列表后重试", 404)
            values = dict(params)
            values.pop("artifact_id", None)
            values.pop("platforms", None)
            if params.get("platforms"):
                options = ExportOptions(**values)
                batch = ExportBatch(ctx.export_service, ctx.registry)
                result = batch.run(
                    artifact,
                    params["platforms"],
                    options,
                    job_id=job_id,
                    cancel_token=cancel,
                    progress=progress,
                )
            else:
                options = ExportOptions(**values)
                result = ctx.export_service.export(
                    artifact, options, job_id=job_id, cancel_token=cancel, progress=progress
                )
        except Exception as exc:
            write_audit(ctx.data_dir, action, target, f"failed:{type(exc).__name__}")
            raise
        write_audit(ctx.data_dir, action, str(result.get("dir_path") or target), "ok")
        return result

    ctx.jobs.register("export", run_export)


def _register_classify(ctx: AppContext) -> None:
    def run_classify(params, cancel, progress, job_id):
        service = ClassifierService(ctx.db, ctx.config)
        return service.classify(
            params.get("skill_ids"),
            use_ai=bool(params.get("use_ai")),
            confirm_ai=bool(params.get("confirm_ai")),
            cancel_token=cancel,
            progress=progress,
        )

    ctx.jobs.register("classify", run_classify)


def _make_context(directory: str, config, db: Database) -> AppContext:
    skills_repo = SkillsRepo(db)
    scans_repo = ScansRepo(db)
    jobs_repo = JobsRepo(db)
    artifacts_repo = ArtifactsRepo(db)
    scanner = ScannerService(db, config)
    registry = PlatformRegistry(paths.platforms_dir())
    merge_service = MergeService(db, config, registry)
    export_service = ExportService(db, config, registry)
    events = EventBroker(jobs_repo)
    job_store = JobStore(jobs_repo)
    jobs = JobQueue(jobs_repo, job_store, events)
    job_store.recover_startup()
    github_token = os.environ.get("SKILLMERGE_GITHUB_TOKEN", "") or os.environ.get("GITHUB_TOKEN", "")
    github_client = GithubClient(token=github_token)
    ctx = AppContext(
        config=config,
        data_dir=directory,
        db=db,
        token=SessionToken(),
        router=None,
        jobs=jobs,
        job_store=job_store,
        events=events,
        scanner=scanner,
        merge_service=merge_service,
        export_service=export_service,
        registry=registry,
        skills_repo=skills_repo,
        scans_repo=scans_repo,
        jobs_repo=jobs_repo,
        artifacts_repo=artifacts_repo,
        started_at=time.monotonic(),
        web_dir=paths.web_dir(),
        github_client=github_client,
    )
    ctx.router = build_router(ctx)
    _register_scan(ctx)
    _register_merge(ctx)
    _register_export(ctx)
    _register_classify(ctx)
    return ctx


def make_context(directory: str, config, db: Database) -> AppContext:
    return _make_context(directory, config, db)


def build_app(
    host: str = "127.0.0.1",
    preferred_port: int = 8765,
    data_dir: Optional[str] = None,
    check_pid: bool = True,
) -> Optional[Any]:
    directory = data_dir or paths.data_dir()
    if check_pid:
        running = existing_instance(directory)
        if running:
            print(f"Skill Merge Studio 已在运行：{running}", file=sys.stderr)
            return None
    config, warnings = load_config(directory)
    for warning in warnings:
        get_logger().warning("%s: %s", warning.get("code"), warning.get("message"))
    os.makedirs(directory, exist_ok=True)
    os.makedirs(config.save_dir, exist_ok=True)
    db = Database(paths.db_path(directory))
    db.initialize()
    ctx = _make_context(directory, config, db)
    server, port = create_server(
        host, ctx.router, ctx.token, ctx.web_dir, ctx.events, ctx.job_store, ctx,
        preferred_port=preferred_port,
    )
    ctx.port = port
    ctx.server = server
    server.port = port
    _write_runtime_files(directory, port)
    ctx.jobs.start()
    atexit.register(_cleanup, directory, server, ctx.jobs, db)
    return server


def run_server(server, host: str = "127.0.0.1") -> int:
    ctx = server.ctx
    stop = threading.Event()

    def _handle(signum, frame):
        stop.set()

    for name in ("SIGINT", "SIGTERM"):
        sig = getattr(signal, name, None)
        if sig is not None:
            try:
                signal.signal(sig, _handle)
            except (OSError, ValueError):
                pass
    thread = threading.Thread(target=server.serve_forever, name="http-server", daemon=True)
    thread.start()
    print(f"Skill Merge Studio {__version__} 已启动 → http://{host}:{ctx.port}", file=sys.stderr)
    try:
        while not stop.wait(0.5):
            pass
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()
        thread.join(timeout=3.0)
        _cleanup(ctx.data_dir, server, ctx.jobs, ctx.db)
    return 0