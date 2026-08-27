import React from "react";
import { analyzeObservation } from "./api/analyze.js";
import { html } from "./ui.js";
import { AnalysisResults } from "./components/AnalysisResults.js";
import { AppHeader } from "./components/AppHeader.js";
import { EmptyState } from "./components/EmptyState.js";
import { ObservationForm } from "./components/ObservationForm.js";

const sampleObservation =
  "During scaffold material shifting, a worker leaned beyond the guardrail without fall protection while a suspended load moved overhead.";

export function App() {
  const [description, setDescription] = React.useState(sampleObservation);
  const [analysisResult, setAnalysisResult] = React.useState(null);
  const [apiError, setApiError] = React.useState("");
  const [isLoading, setIsLoading] = React.useState(false);

  async function handleSubmit(event) {
    if (event) {
      event.preventDefault();
    }

    if (!description.trim()) {
      setApiError("Please enter a safety observation before running analysis.");
      setAnalysisResult(null);
      return;
    }

    setIsLoading(true);
    setApiError("");

    try {
      const result = await analyzeObservation(description.trim());
      setAnalysisResult(result);
    } catch (error) {
      setAnalysisResult(null);
      setApiError(
        error instanceof Error
          ? error.message
          : "Unable to analyze the observation right now. Please verify the backend is running.",
      );
    } finally {
      setIsLoading(false);
    }
  }

  React.useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get("demo") === "1") {
      handleSubmit();
    }
  }, []);

  return html`
    <main className="min-h-screen px-4 py-6 text-slate-100 sm:px-6 lg:px-8">
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-6">
        <${AppHeader} />

        <div className="grid gap-6 xl:grid-cols-[0.95fr_1.05fr]">
          <${ObservationForm}
            description=${description}
            isLoading=${isLoading}
            onChange=${setDescription}
            onSubmit=${handleSubmit}
          />

          <section className="rounded-[2rem] border border-white/10 bg-slatebase/45 p-6 shadow-panel backdrop-blur">
            <div className="mb-4 flex items-center justify-between gap-4">
              <div>
                <h2 className="text-xl font-semibold text-white">Analysis Output</h2>
                <p className="mt-1 text-sm text-slate-300">
                  Structured safety intelligence from the prototype backend.
                </p>
              </div>
              ${isLoading
                ? html`
                    <span className="rounded-full border border-cyanaccent/30 bg-cyanaccent/10 px-3 py-1 text-xs font-medium text-cyanaccent">
                      Running analysis
                    </span>
                  `
                : null}
            </div>

            ${apiError
              ? html`
                  <div
                    role="alert"
                    className="mb-5 rounded-2xl border border-red-400/25 bg-red-500/10 px-4 py-3 text-sm text-red-100"
                  >
                    ${apiError}
                  </div>
                `
              : null}

            ${analysisResult
              ? html`<${AnalysisResults} result=${analysisResult} />`
              : html`<${EmptyState} />`}
          </section>
        </div>
      </div>
    </main>
  `;
}
