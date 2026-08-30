export function resolveApiBaseUrl() {
  const defaultUrl = "http://127.0.0.1:8000";
  if (typeof window === "undefined") return defaultUrl;
  return new URLSearchParams(window.location.search).get("api") || defaultUrl;
}

export function actorHeaders() {
  if (typeof window === "undefined") return { "X-Actor-Name": "Demo HSE Manager", "X-Actor-Role": "HSE_MANAGER" };
  const token = window.localStorage.getItem("sajagAccessToken");
  if (token) return { Authorization: `Bearer ${token}` };
  if (window.localStorage.getItem("sajagDemoMode") !== "true") return {};
  return {
    "X-Actor-Name": window.localStorage.getItem("sajagActorName") || "Demo HSE Manager",
    "X-Actor-Role": window.localStorage.getItem("sajagActorRole") || "HSE_MANAGER",
  };
}

export async function parseResponse(response) {
  let payload = null;
  try { payload = await response.json(); } catch { payload = null; }
  if (!response.ok) {
    const detail = payload?.detail;
    const message = typeof detail === "string" ? detail : detail?.message;
    throw new Error(message || "The request could not be completed.");
  }
  return payload;
}

function queryString(filters = {}) {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (value !== "" && value !== null && value !== undefined) params.set(key, value);
  });
  const value = params.toString();
  return value ? `?${value}` : "";
}

export async function uploadReports(file) {
  const formData = new FormData();
  formData.append("file", file);
  return parseResponse(await fetch(`${resolveApiBaseUrl()}/reports/upload`, { method: "POST", headers: actorHeaders(), body: formData }));
}

export async function uploadPdfReport(file, context = {}) {
  const formData = new FormData();
  formData.append("file", file);
  Object.entries(context).forEach(([key, value]) => { if (value) formData.append(key, value); });
  return parseResponse(await fetch(`${resolveApiBaseUrl()}/reports/upload-pdf`, { method: "POST", headers: actorHeaders(), body: formData }));
}

export async function getReports(filters = {}) {
  return parseResponse(await fetch(`${resolveApiBaseUrl()}/reports${queryString(filters)}`, { headers: actorHeaders() }));
}

export async function getReport(reportId) {
  return parseResponse(await fetch(`${resolveApiBaseUrl()}/reports/${encodeURIComponent(reportId)}`, { headers: actorHeaders() }));
}

export async function getAnalysisStatus() {
  return parseResponse(await fetch(`${resolveApiBaseUrl()}/analysis/status`, { headers: actorHeaders() }));
}

export async function analyzeHistoricalDataset(options = {}) {
  return parseResponse(await fetch(`${resolveApiBaseUrl()}/analysis/batch`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...actorHeaders() },
    body: JSON.stringify({ include_failed: true, reanalyze_all: false, use_gemini: false, ...options }),
  }));
}

export async function getDashboardMetrics() {
  return parseResponse(await fetch(`${resolveApiBaseUrl()}/metrics/dashboard`, { headers: actorHeaders() }));
}

export async function getTrends(filters = {}) {
  return parseResponse(await fetch(`${resolveApiBaseUrl()}/analytics/trends${queryString(filters)}`, { headers: actorHeaders() }));
}

export async function getClusters() {
  return parseResponse(await fetch(`${resolveApiBaseUrl()}/clusters`, { headers: actorHeaders() }));
}

export async function getCluster(clusterId) {
  return parseResponse(await fetch(`${resolveApiBaseUrl()}/clusters/${encodeURIComponent(clusterId)}`, { headers: actorHeaders() }));
}

export async function getEmergingRisks() {
  return parseResponse(await fetch(`${resolveApiBaseUrl()}/emerging-risks`, { headers: actorHeaders() }));
}

export function exportCsvUrl(filters = {}) {
  return `${resolveApiBaseUrl()}/reports/export.csv${queryString(filters)}`;
}

export async function downloadReportsCsv(filters = {}) {
  const response = await fetch(exportCsvUrl(filters), { headers: actorHeaders() });
  if (!response.ok) await parseResponse(response);
  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement("a"); link.href = url; link.download = "sajag-report-export.csv"; link.click();
  URL.revokeObjectURL(url);
}

export async function checkBackendHealth() {
  return parseResponse(await fetch(`${resolveApiBaseUrl()}/health`));
}
