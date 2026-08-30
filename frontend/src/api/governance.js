import { actorHeaders, parseResponse, resolveApiBaseUrl } from "./reports.js";

async function jsonRequest(path, method = "GET", body = null) {
  return parseResponse(await fetch(`${resolveApiBaseUrl()}${path}`, {
    method,
    headers: { "Content-Type": "application/json", ...actorHeaders() },
    body: body === null ? undefined : JSON.stringify(body),
  }));
}

export const submitReview = (reportId, payload) => jsonRequest(`/reports/${encodeURIComponent(reportId)}/reviews`, "POST", payload);
export const getReviewedAnalysis = (reportId) => jsonRequest(`/reports/${encodeURIComponent(reportId)}/reviewed-analysis`);
export const getCapas = () => jsonRequest("/capas");
export const createCapa = (payload) => jsonRequest("/capas", "POST", payload);
export const assignCapa = (id, payload) => jsonRequest(`/capas/${encodeURIComponent(id)}/assign`, "POST", payload);
export const changeCapaStatus = (id, status, note = "") => jsonRequest(`/capas/${encodeURIComponent(id)}/status`, "POST", { status, note });
export const addCapaEvidence = (id, payload) => jsonRequest(`/capas/${encodeURIComponent(id)}/evidence`, "POST", payload);
export const submitCapaVerification = (id, note) => jsonRequest(`/capas/${encodeURIComponent(id)}/submit-verification`, "POST", { note });
export const verifyCapa = (id, note) => jsonRequest(`/capas/${encodeURIComponent(id)}/verify`, "POST", { note });
export const reopenCapa = (id, note) => jsonRequest(`/capas/${encodeURIComponent(id)}/reopen`, "POST", { note });
export const getAudit = (filters = {}) => {
  const params = new URLSearchParams(Object.entries(filters).filter(([, value]) => value));
  return jsonRequest(`/audit${params.toString() ? `?${params}` : ""}`);
};
export const getAlerts = () => jsonRequest("/alerts");
export const decideAlert = (id, decision, reason = "") => jsonRequest(`/alerts/${encodeURIComponent(id)}/decision`, "POST", { decision, reason });
export const getCriticalControls = () => jsonRequest("/analytics/critical-controls");
export const getAgreementMetrics = () => jsonRequest("/analytics/hse-agreement");
export const getDocuments = () => jsonRequest("/knowledge/documents");
export const getDocument = (id) => jsonRequest(`/knowledge/documents/${encodeURIComponent(id)}`);
export const approveDocument = (id) => jsonRequest(`/knowledge/documents/${encodeURIComponent(id)}/approve`, "POST");
export const retireDocument = (id) => jsonRequest(`/knowledge/documents/${encodeURIComponent(id)}/retire`, "POST");

export async function uploadKnowledgeDocument(file, metadata) {
  const form = new FormData(); form.append("file", file);
  Object.entries(metadata).forEach(([key, value]) => form.append(key, value || ""));
  return parseResponse(await fetch(`${resolveApiBaseUrl()}/knowledge/documents`, { method: "POST", headers: actorHeaders(), body: form }));
}
