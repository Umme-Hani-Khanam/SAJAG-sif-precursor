import { html } from "../ui.js";

export function SimilarReportsSection({ reports }) {
  const hasReports = Array.isArray(reports) && reports.length > 0;

  return html`
    <section className="rounded-[1.75rem] border border-white/10 bg-white/[0.035] p-5 shadow-panel">

      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex items-center gap-3">
            <div className="h-2 w-2 rounded-full bg-cyanaccent"></div>

            <h3 className="text-lg font-semibold text-white">
              Similar Historical Reports
            </h3>
          </div>

          <p className="mt-1 text-sm text-slate-400">
            Related observations identified by the backend.
          </p>
        </div>

        ${hasReports
          ? html`
              <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-slate-400">
                ${reports.length} match${reports.length === 1 ? "" : "es"}
              </span>
            `
          : null}
      </div>

      ${hasReports
        ? html`
            <div className="mt-5 space-y-3">
              ${reports.map(
                (report) => html`
                  <article
                    key=${report.report_id}
                    className="rounded-2xl border border-white/10 bg-slatebase/60 p-4 transition hover:border-cyanaccent/20"
                  >
                    <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">

                      <div>
                        <p className="text-xs font-semibold uppercase tracking-wider text-cyanaccent">
                          ${report.report_id}
                        </p>

                        <p className="mt-2 text-sm leading-6 text-slate-300">
                          ${report.description || "No description available."}
                        </p>
                      </div>

                      <div className="shrink-0 rounded-full border border-cyanaccent/20 bg-cyanaccent/10 px-3 py-1 text-xs font-semibold text-cyanaccent">
                        ${(Number(report.similarity) * 100).toFixed(1)}% similar
                      </div>

                    </div>
                  </article>
                `,
              )}
            </div>
          `
        : html`
            <div className="mt-5 rounded-2xl border border-dashed border-white/10 bg-black/10 px-5 py-8 text-center">
              <p className="text-sm text-slate-400">
                No similar historical reports available.
              </p>
            </div>
          `}
    </section>
  `;
}