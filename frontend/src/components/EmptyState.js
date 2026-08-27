import { html } from "../ui.js";

export function EmptyState() {
  return html`
    <section className="rounded-[2rem] border border-dashed border-white/15 bg-white/[0.03] p-8 text-center">
      <h2 className="text-xl font-semibold text-white">Awaiting Analysis</h2>
      <p className="mt-2 text-sm leading-6 text-slate-300">
        Submit a safety observation to view the SIF score, detected precursor
        pattern, and supporting result panels.
      </p>
    </section>
  `;
}
