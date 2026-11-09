const API_URL = "/api";

const formatError = data => {
  if (typeof data === "string") return data;
  if (Array.isArray(data)) return data.map(formatError).join("; ");
  if (data && typeof data === "object") return Object.entries(data)
    .filter(([field]) => field !== "reference")
    .map(([field, value]) => `${["detail", "error", "non_field_errors"].includes(field) ? "" : `${field.replace(/_/g, " ")}: `}${formatError(value)}`).join("; ");
  return "";
};

export default class API {
  static token = localStorage.getItem("token");
  static onUnauthorized = null;

  static headers() {
    return { "Content-Type": "application/json", ...(this.token ? { Authorization: `Token ${this.token}` } : {}) };
  }

  static async perform(endpoint, options, consume, changesData = false) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 60000);
    let response;
    let reference = "";
    try {
      response = await fetch(`${API_URL}${endpoint}`, { ...options, signal: controller.signal });
      const suppliedReference = response.headers?.get?.("X-Request-ID") || "";
      if (/^[a-zA-Z0-9-]{1,64}$/.test(suppliedReference)) reference = suppliedReference;
      if (!response.ok) {
        const status = response.status || 400;
        const data = await response.json().catch(() => null);
        if (controller.signal.aborted) throw new TypeError("Timed out");
        let message;
        if (status >= 500) message = "BillTrack ran into a problem. Try again or contact the administrator.";
        else if (status === 401 && endpoint !== "/auth/login/") message = "Your sign-in has expired. Sign in again to continue.";
        else if (status === 403) message = "You do not have permission to do that. Contact the administrator.";
        else if (status === 404) message = "This record or page was not found. Refresh the list and try again.";
        else if (status === 429) message = "Too many requests. Wait a moment and try again.";
        else message = formatError(data) || "The request could not be completed. Refresh the page and try again.";
        const uncertain = changesData && status >= 500;
        if (uncertain) message += " The change may already have been saved. Check records before retrying.";
        if (reference) message += ` Reference: ${reference}.`;
        if (status === 401 && !["/auth/login/", "/auth/me/"].includes(endpoint)) this.onUnauthorized?.();
        throw Object.assign(new Error(message), { status, reference, uncertain, apiError: true });
      }
      return await consume(response);
    } catch (error) {
      if (error.apiError) throw error;
      let message = controller.signal.aborted
        ? "BillTrack did not respond within 60 seconds. Check the connection and try again."
        : error instanceof SyntaxError
          ? "BillTrack returned an unreadable response. Refresh the page or contact the administrator."
          : "Could not reach BillTrack. Check your network connection and that the server is running.";
      if (changesData) message += " The change may already have been saved. Check records before retrying.";
      if (reference) message += ` Reference: ${reference}.`;
      throw Object.assign(new TypeError(message), { status: response?.status || 0, reference, uncertain: changesData });
    } finally {
      clearTimeout(timeout);
    }
  }

  static request(endpoint, options = {}) {
    const changesData = Boolean(options.method && options.method !== "GET" && endpoint !== "/auth/login/" && endpoint !== "/reports/");
    return this.perform(endpoint, { ...options, headers: this.headers() },
      response => response.status === 204 ? null : response.json(), changesData);
  }

  static async login(username, password) {
    const data = await this.request("/auth/login/", { method: "POST", body: JSON.stringify({ username, password }) });
    if (!data?.token || !data?.user) throw new Error("Sign-in could not be confirmed. Try again or contact the administrator.");
    this.token = data.token;
    localStorage.setItem("token", data.token);
    return data;
  }

  static logout() { this.token = null; localStorage.removeItem("token"); }
  static get(endpoint) { return this.request(endpoint); }
  static post(endpoint, data) { return this.request(endpoint, { method: "POST", body: JSON.stringify(data) }); }
  static put(endpoint, data) { return this.request(endpoint, { method: "PUT", body: JSON.stringify(data) }); }
  static patch(endpoint, data) { return this.request(endpoint, { method: "PATCH", body: JSON.stringify(data) }); }
  static delete(endpoint) { return this.request(endpoint, { method: "DELETE" }); }

  static async getAll(endpoint) {
    let next = endpoint;
    const rows = [];
    while (next) {
      const data = await this.get(next.replace(/^https?:\/\/[^/]+\/api/, "").replace(/^\/api/, ""));
      if (Array.isArray(data)) return data;
      rows.push(...(data.results || []));
      next = data.next;
    }
    return rows;
  }

  static upload(endpoint, formData) {
    const headers = this.token ? { Authorization: `Token ${this.token}` } : {};
    return this.perform(endpoint, { method: "POST", headers, body: formData }, response => response.json(), true);
  }

  static document(endpoint) {
    return this.perform(endpoint, { headers: this.headers() }, async response => {
      const document = await response.blob();
      if (!document.size || document.type.includes("application/json")) throw new SyntaxError("Unexpected invoice response");
      return document;
    });
  }

  static async download(endpoint, data, filename) {
    const blob = await this.perform(endpoint, { method: "POST", headers: this.headers(), body: JSON.stringify(data) }, async response => {
      const file = await response.blob();
      if (!file.size || /text\/html|application\/json/.test(file.type)) throw new SyntaxError("Unexpected download response");
      return file;
    });
    let url;
    let link;
    try {
      url = URL.createObjectURL(blob);
      link = document.createElement("a");
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch {
      if (url) URL.revokeObjectURL(url);
      throw new Error("The file could not be downloaded. Allow downloads for BillTrack and try again.");
    } finally {
      link?.remove();
    }
  }
}
