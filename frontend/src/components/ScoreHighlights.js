import { html } from "../ui.js";

function getRiskStyles(level) {
  const normalized = String(level || "").toLowerCase();

  if (normalized === "critical") {
    return {
      badge: "border-rose-200 bg-rose-50 text-rose-700",
      meter: "from-rose-500 via-rose-400 to-orange-300",
    };
  }

  if (normalized === "high") {
    return {
      badge: "border-red-200 bg-red-50 text-red-700",
      meter: "from-red-500 via-orange-400 to-amber-300",
    };
  }

  if (normalized === "medium") {
    return {
      badge: "border-amber-200 bg-amber-50 text-amber-700",
      meter: "from-amber-500 via-yellow-400 to-lime-300",
    };
  }

  return {
    badge: "border-emerald-200 bg-emerald-50 text-emerald-700",
    meter: "from-emerald-500 via-emerald-400 to-cyan-300",
  };
}

export function ScoreHighlights({ sifScore, riskLevel }) {
  const roundedScore = Math.round(Number(sifScore) || 0);
  const progress = Math.max(0, Math.min(100, roundedScore));
  const styles = getRiskStyles(riskLevel);

  return html`
    <section className="rounded-[1.9rem] border border-cyan-100 bg-cyan-50/60 p-6 shadow-sm">
      <div className="flex flex-col gap-6 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.25em] text-cyan-700">
            SIF PRIORITY SCORE
          </p>

          <div className="mt-4 flex items-end gap-3">
            <span className="text-6xl font-bold tracking-tight text-slate-900">
              ${roundedScore}
            </span>
            <span className="pb-2 text-xl font-semibold text-slate-500">
              / 100
            </span>
          </div>

          <div className=${`mt-4 inline-flex rounded-full border px-4 py-2 text-sm font-bold uppercase ${styles.badge}`}>
            ${riskLevel || "Unknown"}
          </div>
        </div>

        <div className="flex items-center gap-6">
          <div className="relative flex h-44 w-44 items-center justify-center rounded-full bg-white ring-8 ring-cyan-100">
            <div
              className=${`absolute inset-0 rounded-full bg-gradient-to-br ${styles.meter}`}
              style=${{
                clipPath: `inset(${100 - progress}% 0 0 0 round 9999px)`,
                opacity: 0.9,
              }}
            ></div>

            <div className="absolute inset-[14px] rounded-full bg-white"></div>

            <div className="relative text-center">
              <p className="text-4xl font-bold text-slate-900">${roundedScore}</p>
              <p className="text-sm font-semibold text-slate-500">Priority</p>
            </div>
          </div>

          <div className="hidden w-56 lg:block">
            <div className="h-4 overflow-hidden rounded-full bg-white">
              <div
                className=${`h-full rounded-full bg-gradient-to-r ${styles.meter}`}
                style=${{ width: `${progress}%` }}
              ></div>
            </div>

            <p className="mt-3 text-sm leading-6 text-slate-600">
              Higher scores mean the observation needs faster HSE attention.
            </p>
          </div>
        </div>
      </div>
    </section>
  `;
}
