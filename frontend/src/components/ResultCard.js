import { html } from "../ui.js";

export function ResultCard({ title, value }) {
  return html`
    <article className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm transition hover:-translate-y-0.5 hover:shadow-md">

      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-cyan-600">
        ${title}
      </p>

      <p className="mt-3 text-sm leading-6 text-slate-700">
        ${value || "Not available"}
      </p>

    </article>
  `;
}