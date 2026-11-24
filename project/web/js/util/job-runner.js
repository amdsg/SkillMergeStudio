import { t } from "/js/i18n/index.js";
import { phaseLabel } from "/js/util/phases.js";

export function createJobRunner({ stream, progressBar, el, state, api, setStatus }) {
  function followJob(jobId, onDone, jobType = "") {
    state.currentJob = jobId;
    el.cancelButton.disabled = false;
    el.cancelButton.classList.remove("hidden");
    progressBar.begin();
    stream.open(jobId, {
      onProgress: (payload) => {
        setStatus(
          t("status.job", {
            status: t("common.running"),
            phase: payload.phase ? phaseLabel(payload.phase) : "",
            message: payload.message || ""
          })
        );
        try {
          progressBar.update(payload);
        } catch (error) {
          console.warn("progress update failed", error);
        }
      },
      onDone: async (result) => {
        el.cancelButton.classList.add("hidden");
        progressBar.finish("succeeded");
        if (jobType === "scan") progressBar.showSummary(result);
        setStatus(t("status.done"), "ok");
        if (onDone) await onDone(result);
      },
      onError: (job) => {
        el.cancelButton.classList.add("hidden");
        const cancelled = job && job.status === "cancelled";
        progressBar.finish(cancelled ? "cancelled" : "failed");
        const message = job && job.error && job.error.message ? job.error.message : t("status.failed");
        setStatus(cancelled ? t("status.cancelled") : message, "error");
      }
    });
  }

  async function cancelCurrent() {
    if (!state.currentJob) return;
    el.cancelButton.disabled = true;
    progressBar.cancelRequested();
    setStatus(t("progress.cancelling"));
    try {
      await api(`/api/jobs/${encodeURIComponent(state.currentJob)}/cancel`, { method: "POST", body: "{}" });
    } catch (error) {
      el.cancelButton.disabled = false;
      setStatus(error.message, "error");
    }
  }

  async function restoreRunningJob(onRestored) {
    try {
      const data = await api("/api/jobs");
      const job = (data.items || []).find(
        (item) => ["scan", "full_scan"].includes(item.type) && ["queued", "running"].includes(item.status)
      );
      if (!job) return;
      followJob(job.id, onRestored, "scan");
      if (job.progress) progressBar.update({ ...job.progress, seq: 0 });
    } catch (error) {
      /* restore is best effort */
    }
  }

  return { followJob, cancelCurrent, restoreRunningJob };
}