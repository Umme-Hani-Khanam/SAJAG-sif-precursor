import React from "react";
import { getDashboardMetrics, getReports, getTrends } from "../api/reports.js";
import { html } from "../ui.js";
import { PageTitle } from "./AnalyzePage.js";
import { getCriticalControls } from "../api/governance.js";

export function DashboardPage() {
  const [metrics, setMetrics] = React.useState(null);
  const [trends, setTrends] = React.useState(null);
  const [reports, setReports] = React.useState([]);
  const [filters, setFilters] = React.useState({ date_from: "", date_to: "", site: "", risk_level: "", precursor: "", cluster_id: "" });
  const [error, setError] = React.useState("");
  const [controls, setControls] = React.useState([]);

  React.useEffect(() => {
    Promise.all([getDashboardMetrics(), getTrends(filters), getReports(), getCriticalControls()])
      .then(([m, t, r, c]) => { setMetrics(m); setTrends(t); setReports(r); setControls(c.controls || []); setError(""); })
      .catch((err) => setError(err.message));
  }, []);

  async function applyFilters() {
    try { setTrends(await getTrends(filters)); setError(""); } catch (err) { setError(err.message); }
  }

  if (!metrics) return html`<div className="panel">${error || "Loading live dashboard…"}</div>`;
  const cards = [
    ["Total reports", metrics.total_reports], ["Analysed", metrics.analysed],
    ["High risk", metrics.high_risk_reports], ["Critical", metrics.critical_reports],
    ["Emerging patterns", metrics.emerging_patterns], ["Unclassified candidates", metrics.unclassified_candidates],
  ];
  const sites = unique(reports.map((r) => r.site || r.location_site));
  const departments = unique(reports.map((r) => r.department));
  const activities = unique(reports.map((r) => r.activity));
  const precursors = unique(reports.map((r) => r.analysis?.precursor_pattern));
  const clusters = unique(reports.map((r) => r.analysis?.cluster_id).filter((v) => v !== null && v >= 0));

  return html`
    <div className="space-y-6">
      <${PageTitle} eyebrow="DASHBOARD" title="Historical SIF intelligence" subtitle="Transparent precursor frequency, risk mix, control failures, and time trends from persisted analysis records." />
      ${error ? html`<div className="error-box">${error}</div>` : null}
      <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
        ${cards.map(([label, value]) => html`<article className="metric-card" key=${label}><p className="text-3xl font-bold">${value}</p><p className="mt-1 text-xs font-semibold uppercase tracking-wide text-slate-500">${label}</p></article>`)}
      </section>
      <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-8">
        ${[
          ["Unreviewed AI", metrics.unreviewed_ai_analyses], ["Confirmed", metrics.confirmed_analyses], ["Corrected", metrics.corrected_analyses],
          ["Open CAPAs", metrics.open_capas], ["Overdue CAPAs", metrics.overdue_capas], ["Awaiting verification", metrics.awaiting_verification],
          ["Critical alerts", metrics.critical_alerts], ["HSE agreement", metrics.hse_agreement?.hse_agreement_rate === null ? "—" : `${metrics.hse_agreement?.hse_agreement_rate}%`],
        ].map(([label, value]) => html`<article className="metric-card" key=${label}><p className="text-2xl font-bold">${value}</p><p className="mt-1 text-[10px] font-semibold uppercase tracking-wide text-slate-500">${label}</p></article>`)}
      </section>
      <section className="panel"><p className="eyebrow">PHASE 3A OPERATIONS</p><div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-8">${[
        ["Pending jobs", metrics.phase3a?.pending_jobs], ["Failed jobs", metrics.phase3a?.failed_jobs],
        ["Unread critical", metrics.phase3a?.unread_critical_notifications], ["Low-confidence High/Critical", metrics.phase3a?.low_confidence_high_critical],
        ["Approved docs", metrics.phase3a?.documents?.approved], ["Draft docs", metrics.phase3a?.documents?.draft],
        ["Superseded docs", metrics.phase3a?.documents?.superseded], ["Review due", metrics.phase3a?.documents?.review_due],
      ].map(([label, value]) => html`<article className="metric-card" key=${label}><p className="text-2xl font-bold">${value ?? 0}</p><p className="mt-1 text-[10px] font-semibold uppercase tracking-wide text-slate-500">${label}</p></article>`)}</div>${metrics.phase3a?.validation ? html`<div className="mt-5 rounded-2xl bg-violet-50 p-4"><div className="flex flex-wrap justify-between gap-3"><div><p className="text-xs font-bold text-violet-700">FORMAL LABELLED VALIDATION</p><p className="mt-1 text-sm">${metrics.phase3a.validation.metrics.dataset_size} cases · Precursor F1 ${(metrics.phase3a.validation.metrics.precursor_f1 * 100).toFixed(1)}% · High/Critical false negatives ${metrics.phase3a.validation.metrics.high_critical_false_negatives}</p></div><a href="#validation" className="secondary-button">Open validation</a></div></div>` : html`<p className="mt-4 text-sm text-slate-500">No formal labelled validation run yet. HSE agreement below remains an operational review metric, not accuracy.</p>`}</section>
      <section className="grid gap-5 lg:grid-cols-2">
        <article className="panel"><p className="eyebrow">PRIORITY SIGNALS</p><dl className="mt-4 space-y-4">
          <div><dt className="text-xs text-slate-500">Top critical-control failure</dt><dd className="mt-1 font-semibold">${metrics.top_critical_control_failure}</dd></div>
          <div><dt className="text-xs text-slate-500">Highest-risk site</dt><dd className="mt-1 font-semibold">${metrics.highest_risk_site}</dd></div>
        </dl></article>
        <article className="panel"><p className="eyebrow">ANALYSIS COVERAGE</p><div className="mt-4 h-3 overflow-hidden rounded-full bg-slate-100"><div className="h-full bg-cyan-500" style=${{ width: `${metrics.total_reports ? metrics.analysed / metrics.total_reports * 100 : 0}%` }}></div></div><p className="mt-3 text-sm text-slate-600">${metrics.pending} pending · ${metrics.failed} failed. Only analysed records drive intelligence.</p></article>
      </section>
      <section className="panel"><p className="eyebrow">HSE AGREEMENT TRACKING</p><h2 className="mt-2 text-xl font-semibold">AI versus latest operational HSE decision</h2><p className="mt-1 text-xs text-slate-500">These are human-review agreement measures, not formal labelled validation or model accuracy.</p><div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-6">${[
        ["Reviewed", metrics.hse_agreement?.reviewed_reports], ["Overall agreement", metrics.hse_agreement?.hse_agreement_rate], ["Risk agreement", metrics.hse_agreement?.risk_level_agreement], ["Precursor agreement", metrics.hse_agreement?.precursor_agreement], ["Control agreement", metrics.hse_agreement?.critical_control_agreement], ["Correction / rejected", metrics.hse_agreement?.correction_rate === null ? null : `${metrics.hse_agreement.correction_rate}% / ${metrics.hse_agreement.rejected_flag_rate}%`],
      ].map(([label, value], index) => html`<div className="rounded-xl bg-slate-50 p-3" key=${label}><p className="text-xl font-bold">${value === null || value === undefined ? "—" : index > 0 && index < 5 ? `${value}%` : value}</p><p className="text-xs text-slate-500">${label}</p></div>`)}</div></section>

      <section className="panel">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between"><div><p className="eyebrow">REAL-TIME FILTERS</p><h2 className="mt-2 text-xl font-semibold">Trend analysis</h2></div><button className="primary-button" onClick=${applyFilters}>Apply filters</button></div>
        <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-7">
          <${FilterInput} label="From" type="date" value=${filters.date_from} onChange=${(v) => setFilters({ ...filters, date_from: v })} />
          <${FilterInput} label="To" type="date" value=${filters.date_to} onChange=${(v) => setFilters({ ...filters, date_to: v })} />
          <${FilterSelect} label="Site" value=${filters.site} values=${sites} onChange=${(v) => setFilters({ ...filters, site: v })} />
          <${FilterSelect} label="Department" value=${filters.department || ""} values=${departments} onChange=${(v) => setFilters({ ...filters, department: v })} />
          <${FilterSelect} label="Activity" value=${filters.activity || ""} values=${activities} onChange=${(v) => setFilters({ ...filters, activity: v })} />
          <${FilterSelect} label="Risk" value=${filters.risk_level} values=${["low", "medium", "high", "critical"]} onChange=${(v) => setFilters({ ...filters, risk_level: v })} />
          <${FilterSelect} label="Precursor" value=${filters.precursor} values=${precursors} onChange=${(v) => setFilters({ ...filters, precursor: v })} />
          <${FilterSelect} label="Cluster" value=${filters.cluster_id} values=${clusters} format=${(v) => `C-${Number(v) + 1}`} onChange=${(v) => setFilters({ ...filters, cluster_id: v })} />
          <button className="secondary-button self-end" onClick=${() => { setFilters({ date_from: "", date_to: "", site: "", department: "", activity: "", risk_level: "", precursor: "", cluster_id: "" }); }}>Clear</button>
        </div>
        <${TrendVisuals} trends=${trends} />
      </section>

      <section className="panel"><p className="eyebrow">SITE RISK METRICS</p><h2 className="mt-2 text-xl font-semibold">Volume is shown separately from risk concentration</h2>
        <div className="mt-4 overflow-x-auto"><table className="data-table"><thead><tr><th>Site</th><th>Report volume</th><th>High/Critical</th><th>High/Critical %</th><th>Average SIF</th></tr></thead><tbody>${(metrics.site_metrics || []).map((row) => html`<tr key=${row.site}><td className="font-semibold">${row.site}</td><td>${row.report_volume}</td><td>${row.high_critical_count}</td><td>${row.high_critical_percentage}%</td><td>${row.average_sif_score}</td></tr>`)}</tbody></table></div>
        <p className="mt-3 text-xs text-slate-500">No worker-hour denominator is available, so SAJAG does not present these values as an incident rate.</p>
      </section>
      <section className="panel"><p className="eyebrow">CRITICAL CONTROL HEALTH</p><div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between"><h2 className="mt-2 text-xl font-semibold">Observation-based control condition</h2><p className="text-xs text-slate-500">Most deteriorating: <b>${metrics.most_deteriorating_critical_control}</b></p></div><div className="mt-4 overflow-x-auto"><table className="data-table"><thead><tr><th>Critical control</th><th>Observations</th><th>Effective</th><th>Degraded</th><th>Missing</th><th>Failed/bypassed</th><th>Unknown</th><th>Ineffective/degraded</th><th>High/Critical</th><th>Trend</th><th>Affected sites</th></tr></thead><tbody>${controls.slice(0, 12).map((row) => html`<tr key=${row.critical_control}><td className="font-semibold">${row.critical_control}</td><td>${row.total_observations}</td><td>${row.effective_intact_count}</td><td>${row.degraded_count}</td><td>${row.missing_count}</td><td>${row.failed_bypassed_count}</td><td>${row.unknown_count}</td><td>${row.ineffective_or_degraded_percentage}%</td><td>${row.high_critical_reports}</td><td className="capitalize">${row.trend}</td><td>${row.sites_affected.join(", ")}</td></tr>`)}</tbody></table></div><p className="mt-3 text-xs text-slate-500">Percentage denominator: analysed observations mentioning each control. Worker-hours are unavailable, so this is not presented as an operational failure rate.</p></section>
    </div>
  `;
}

