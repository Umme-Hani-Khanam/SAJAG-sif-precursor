import { html } from "../ui.js";

export function ResultCard({ title, value }) {
  return html`
    <article className="rounded-[1.75rem] border border-white/10 bg-white/5 p-5 backdrop-blur">
      <p className="text-sm font-medium uppercase tracking-[0.22em] text-slate-400">
        ${title}
      </p>
      <p className="mt-3 text-sm leading-6 text-slate-100">
        ${value || "Not available"}
      </p>
    </article>
  `;
}
