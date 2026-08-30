import { actorHeaders, parseResponse, resolveApiBaseUrl } from "./reports.js";

async function request(path, method = "GET", body = null) {
  return parseResponse(await fetch(`${resolveApiBaseUrl()}${path}`, {
    method, headers: { ...(body ? { "Content-Type": "application/json" } : {}), ...actorHeaders() },
    body: body ? JSON.stringify(body) : undefined,
  }));
}

export async function login(identifier, password) {
  return parseResponse(await fetch(`${resolveApiBaseUrl()}/auth/login`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ identifier, password }),
  }));
}
export const me = () => request("/auth/me");
export const logout = () => request("/auth/logout", "POST");
export const getNotifications = (unread = false) => request(`/notifications${unread ? "?unread=true" : ""}`);
export const getUnreadCount = () => request("/notifications/unread-count");
export const markNotificationRead = (id) => request(`/notifications/${encodeURIComponent(id)}/read`, "POST");
export const markAllNotificationsRead = () => request("/notifications/read-all", "POST");
export const getJobs = () => request("/jobs");
export const startHistoricalJob = (options = {}) => request("/jobs/historical-analysis", "POST", { include_failed: true, reanalyze_all: false, use_gemini: false, ...options });
export const getValidationRuns = () => request("/validation/runs");
export const runValidation = (id) => request(`/validation/datasets/${encodeURIComponent(id)}/run`, "POST");

export async function analyzePhoto(file, context) {
  const form = new FormData(); form.append("file", file);
  Object.entries(context).forEach(([key, value]) => { if (value) form.append(key, value); });
  return parseResponse(await fetch(`${resolveApiBaseUrl()}/analyze/photo`, { method: "POST", headers: actorHeaders(), body: form }));
}

export async function uploadValidationDataset(file, name, description = "") {
  const form = new FormData(); form.append("file", file); form.append("name", name); form.append("description", description);
  return parseResponse(await fetch(`${resolveApiBaseUrl()}/validation/datasets`, { method: "POST", headers: actorHeaders(), body: form }));
}
