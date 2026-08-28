import React from "react";
import { analyzeObservation } from "./api/analyze.js";
import { getReports, uploadPdfReport } from "./api/reports.js";
import { html } from "./ui.js";

import { AnalysisResults } from "./components/AnalysisResults.js";
import { AppHeader } from "./components/AppHeader.js";
import { EmptyState } from "./components/EmptyState.js";
import { ObservationForm } from "./components/ObservationForm.js";
import { ReportManagement } from "./components/ReportManagement.js";

const sampleObservation =
  "During scaffold material shifting, a worker leaned beyond the guardrail without fall protection while a suspended load moved overhead.";

export function App() {
  const [description, setDescription] =
    React.useState(sampleObservation);
  const [inputMode, setInputMode] =
    React.useState("text");
  const [pdfFile, setPdfFile] =
    React.useState(null);

  const [site, setSite] = React.useState("");

  const [activity, setActivity] =
    React.useState("");

  const [analysisResult, setAnalysisResult] =
    React.useState(null);

  const [apiError, setApiError] =
    React.useState("");

  const [isLoading, setIsLoading] =
    React.useState(false);
  const [isPdfLoading, setIsPdfLoading] =
    React.useState(false);
  const [pdfError, setPdfError] =
    React.useState("");
  const [historicalReportCount, setHistoricalReportCount] =
    React.useState(0);

  React.useEffect(() => {
    let isMounted = true;

    async function loadHistoricalCount() {
      try {
        const reports = await getReports();
        if (isMounted) {
          setHistoricalReportCount(Array.isArray(reports) ? reports.length : 0);
        }
      } catch {
        if (isMounted) {
          setHistoricalReportCount(0);
        }
      }
    }

    loadHistoricalCount();

    return () => {
      isMounted = false;
    };
  }, []);

  async function runAnalysis(
    observation = description,
    observationSite = site,
    observationActivity = activity,
  ) {
    if (!observation.trim()) {
      setApiError(
        "Please enter a safety observation before running analysis.",
      );

      setAnalysisResult(null);
      return;
    }

    setIsLoading(true);
    setApiError("");

    try {
      const result = await analyzeObservation(
        observation.trim(),
        observationSite.trim(),
        observationActivity.trim(),
      );

      setAnalysisResult(result);
    } catch (error) {
      setAnalysisResult(null);

      setApiError(
        error instanceof Error
          ? error.message
          : "Unable to analyze the observation. Please verify that the backend is running.",
      );
    } finally {
      setIsLoading(false);
    }
  }

  async function handlePdfSubmit(event) {
    if (event) {
      event.preventDefault();
    }

    if (!pdfFile) {
      setPdfError("Please select a PDF report before starting analysis.");
      return;
    }

    setIsPdfLoading(true);
    setPdfError("");
    setApiError("");

    try {
      const result = await uploadPdfReport(pdfFile);

      setAnalysisResult(result);
      setPdfFile(null);

      window.scrollTo({
        top: 0,
        behavior: "smooth",
      });
    } catch (error) {
      setAnalysisResult(null);
      setPdfError(
        error instanceof Error
          ? error.message
          : "Unable to analyze the uploaded PDF right now.",
      );
    } finally {
      setIsPdfLoading(false);
    }
  }

  async function handleSubmit(event) {
    if (event) {
      event.preventDefault();
    }

    await runAnalysis();
  }

  return html`
    <main className="min-h-screen bg-slate-50 px-4 py-6 text-slate-900 sm:px-6 lg:px-8">

      <div className="mx-auto flex w-full max-w-7xl flex-col gap-6">

        <${AppHeader} />


        <!-- ANALYSIS -->

        <div className="grid gap-6 xl:grid-cols-[0.95fr_1.05fr]">

          <${ObservationForm}
            description=${description}
            inputMode=${inputMode}
            site=${site}
            activity=${activity}
            isLoading=${isLoading}
            isPdfLoading=${isPdfLoading}
            pdfFileName=${pdfFile?.name || ""}
            pdfError=${pdfError}
            onChange=${setDescription}
            onModeChange=${(mode) => {
              setInputMode(mode);
              setApiError("");
              setPdfError("");
            }}
            onPdfSelect=${(file) => {
              setPdfFile(file);
              setPdfError("");
            }}
            onSiteChange=${setSite}
            onActivityChange=${setActivity}
            onSubmit=${handleSubmit}
            onPdfSubmit=${handlePdfSubmit}
          />


          <section className="min-h-[600px] rounded-[2rem] border border-slate-200 bg-white p-6 shadow-sm">

            <div className="mb-5 flex items-center justify-between gap-4">

              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.25em] text-cyan-600">
                  RESULTS
                </p>

                <h2 className="mt-1 text-2xl font-semibold text-slate-900">
                  Analysis Output
                </h2>

                <p className="mt-1 text-sm text-slate-500">
                  Safety intelligence generated from the submitted observation.
                </p>
              </div>

              ${isLoading || isPdfLoading
                ? html`
                    <span className="rounded-full border border-cyan-200 bg-cyan-50 px-3 py-1 text-xs font-medium text-cyan-700">
                      ${isPdfLoading ? "Analyzing PDF..." : "Analyzing..."}
                    </span>
                  `
                : null}

            </div>


            ${apiError
              ? html`
                  <div
                    role="alert"
                    className="mb-5 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
                  >
                    ${apiError}
                  </div>
                `
              : null}


            ${analysisResult
              ? html`
                  <${AnalysisResults}
                    result=${analysisResult}
                    historicalReportCount=${historicalReportCount}
                  />
                `
              : html`
                  <${EmptyState} />
                `}

          </section>

        </div>


        <!-- REPORT MANAGEMENT -->

        <${ReportManagement}
          onReportsLoaded=${(reports) =>
            setHistoricalReportCount(Array.isArray(reports) ? reports.length : 0)}
        />

      </div>
    </main>
  `;
}
