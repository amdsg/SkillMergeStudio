export function createJobStream({ getJob }) {
  let source = null;
  let timer = 0;
  let jobId = "";
  let state = "idle";
  let failures = 0;
  let handlers = {};

  function close() {
    if (source) {
      source.close();
      source = null;
    }
    if (timer) {
      clearTimeout(timer);
      timer = 0;
    }
    jobId = "";
    state = "closed";
  }

  async function poll() {
    if (!jobId) return;
    const current = jobId;
    try {
      const job = await getJob(current);
      if (current !== jobId) return;
      failures = 0;
      if (job.status === "succeeded") {
        const result = job.result;
        close();
        if (handlers.onDone) handlers.onDone(result, job);
        return;
      }
      if (job.status === "failed" || job.status === "cancelled") {
        close();
        if (handlers.onError) handlers.onError(job);
        return;
      }
    } catch (error) {
      failures += 1;
      if (failures > 30) {
        close();
        if (handlers.onError) handlers.onError({ status: "failed", error: { message: error.message } });
        return;
      }
    }
    timer = setTimeout(poll, 900);
  }

  function open(id, next = {}) {
    close();
    handlers = next;
    jobId = id;
    state = "open";
    failures = 0;
    try {
      source = new EventSource(`/api/jobs/${encodeURIComponent(id)}/events`);
      source.onopen = () => {
        state = "open";
      };
      source.onerror = () => {
        state = "reconnect";
      };
      source.onmessage = (event) => {
        let payload = null;
        try {
          payload = JSON.parse(event.data);
        } catch (error) {
          return;
        }
        if (payload && handlers.onProgress) handlers.onProgress(payload);
      };
      source.addEventListener("done", () => {
        poll();
      });
    } catch (error) {
      state = "closed";
    }
    poll();
  }

  return {
    open,
    close,
    get state() {
      return state;
    },
    get jobId() {
      return jobId;
    }
  };
}