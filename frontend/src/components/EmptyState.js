import { html } from "../ui.js";

export function EmptyState() {
  return html`
    <section className="rounded-[2rem] border border-dashed border-slate-200 bg-slate-50 p-8 text-center">
      <h2 className="text-xl font-semibold text-slate-900">Awaiting Analysis</h2>
      <p className="mt-2 text-sm leading-6 text-slate-500">
        Submit a safety observation or upload a PDF report to view the SIF
        priority score, score rationale, precursor pattern, and historical evidence.
      </p>
    </section>
  `;
}