function TrendVisuals({ trends }) {
  if (!trends) return html`<p className="mt-6 text-sm text-slate-500">Loading chart data…</p>`;
  const series = trends.series || [];
  const maxReports = Math.max(1, ...series.map((p) => p.reports));
  return html`<div className="mt-7 grid gap-6 xl:grid-cols-[1.4fr_0.6fr]">
    <div><h3 className="text-sm font-semibold">Reports and High/Critical observations over time</h3>
      ${series.length ? html`<div className="mt-4 flex h-56 items-end gap-2 overflow-x-auto border-b border-slate-200 px-2">${series.map((point) => html`<div key=${point.period} className="flex min-w-20 flex-1 flex-col items-center justify-end gap-1"><span className="text-[10px] font-semibold">${point.reports}</span><div className="flex w-full items-end justify-center gap-1"><div title="All reports" className="w-3 rounded-t bg-cyan-400" style=${{ height: `${Math.max(3, point.reports / maxReports * 160)}px` }}></div><div title="High/Critical" className="w-3 rounded-t bg-rose-500" style=${{ height: `${Math.max(2, point.high_critical / maxReports * 160)}px` }}></div><div title="Precursor frequency" className="w-3 rounded-t bg-violet-500" style=${{ height: `${Math.max(2, point.top_precursor_count / maxReports * 160)}px` }}></div><div title="Critical-control failures" className="w-3 rounded-t bg-amber-500" style=${{ height: `${Math.max(2, point.critical_control_failures / maxReports * 160)}px` }}></div></div><span className="pb-2 text-[10px] text-slate-500">${point.period}</span></div>`)}</div>` : html`<p className="mt-4 text-sm text-slate-500">No dated analysed reports match the filters.</p>`}
      <div className="mt-3 flex flex-wrap gap-4 text-xs text-slate-500"><span>■ <b className="text-cyan-500">All reports</b></span><span>■ <b className="text-rose-500">High/Critical</b></span><span>■ <b className="text-violet-500">Precursor frequency</b></span><span>■ <b className="text-amber-500">Control failures</b></span></div>
    </div>
    <div className="space-y-5"><${FrequencyBars} title="Precursor frequency" rows=${trends.precursor_frequency} /><${FrequencyBars} title="Critical-control failures" rows=${trends.critical_control_failures} /></div>
  </div>`;
}

