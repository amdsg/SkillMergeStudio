const PHASE_ORDER = { walk: 0, parse: 1, classify: 2, ai: 2, write: 2, build: 3, export: 3 };
const PHASE_WEIGHT = { walk: 15, parse: 55, write: 30 };

export class ProgressModel {
  constructor() {
    this.reset();
  }

  reset() {
    this.lastSeq = -1;
    this.phaseIndex = -1;
    this.phase = "";
    this.current = 0;
    this.total = null;
    this.percent = null;
    this.maxPercent = 0;
    this.overallPercent = null;
    this.maxOverall = 0;
    this.mode = "indeterminate";
    this.status = "running";
    this.cancelled = false;
  }

  update(payload = {}) {
    if (!payload || this.status !== "running") return this.snapshot();
    const rawSeq = Number(payload.seq);
    const hasSeq = Number.isFinite(rawSeq);
    if (hasSeq && rawSeq <= this.lastSeq) return this.snapshot();
    if (hasSeq) this.lastSeq = rawSeq;

    const phase = String(payload.phase || "");
    if (phase === "succeeded") return this.finish("succeeded");
    if (phase === "failed") return this.finish("failed");
    if (phase === "cancelled") return this.finish("cancelled");

    const known = Object.prototype.hasOwnProperty.call(PHASE_ORDER, phase);
    const nextIndex = known ? PHASE_ORDER[phase] : -1;
    if (known && this.phaseIndex >= 0 && nextIndex < this.phaseIndex) return this.snapshot();
    if (known) this.phaseIndex = nextIndex;
    if (phase) this.phase = phase;

    this.current = Math.max(0, Number(payload.current) || 0);
    const rawTotal = payload.total;
    this.total = rawTotal === null || rawTotal === undefined ? null : Number(rawTotal);

    const determinate =
      known && Number.isFinite(this.total) && this.total > 0 && this.current >= 0 && this.current <= this.total;

    if (!determinate) {
      this.percent = null;
      this.mode = "indeterminate";
      this.overallPercent = null;
      return this.snapshot();
    }

    const percent = Math.round((this.current / this.total) * 100);
    this.maxPercent = Math.max(this.maxPercent, percent);
    this.percent = this.maxPercent;
    this.mode = "determinate";
    this.overallPercent = this.overallFor(percent);
    if (this.overallPercent !== null) {
      this.maxOverall = Math.max(this.maxOverall, this.overallPercent);
      this.overallPercent = this.maxOverall;
    }
    return this.snapshot();
  }

  overallFor(percent) {
    if (this.phase === "parse") return 15 + Math.round(percent * 0.55);
    if (this.phase === "write") return 70 + Math.round(percent * 0.3);
    return null;
  }

  finish(status) {
    this.status = status;
    this.mode = "terminal";
    if (status === "succeeded") {
      this.percent = 100;
      this.maxPercent = 100;
      this.overallPercent = 100;
      this.maxOverall = 100;
      this.cancelled = false;
    } else {
      this.percent = this.maxPercent > 0 ? Math.min(this.maxPercent, 99) : null;
      this.overallPercent = this.maxOverall > 0 ? Math.min(this.maxOverall, 99) : null;
      this.cancelled = status === "cancelled";
    }
    return this.snapshot();
  }

  cancelRequested() {
    if (this.status === "running") this.status = "cancelling";
    return this.snapshot();
  }

  snapshot() {
    return {
      mode: this.mode,
      percent: this.percent,
      maxPercent: this.maxPercent,
      overallPercent: this.overallPercent,
      phase: this.phase,
      current: this.current,
      total: this.total,
      cancelled: this.cancelled,
      status: this.status
    };
  }
}