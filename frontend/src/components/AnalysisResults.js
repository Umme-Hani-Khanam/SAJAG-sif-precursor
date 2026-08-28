import React from "react";
import { html } from "../ui.js";
import { SectionErrorBoundary } from "./SectionErrorBoundary.js";
import { ScoreHighlights } from "./ScoreHighlights.js";
import { ResultCard } from "./ResultCard.js";
import { SimilarReportsSection } from "./SimilarReportsSection.js";

export function AnalysisResults({ result }) {
  const breakdown = result.score_breakdown || {};

  return React.createElement(
    "div",
    { className: "space-y-6" },

    React.createElement(
      SectionErrorBoundary,
      { fallbackMessage: "Score section is unavailable." },
      React.createElement(ScoreHighlights, {
        sifScore: result.sif_score,
        riskLevel: result.risk_level,
      }),
    ),

    html`
      <section>
        <div className="mb-4">
          <p className="text-xs font-semibold uppercase tracking-[0.25em] text-cyan-600">
            SAFETY INTELLIGENCE
          </p>

          <h3 className="mt-1 text-xl font-semibold text-slate-900">
            Detected Safety Factors
          </h3>
        </div>

        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          <${ResultCard}
            title="Precursor Pattern"
            value=${result.precursor_pattern}
          />

          <${ResultCard}
            title="Hazard"
            value=${result.hazard}
          />

          <${ResultCard}
            title="Energy Source"
            value=${result.energy_source}
          />

          <${ResultCard}
            title="Exposure Type"
            value=${result.exposure_type}
          />

          <${ResultCard}
            title="Unsafe Act"
            value=${result.unsafe_act}
          />

          <${ResultCard}
            title="Unsafe Condition"
            value=${result.unsafe_condition}
          />

          <${ResultCard}
            title="Critical Control"
            value=${result.critical_control}
          />

          <${ResultCard}
            title="Control Status"
            value=${result.control_status}
          />

          <${ResultCard}
            title="Potential Consequence"
            value=${result.potential_consequence}
          />

          <${ResultCard}
            title="Likelihood"
            value=${result.likelihood}
          />

          <${ResultCard}
            title="Site"
            value=${result.site}
          />

          <${ResultCard}
            title="Activity"
            value=${result.activity}
          />
        </div>
      </section>
    `,

    html`
      <section className="grid gap-5 lg:grid-cols-2">

        <article className="rounded-[1.75rem] border border-cyan-100 bg-cyan-50/50 p-5">
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-cyan-700">
            LIFE-SAVING RULE
          </p>

          <p className="mt-3 text-base font-medium leading-7 text-slate-800">
            ${result.life_saving_rule || "Not available"}
          </p>
        </article>


        <article className="rounded-[1.75rem] border border-slate-200 bg-slate-50 p-5">
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-500">
            WHY THIS SCORE?
          </p>

          <div className="mt-4 space-y-3">

            <ScoreRow
              label="Potential Consequence"
              value=${breakdown.potential_consequence}
            />

            <ScoreRow
              label="Hazardous Energy Exposure"
              value=${breakdown.hazardous_energy_exposure}
            />

            <ScoreRow
              label="Critical Control Failure"
              value=${breakdown.critical_control_failure}
            />

            <ScoreRow
              label="Likelihood"
              value=${breakdown.likelihood}
            />

            <ScoreRow
              label="Historical Recurrence"
              value=${breakdown.historical_recurrence}
            />

            <div className="border-t border-slate-200 pt-3">
              <ScoreRow
                label="Total"
                value=${breakdown.total}
                strong=${true}
              />
            </div>

          </div>
        </article>

      </section>
    `,

    React.createElement(
      SectionErrorBoundary,
      { fallbackMessage: "Similar historical reports are unavailable." },
      React.createElement(SimilarReportsSection, {
        reports: result.similar_reports,
      }),
    ),
  );
}

function ScoreRow({ label, value, strong = false }) {
  return html`
    <div className="flex items-center justify-between gap-4">
      <span className=${strong
        ? "text-sm font-semibold text-slate-900"
        : "text-sm text-slate-600"}>
        ${label}
      </span>

      <span className=${strong
        ? "text-sm font-bold text-slate-900"
        : "text-sm font-semibold text-slate-800"}>
        ${value ?? 0}
      </span>
    </div>
  `;
}