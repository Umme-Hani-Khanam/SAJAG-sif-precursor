import React from "react";
import { analyzeObservation } from "../api/analyze.js";
import { getAnalysisStatus, uploadPdfReport } from "../api/reports.js";
import { analyzePhoto } from "../api/phase3.js";
import { html } from "../ui.js";
import { AnalysisResults } from "./AnalysisResults.js";
import { EmptyState } from "./EmptyState.js";
import { ObservationForm } from "./ObservationForm.js";

const sampleObservation =
  "During scaffold material shifting, a worker leaned beyond the guardrail without fall protection while a suspended load moved overhead.";

export function AnalyzePage({ actor }) {
  const [description, setDescription] = React.useState(sampleObservation);
  const [inputMode, setInputMode] = React.useState("text");
  const [pdfFile, setPdfFile] = React.useState(null);
  const [photoFile, setPhotoFile] = React.useState(null);
  const [site, setSite] = React.useState("");
  const [activity, setActivity] = React.useState("");
  const [observedAt, setObservedAt] = React.useState(new Date().toISOString().slice(0, 16));
  const [result, setResult] = React.useState(null);
  const [error, setError] = React.useState("");
  const [loading, setLoading] = React.useState(false);
  const [pdfLoading, setPdfLoading] = React.useState(false);
  const [pdfError, setPdfError] = React.useState("");
  const [photoError, setPhotoError] = React.useState("");
  const [photoLoading, setPhotoLoading] = React.useState(false);
  const [status, setStatus] = React.useState({ total_reports: 0, analysed: 0, pending: 0, failed: 0 });

  React.useEffect(() => { getAnalysisStatus().then(setStatus).catch(() => {}); }, []);

  async function runAnalysis(observation = description, observationSite = site, observationActivity = activity) {
    if (!observation.trim()) { setError("Please enter a safety observation before running analysis."); return; }
    setLoading(true); setError("");
    try { setResult(await analyzeObservation(observation.trim(), observationSite.trim(), observationActivity.trim(), observedAt)); }
    catch (err) { setResult(null); setError(err instanceof Error ? err.message : "Unable to analyze the observation."); }
    finally { setLoading(false); }
  }

  async function handlePdfSubmit(event) {
    event?.preventDefault();
    if (!pdfFile) { setPdfError("Please select a PDF report before starting analysis."); return; }
    setPdfLoading(true); setPdfError(""); setError("");
    try { setResult(await uploadPdfReport(pdfFile, { site, activity, observed_at: observedAt })); setPdfFile(null); }
    catch (err) { setResult(null); setPdfError(err instanceof Error ? err.message : "Unable to analyze the PDF."); }
    finally { setPdfLoading(false); }
  }

  async function handlePhotoSubmit(event) {
    event?.preventDefault(); if (!photoFile) { setPhotoError("Please select a JPG, PNG, or WEBP hazard photo."); return; }
    setPhotoLoading(true); setPhotoError(""); setError("");
    try { setResult(await analyzePhoto(photoFile, { description, site, activity, observed_at: observedAt })); setPhotoFile(null); }
    catch (err) { setResult(null); setPhotoError(err instanceof Error ? err.message : "Unable to analyze the photo."); }
    finally { setPhotoLoading(false); }
  }

  return html`
    <div className="space-y-6">
      <${PageTitle} eyebrow="ANALYZE" title="SIF precursor detection" subtitle="Extract structured hazards, score the potential, and connect the observation to persisted historical evidence." />
      <div className="grid items-start gap-6 xl:grid-cols-[0.88fr_1.12fr]">
        <div className="space-y-5 xl:sticky xl:top-24">
          <${ObservationForm}
            description=${description} inputMode=${inputMode} site=${site} activity=${activity}
            observedAt=${observedAt}
            isLoading=${loading} isPdfLoading=${pdfLoading} pdfFileName=${pdfFile?.name || ""} pdfError=${pdfError}
            photoFileName=${photoFile?.name || ""} photoError=${photoError} isPhotoLoading=${photoLoading}
            onChange=${setDescription} onModeChange=${(mode) => { setInputMode(mode); setError(""); setPdfError(""); setPhotoError(""); }}
            onPdfSelect=${(file) => { setPdfFile(file); setPdfError(""); }}
            onPhotoSelect=${(file) => { setPhotoFile(file); setPhotoError(""); }}
            onSiteChange=${setSite} onActivityChange=${setActivity}
            onObservedAtChange=${setObservedAt}
            onSubmit=${(event) => { event?.preventDefault(); runAnalysis(); }} onPdfSubmit=${handlePdfSubmit} onPhotoSubmit=${handlePhotoSubmit}
          />
          <${AnalysisContext} context=${result?.analysis_context} status=${status} />
        </div>
        <section className="min-h-[640px] rounded-[2rem] border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
          <div className="mb-5 flex items-center justify-between gap-4">
            <div><p className="eyebrow">RESULTS</p><h2 className="mt-1 text-2xl font-semibold">Analysis output</h2></div>
            ${loading || pdfLoading || photoLoading ? html`<span className="status-pill">${pdfLoading ? "Extracting PDF/OCR…" : photoLoading ? "Inspecting visual evidence…" : "Analyzing…"}</span>` : null}
          </div>
          ${error ? html`<div role="alert" className="error-box mb-5">${error}</div>` : null}
          ${result ? html`<${AnalysisResults} result=${result} historicalReportCount=${status.analysed} actor=${actor} />` : html`<${EmptyState} />`}
        </section>
      </div>
    </div>
  `;
}

function AnalysisContext({ context, status }) {
  const values = context || {
    historical_reports_loaded: status.analysed,
    reports_from_selected_site: 0,
    recent_reports: 0,
    matching_precursor_count: 0,
    site_trend_indicator: "Run an analysis to calculate",
  };
  return html`
    <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
      <p className="eyebrow">LIVE CONTEXT</p>
      <div className="mt-4 grid grid-cols-2 gap-3">
        ${[
          ["Historical analysed", values.historical_reports_loaded],
          ["Selected site", values.reports_from_selected_site],
          ["Recent reports", values.recent_reports],
          ["Same precursor", values.matching_precursor_count],
        ].map(([label, value]) => html`<div key=${label} className="rounded-2xl bg-slate-50 p-3"><p className="text-xl font-bold">${value}</p><p className="text-xs text-slate-500">${label}</p></div>`)}
      </div>
      <div className="mt-3 rounded-2xl border border-slate-200 p-3 text-sm text-slate-600">
        <span className="font-semibold text-slate-900">Site trend:</span> ${values.site_trend_indicator}
      </div>
      <p className="mt-3 text-xs text-slate-500">Pending ${status.pending} · Failed ${status.failed}</p>
    </section>
  `;
}

export function PageTitle({ eyebrow, title, subtitle }) {
  return html`<div><p className="eyebrow">${eyebrow}</p><h1 className="mt-2 text-3xl font-bold tracking-tight text-slate-900">${title}</h1><p className="mt-2 max-w-3xl text-sm leading-6 text-slate-500">${subtitle}</p></div>`;
}
