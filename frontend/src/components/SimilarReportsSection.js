import { html } from "../ui.js";

export function SimilarReportsSection({ reports, precursorPattern, historicalReportCount = 0 }) {
  const rows = Array.isArray(reports) ? reports : [];
  return html`
    <section className="rounded-[1.75rem] border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div><p className="eyebrow">HISTORICAL EVIDENCE</p><h3 className="mt-2 text-xl font-semibold">Explainable related reports</h3>
          <p className="mt-1 text-sm text-slate-500">${historicalReportCount} analysed reports · Pattern focus: ${precursorPattern}.</p></div>
        ${rows.length ? html`<span className="status-pill">${rows.length} distinct matches</span>` : null}
      </div>
      ${rows.length ? html`
        <div className="mt-5 space-y-4">
          ${rows.map((report) => html`
            <article key=${report.report_id} className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
              <div className="flex flex-col gap-4 lg:flex-row lg:justify-between">
                <div className="min-w-0 flex-1">
                  <p className="text-xs font-bold uppercase tracking-[0.18em] text-cyan-700">REPORT ${report.report_id}</p>
                  <div className="mt-2 flex flex-wrap gap-2 text-xs text-slate-500">
                    <span className="meta-pill">${report.date || "Date unavailable"}</span><span className="meta-pill">${report.site || "Site unavailable"}</span><span className="meta-pill">${report.activity || "Activity unavailable"}</span>
                  </div>
                  <p className="mt-3 text-sm leading-6 text-slate-700">${report.description}</p>
                  <div className="mt-4 rounded-xl bg-white p-3">
                    <p className="text-xs font-bold uppercase tracking-[0.16em] text-slate-500">Why flagged</p>
                    <ul className="mt-2 space-y-1 text-sm text-slate-700">
                      ${(report.match_reasons || []).map((reason) => html`<li key=${reason}>✓ ${reason}</li>`)}
                    </ul>
                  </div>
                </div>
                <div className="shrink-0 lg:w-44">
                  <div className="rounded-2xl border border-cyan-200 bg-white p-4 text-center">
                    <p className="text-3xl font-bold text-slate-900">${Number(report.overall_match_percent).toFixed(1)}%</p><p className="text-xs font-semibold text-cyan-700">related overall</p>
                  </div>
                  <div className="mt-2 grid grid-cols-2 gap-1 text-[10px] text-slate-500">
                    <span>Semantic ${report.semantic_similarity}%</span><span>Hazard ${report.hazard_match}%</span>
                    <span>Exposure ${report.exposure_match}%</span><span>Control ${report.critical_control_match}%</span>
                  </div>
                </div>
              </div>
            </article>
          `)}
        </div>` : html`<div className="mt-5 rounded-2xl border border-dashed border-slate-200 bg-slate-50 p-7 text-center text-sm text-slate-500">${historicalReportCount ? "No analysed evidence met the configured threshold." : "Analyse the historical dataset to enable evidence matching."}</div>`}
    </section>
  `;
}
