import { actorHeaders, resolveApiBaseUrl } from "./reports.js";

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
  observedAt = "",
) {
  const response = await fetch(
    `${resolveApiBaseUrl()}/analyze`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...actorHeaders(),
      },
      body: JSON.stringify({
        description,
        site,
        activity,
        observed_at: observedAt || null,
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
