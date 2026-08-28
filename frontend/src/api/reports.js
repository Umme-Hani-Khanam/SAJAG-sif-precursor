function resolveApiBaseUrl() {
  const defaultUrl = "http://127.0.0.1:8000";

  if (typeof window === "undefined") {
    return defaultUrl;
  }

  const params = new URLSearchParams(window.location.search);
  return params.get("api") || defaultUrl;
}

async function parseResponse(response) {
  let payload = null;

  try {
    payload = await response.json();
  } catch {
    payload = null;
  }

  if (!response.ok) {
    const message =
      typeof payload?.detail === "string"
        ? payload.detail
        : "The request could not be completed.";

    throw new Error(message);
  }

  return payload;
}

export async function uploadReports(file) {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(
    `${resolveApiBaseUrl()}/reports/upload`,
    {
      method: "POST",
      body: formData,
    },
  );

  return parseResponse(response);
}

export async function uploadPdfReport(file) {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(
    `${resolveApiBaseUrl()}/reports/upload-pdf`,
    {
      method: "POST",
      body: formData,
    },
  );

  return parseResponse(response);
}

export async function getReports() {
  const response = await fetch(
    `${resolveApiBaseUrl()}/reports`,
  );

  return parseResponse(response);
}

export async function getReport(reportId) {
  const response = await fetch(
    `${resolveApiBaseUrl()}/reports/${encodeURIComponent(reportId)}`,
  );

  return parseResponse(response);
}

export async function checkBackendHealth() {
  const response = await fetch(
    `${resolveApiBaseUrl()}/health`,
  );

  return parseResponse(response);
}