import React from "react";
import { getValidationRuns, runValidation, uploadValidationDataset } from "../api/phase3.js";
import { html } from "../ui.js";
import { PageTitle } from "./AnalyzePage.js";

const percent = (value) => value === null || value === undefined ? "—" : `${(Number(value) * 100).toFixed(1)}%`;

export function ValidationPage() {
  const [runs, setRuns] = React.useState([]); const [file, setFile] = React.useState(null);
  const [name, setName] = React.useState(""); const [dataset, setDataset] = React.useState(null);
  const [error, setError] = React.useState(""); const [busy, setBusy] = React.useState(false);
  const load = React.useCallback(async () => {
    try {
      setRuns(await getValidationRuns());
    } catch (err) {
      setError(err.message);
    }
  }, []);
  React.useEffect(() => { void load(); }, [load]);
  async function upload(event) { event.preventDefault(); if (!file) return setError("Select a labelled CSV dataset."); setBusy(true); try { setDataset(await uploadValidationDataset(file, name)); setError(""); } catch (err) { setError(err.message); } finally { setBusy(false); } }
  async function run() { setBusy(true); try { await runValidation(dataset.dataset_id); await load(); } catch (err) { setError(err.message); } finally { setBusy(false); } }
  const latest = runs[0]; const metrics = latest?.metrics;
  return html`<div className="space-y-6"><${PageTitle} eyebrow="VALIDATION" title="Labelled model-quality evidence" subtitle="Formal evaluation is kept separate from operational HSE agreement. Metrics are calculated from curated ground truth, never hardcoded." />${error ? html`<div className="error-box">${error}</div>` : null}<form className="panel" onSubmit=${upload}><p className="eyebrow">CURATED DATASET</p><div className="mt-4 grid gap-3 md:grid-cols-[1fr_1.5fr_auto]"><input className="filter-control" placeholder="Dataset name" value=${name} onChange=${(e) => setName(e.target.value)} required /><input className="filter-control" type="file" accept=".csv,text/csv" onChange=${(e) => setFile(e.target.files?.[0] || null)} /><button className="primary-button" disabled=${busy}>Load dataset</button></div><p className="mt-3 text-xs text-slate-500">Required fields: description, expected hazard/exposure/control/precursor/risk level.</p>${dataset ? html`<div className="mt-4 flex items-center justify-between rounded-xl bg-cyan-50 p-4"><span><b>${dataset.name}</b> · ${dataset.case_count} labelled cases</span><button type="button" className="primary-button" onClick=${run} disabled=${busy}>Run evaluation</button></div>` : null}</form>${latest ? html`<section className="panel"><div className="flex flex-wrap justify-between gap-3"><div><p className="eyebrow">LATEST FORMAL RUN</p><h2 className="mt-2 text-xl font-bold">${latest.run_id}</h2></div><p className="text-xs text-slate-500">${latest.model_version}<br />${latest.scoring_version}</p></div><div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">${[["Dataset size", metrics.dataset_size],["Precursor precision", percent(metrics.precursor_precision)],["Precursor recall", percent(metrics.precursor_recall)],["Precursor F1", percent(metrics.precursor_f1)],["High/Critical false negatives", metrics.high_critical_false_negatives],["False-negative rate", percent(metrics.high_critical_false_negative_rate)],["Risk exact", percent(metrics.risk_exact_agreement)],["Risk adjacent", percent(metrics.risk_adjacent_agreement)],["Critical-control agreement", percent(metrics.critical_control_agreement)]].map(([label,value]) => html`<article className="metric-card" key=${label}><p className="text-2xl font-bold">${value}</p><p className="mt-1 text-xs text-slate-500">${label}</p></article>`)}</div><details className="mt-5 rounded-xl bg-slate-50 p-4"><summary className="cursor-pointer font-semibold">Risk confusion matrix data</summary><pre className="mt-3 overflow-auto text-xs">${JSON.stringify(latest.confusion_matrix, null, 2)}</pre></details></section>` : html`<section className="panel text-sm text-slate-500">No formal validation run has been recorded yet.</section>`}</div>`;
}