function FrequencyBars({ title, rows = [] }) {
  const shown = rows.slice(0, 5); const max = Math.max(1, ...shown.map((r) => r.count));
  return html`<div><h3 className="text-sm font-semibold">${title}</h3><div className="mt-3 space-y-2">${shown.map((row) => html`<div key=${row.name}><div className="flex justify-between gap-3 text-xs"><span className="truncate">${row.name}</span><b>${row.count}</b></div><div className="mt-1 h-1.5 rounded bg-slate-100"><div className="h-full rounded bg-slate-800" style=${{ width: `${row.count / max * 100}%` }}></div></div></div>`)}</div></div>`;
}

function FilterInput({ label, type = "text", value, onChange }) { return html`<label><span className="filter-label">${label}</span><input className="filter-control" type=${type} value=${value} onChange=${(e) => onChange(e.target.value)} /></label>`; }
function FilterSelect({ label, value, values, onChange, format = (v) => v }) { return html`<label><span className="filter-label">${label}</span><select className="filter-control" value=${value} onChange=${(e) => onChange(e.target.value)}><option value="">All</option>${values.map((v) => html`<option key=${v} value=${v}>${format(v)}</option>`)}</select></label>`; }
function unique(values) { return [...new Set(values.filter((v) => v !== "" && v !== null && v !== undefined))].sort(); }
