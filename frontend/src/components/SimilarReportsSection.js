import { html } from "../ui.js";

export function SimilarReportsSection({ reports }) {
  const hasReports = Array.isArray(reports) && reports.length > 0;

  return html`
    <section className="rounded-[1.75rem] border border-white/10 bg-white/5 p-5 shadow-panel">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h3 className="text-lg font-semibold text-white">Similar Historical Reports</h3>
          <p className="mt-1 text-sm text-slate-400">
            Top related observations returned by the current backend.
          </p>
        </div>
      </div>

      ${hasReports
        ? html`
            <div className="mt-4 space-y-3">
              ${reports.map(
                (report) => html`
                  <article
                    key=${report.report_id}
                    className="rounded-2xl border border-white/10 bg-slatebase/60 p-4"
                  >
                    <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                      <div>
                        <p className="text-sm font-semibold text-white">${report.report_id}</p>
                        <p className="mt-2 text-sm leading-6 text-slate-300">
                          ${report.description || "No description available."}
                        </p>
                      </div>
                      <div className="shrink-0 rounded-full border border-cyanaccent/25 bg-cyanaccent/10 px-3 py-1 text-xs font-medium text-cyanaccent">
                        Similarity ${(Number(report.similarity) * 100).toFixed(1)}%
                      </div>
                    </div>
                  </article>
                `,
              )}
            </div>
          `
        : html`
            <p className="mt-4 text-sm text-slate-300">
              No similar historical reports available.
            </p>
          `}
    </section>
  `;
}
