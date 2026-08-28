import { html } from "../ui.js";

export function SimilarReportsSection({
  reports,
  precursorPattern,
  historicalReportCount = 0,
}) {
  const hasReports = Array.isArray(reports) && reports.length > 0;
  const historyLoaded = Number(historicalReportCount) > 0;

  return html`
    <section className="rounded-[1.75rem] border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-cyan-600">
            HISTORICAL EVIDENCE
          </p>

          <h3 className="mt-2 text-xl font-semibold text-slate-900">
            Similar historical reports
          </h3>

          <p className="mt-1 text-sm text-slate-500">
            ${hasReports
              ? `${historicalReportCount} historical reports loaded. Pattern focus: ${precursorPattern}.`
              : historyLoaded
                ? "Historical records are loaded, but no close matches were returned for this observation."
                : "No historical reports have been loaded yet."}
          </p>
        </div>

        ${hasReports
          ? html`
              <span className="rounded-full border border-cyan-100 bg-cyan-50 px-3 py-1 text-xs font-semibold text-cyan-700">
                ${reports.length} related observation${reports.length === 1 ? "" : "s"} found
              </span>
            `
          : null}
      </div>

      ${hasReports
        ? html`
            <div className="mt-5 space-y-3">
              ${reports.map((report) => html`
                <article
                  key=${report.report_id}
                  className="rounded-2xl border border-slate-200 bg-slate-50 p-4"
                >
                  <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                    <div className="space-y-2">
                      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-cyan-600">
                        ${report.report_id}
                      </p>

                      <div className="flex flex-wrap gap-2 text-xs text-slate-500">
                        <span className="rounded-full bg-white px-3 py-1">
                          ${report.date || "Date not available"}
                        </span>
                        <span className="rounded-full bg-white px-3 py-1">
                          ${report.site || "Site not available"}
                        </span>
                        <span className="rounded-full bg-white px-3 py-1">
                          ${report.activity || "Activity not available"}
                        </span>
                      </div>

                      <p className="text-sm leading-6 text-slate-700">
                        ${report.description || "No description available."}
                      </p>
                    </div>

                    <div className="shrink-0 rounded-full border border-cyan-200 bg-white px-3 py-1 text-xs font-semibold text-cyan-700">
                      ${(Number(report.similarity) * 100).toFixed(1)}% similar
                    </div>
                  </div>
                </article>
              `)}
            </div>
          `
        : html`
            <div className="mt-5 rounded-2xl border border-dashed border-slate-200 bg-slate-50 px-5 py-8 text-center">
              <p className="text-sm text-slate-500">
                ${historyLoaded
                  ? "No close historical matches found for this observation."
                  : "No historical reports have been loaded yet."}
              </p>
            </div>
          `}
    </section>
  `;
}
