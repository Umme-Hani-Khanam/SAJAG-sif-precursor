import { html } from "../ui.js";

function getRiskStyles(level) {
  const normalized = String(level || "").toLowerCase();

  if (normalized === "high") {
    return "border-red-200 bg-red-50 text-red-700";
  }

  if (normalized === "medium") {
    return "border-amber-200 bg-amber-50 text-amber-700";
  }

  return "border-emerald-200 bg-emerald-50 text-emerald-700";
}

export function ScoreHighlights({ sifScore, riskLevel }) {
  return html`
    <section className="grid gap-4 lg:grid-cols-[1.2fr_0.8fr]">

      <article className="rounded-[1.75rem] border border-cyan-100 bg-cyan-50/50 p-6">

        <p className="text-xs font-semibold uppercase tracking-[0.25em] text-cyan-700">
          SIF SCORE
        </p>

        <div className="mt-3 flex items-end gap-3">
          <span className="text-6xl font-bold text-slate-900">
            ${Math.round(Number(sifScore) || 0)}
          </span>

          <span className="pb-2 text-lg text-slate-500">
            /100
          </span>
        </div>

        <p className="mt-2 text-sm text-slate-500">
          Serious Injury and Fatality precursor risk score
        </p>

      </article>


      <article
        className=${`rounded-[1.75rem] border p-6 ${getRiskStyles(
          riskLevel,
        )}`}
      >

        <p className="text-xs font-semibold uppercase tracking-[0.25em]">
          RISK LEVEL
        </p>

        <p className="mt-4 text-4xl font-bold capitalize">
          ${riskLevel || "Unknown"}
        </p>

        <p className="mt-2 text-sm opacity-80">
          Based on the current safety observation
        </p>

      </article>

    </section>
  `;
}