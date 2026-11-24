const DEFAULT_AGENT = "http://127.0.0.1:8788";

export const PROTOCOL_VERSION = "wb-1";

export function createAgentClient(base = DEFAULT_AGENT, token = "") {
  async function request(method, path, payload, headers = {}) {
    const options = {
      method,
      headers: {
        "Content-Type": "application/json",
        "X-WB-CSRF": "1",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...headers,
      },
      credentials: "omit",
    };
    if (payload !== undefined) {
      options.body = JSON.stringify(payload);
    }
    const response = await fetch(`${base}${path}`, options);
    const data = await response.json();
    if (!data.ok) {
      const error = new Error(data.error?.code || "E_INTERNAL");
      error.code = data.error?.code;
      error.messageKey = data.error?.message_key;
      error.fixKey = data.error?.fix_key;
      throw error;
    }
    return data.data;
  }
  return {
    health: () => request("GET", "/health"),
    search: (payload) => request("POST", "/search", payload),
    download: (payload) => request("POST", "/download", payload),
    preview: (payload) => request("POST", "/install/preview", payload),
    convert: (payload) => request("POST", "/convert", payload),
    merge: (payload) => request("POST", "/merge", payload),
    upgrade: (payload) => request("POST", "/upgrade/check", payload),
  };
}