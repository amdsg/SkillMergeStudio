export const EVENTS = {
  REQUEST: "wb.request",
  RESPONSE: "wb.response",
  FOCUS: "ui.focusTarget",
};

export function envelope(data, requestId = "") {
  return {
    protocol: "wb-1",
    request_id: requestId,
    ok: true,
    data,
    sent_at: new Date().toISOString(),
  };
}

export function isEnvelope(payload) {
  return Boolean(payload && payload.protocol === "wb-1" && "ok" in payload);
}