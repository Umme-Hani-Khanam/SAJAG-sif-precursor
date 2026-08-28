function resolveApiBaseUrl() {
  const defaultUrl = "http://127.0.0.1:8000";

  if (typeof window === "undefined") {
    return defaultUrl;
  }

  const params = new URLSearchParams(window.location.search);
  return params.get("api") || defaultUrl;
}

export async function analyzePdf(file) {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(
    `${resolveApiBaseUrl()}/reports/upload-pdf`,
    {
      method: "POST",
      body: formData,
    },
  );

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
        : "Unable to analyze the PDF.";

    throw new Error(message);
  }

  return payload;
}