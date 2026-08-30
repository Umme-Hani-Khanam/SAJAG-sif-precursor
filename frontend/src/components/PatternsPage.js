import React from "react";
import { getCluster, getClusters, getDashboardMetrics } from "../api/reports.js";
import { html } from "../ui.js";
import { PageTitle } from "./AnalyzePage.js";

export function PatternsPage() {
  const [clusters, setClusters] = React.useState([]);
  const [selected, setSelected] = React.useState(null);
  const [noise, setNoise] = React.useState(0);
  const [error, setError] = React.useState("");
  React.useEffect(() => {
    Promise.all([getClusters(), getDashboardMetrics()]).then(([rows, metrics]) => { setClusters(rows); setNoise(metrics.unclassified_candidates); }).catch((err) => setError(err.message));
  }, []);
  async function openCluster(id) { try { setSelected(await getCluster(id)); } catch (err) { setError(err.message); } }
  return html`<div className="space-y-6">
    <${PageTitle} eyebrow="PATTERNS" title="Precursor cluster explorer" subtitle="DBSCAN groups persisted safety embeddings. Cluster −1 remains explicitly unclassified and is never presented as an established pattern." />
    ${error ? html`<div className="error-box">${error}</div>` : null}
    <div className="grid gap-5 xl:grid-cols-[0.8fr_1.2fr]">
      <section className="space-y-3">
        <div className="rounded-2xl border border-dashed border-slate-300 bg-slate-100 p-4"><p className="text-sm font-semibold">Unclassified / noise</p><p className="mt-1 text-2xl font-bold">${noise}</p><p className="text-xs text-slate-500">Monitored through staged candidate-pattern rules.</p></div>
        ${clusters.length ? clusters.map((cluster) => html`
          <button type="button" key=${cluster.cluster_id} onClick=${() => openCluster(cluster.cluster_id)} className=${`w-full rounded-2xl border p-5 text-left shadow-sm transition hover:-translate-y-0.5 ${selected?.cluster_id === cluster.cluster_id ? "border-cyan-400 bg-cyan-50" : "border-slate-200 bg-white"}`}>
            <div className="flex justify-between gap-3"><p className="text-xs font-bold tracking-wider text-cyan-700">${cluster.cluster_code}</p>${cluster.emerging ? html`<span className="rounded-full bg-amber-100 px-2 py-1 text-[10px] font-bold text-amber-800">EMERGING</span>` : null}</div>
            <h2 className="mt-2 font-bold">${cluster.cluster_name}</h2><p className="mt-2 text-sm text-slate-500">${cluster.report_count} reports · ${cluster.sites_affected.length} sites · Avg SIF ${cluster.average_sif_score}</p>
            <p className="mt-2 text-xs text-slate-500">Control: ${cluster.dominant_critical_control_failure}</p>
          </button>`)
          : html`<div className="panel text-sm text-slate-500">No established clusters yet. Analyse the historical dataset first.</div>`}
      </section>
      <section className="panel min-h-[520px]">${selected ? html`<${ClusterDetail} cluster=${selected} />` : html`<div className="flex min-h-[430px] items-center justify-center text-center"><div><p className="text-lg font-semibold">Choose a cluster</p><p className="mt-2 text-sm text-slate-500">Its evidence, dominant controls, dates, and member reports will appear here.</p></div></div>`}</section>
    </div>
  </div>`;
}

function ClusterDetail({ cluster }) {
  return html`<div><p className="eyebrow">${cluster.cluster_code}</p><h2 className="mt-2 text-2xl font-bold">${cluster.cluster_name}</h2>
    <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">${[["Reports", cluster.report_count], ["Average SIF", cluster.average_sif_score], ["High", cluster.high_risk_count], ["Critical", cluster.critical_count]].map(([l, v]) => html`<div key=${l} className="rounded-2xl bg-slate-50 p-3"><p className="text-2xl font-bold">${v}</p><p className="text-xs text-slate-500">${l}</p></div>`)}</div>
    <dl className="mt-5 grid gap-4 text-sm md:grid-cols-2"><div><dt className="text-xs text-slate-500">Dominant hazard</dt><dd className="font-semibold">${cluster.dominant_hazard}</dd></div><div><dt className="text-xs text-slate-500">Dominant exposure</dt><dd className="font-semibold">${cluster.dominant_exposure}</dd></div><div><dt className="text-xs text-slate-500">Critical control</dt><dd className="font-semibold">${cluster.dominant_critical_control_failure}</dd></div><div><dt className="text-xs text-slate-500">Dominant precursor</dt><dd className="font-semibold">${cluster.dominant_precursor}</dd></div><div><dt className="text-xs text-slate-500">First / last seen</dt><dd>${cluster.first_seen} → ${cluster.last_seen}</dd></div><div><dt className="text-xs text-slate-500">Sites affected</dt><dd>${cluster.sites_affected.join(", ")}</dd></div><div><dt className="text-xs text-slate-500">Activities</dt><dd>${cluster.activities_affected.join(", ")}</dd></div><div><dt className="text-xs text-slate-500">High/Critical reports</dt><dd>${cluster.high_risk_count + cluster.critical_count}</dd></div></dl>
    <div className="mt-6"><h3 className="font-semibold">Cluster reports</h3><div className="mt-3 max-h-96 space-y-2 overflow-y-auto">${cluster.reports.map((report) => html`<article key=${report.report_id} className="rounded-xl border border-slate-200 p-3"><div className="flex justify-between gap-3"><b className="text-sm">${report.report_id}</b><span className="text-xs text-slate-500">${report.date}</span></div><p className="mt-2 text-sm leading-5 text-slate-600">${report.description}</p><p className="mt-2 text-xs text-slate-500">${report.site} · ${report.activity} · ${report.analysis?.risk_level || "pending"}</p></article>`)}</div></div>
  </div>`;
}
