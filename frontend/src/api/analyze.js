function resolveApiBaseUrl() {
  const defaultUrl = "http://127.0.0.1:8000";

  if (typeof window === "undefined") {
    return defaultUrl;
  }

  const params = new URLSearchParams(window.location.search);
  return params.get("api") || defaultUrl;
}

function normalizeErrorMessage(errorPayload, fallbackMessage) {
  if (!errorPayload) {
    return fallbackMessage;
  }

  if (typeof errorPayload === "string") {
    return errorPayload;
  }

  if (typeof errorPayload.detail === "string") {
    return errorPayload.detail;
  }

  return fallbackMessage;
}

export async function analyzeObservation(
  description,
  site = "",
  activity = "",
) {
  const response = await fetch(
    `${resolveApiBaseUrl()}/analyze`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        description,
        site,
        activity,
      }),
    },
  );

  let payload = null;

  try {
    payload = await response.json();
  } catch {
    payload = null;
  }

  if (!response.ok) {
    throw new Error(
      normalizeErrorMessage(
        payload,
        "Unable to analyze the observation right now. Please verify the backend is running.",
      ),
    );
  }

  return payload;
}