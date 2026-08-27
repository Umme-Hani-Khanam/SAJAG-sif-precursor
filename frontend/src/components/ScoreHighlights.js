import { html } from "../ui.js";

function getRiskStyles(level) {
  const normalized = String(level).toLowerCase();

  if (normalized === "high") {
    return "border-red-400/30 bg-red-500/15 text-red-100";
  }

  if (normalized === "medium") {
    return "border-amberaccent/30 bg-amberaccent/15 text-amber-100";
  }

  return "border-mintaccent/30 bg-mintaccent/15 text-emerald-100";
}

export function ScoreHighlights({ sifScore, riskLevel }) {
  return html`
    <section className="grid gap-4 lg:grid-cols-[1.2fr_0.8fr]">
      <article className="rounded-[2rem] border border-cyanaccent/20 bg-gradient-to-br from-cyanaccent/20 to-white/5 p-6 shadow-panel">
        <p className="text-sm uppercase tracking-[0.25em] text-cyan-100/80">
          SIF Score
        </p>
        <div className="mt-4 flex items-end gap-3">
          <span className="text-6xl font-semibold text-white">
            ${Math.round(Number(sifScore) || 0)}
          </span>
          <span className="pb-2 text-lg text-cyan-100">/100</span>
        </div>
      </article>

      <article className=${`rounded-[2rem] border p-6 shadow-panel ${getRiskStyles(riskLevel)}`}>
        <p className="text-sm uppercase tracking-[0.25em]">Risk Level</p>
        <p className="mt-5 text-4xl font-semibold capitalize">${riskLevel || "Unknown"}</p>
      </article>
    </section>
  `;
}
