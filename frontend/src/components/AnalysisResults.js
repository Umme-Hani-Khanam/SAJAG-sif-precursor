import React from "react";
import { html } from "../ui.js";
import { SectionErrorBoundary } from "./SectionErrorBoundary.js";
import { ScoreHighlights } from "./ScoreHighlights.js";
import { ResultCard } from "./ResultCard.js";
import { SimilarReportsSection } from "./SimilarReportsSection.js";

const BREAKDOWN_ITEMS = [
  ["Potential consequence", "potential_consequence", 30],
  ["Hazardous energy/exposure", "hazardous_energy_exposure", 25],
  ["Critical-control failure", "critical_control_failure", 25],
  ["Likelihood/exposure", "likelihood", 10],
  ["Historical recurrence", "historical_recurrence", 10],
];

export function AnalysisResults({ result, historicalReportCount = 0 }) {
  const breakdown = result.score_breakdown || {};
  const precursorName = compactText(result.precursor_pattern, "Precursor not identified");
  const explanation = buildShortExplanation(result);
  const actionNow = buildActionNow(result);
  const ruleSentence = buildRuleSentence(result);
  const ruleTitle = compactText(result.life_saving_rule, "Life-saving rule");
  const detailItems = buildDetailItems(result);

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
      <section className="grid gap-5 xl:grid-cols-[0.95fr_1.05fr]">
        <article className="rounded-[1.75rem] border border-slate-200 bg-white p-6 shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-[0.25em] text-cyan-600">
            DETECTED PRECURSOR
          </p>

          <h3 className="mt-3 text-3xl font-bold tracking-tight text-slate-900">
            ${precursorName}
          </h3>

          <p className="mt-4 text-base leading-7 text-slate-600">
            ${explanation}
          </p>
        </article>

        <article className="rounded-[1.75rem] border border-slate-200 bg-white p-6 shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-[0.25em] text-cyan-600">
            WHY IS IT RISKY?
          </p>

          <div className="mt-4 space-y-3">
            ${buildRiskItems(result).map((item) => html`
              <div className="rounded-2xl bg-slate-50 px-4 py-3">
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                  ${item.label}
                </p>
                <p className="mt-1 text-sm leading-6 text-slate-700">
                  ${item.value}
                </p>
              </div>
            `)}
          </div>
        </article>
      </section>
    `,

    html`
      <section className="grid gap-5 lg:grid-cols-2">
        <article className="rounded-[1.75rem] border border-cyan-100 bg-cyan-50/60 p-6 shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-cyan-700">
            LIFE-SAVING RULE
          </p>

          <h3 className="mt-3 text-xl font-bold text-slate-900">
            ${ruleTitle}
          </h3>

          <p className="mt-2 text-sm leading-6 text-slate-700">
            ${ruleSentence}
          </p>
        </article>

        <article className="rounded-[1.75rem] border border-slate-200 bg-white p-6 shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-500">
            ACTION NOW
          </p>

          <p className="mt-3 text-base font-medium leading-7 text-slate-800">
            ${actionNow}
          </p>
        </article>
      </section>
    `,

    html`
      <details className="rounded-[1.75rem] border border-slate-200 bg-slate-50 p-5">
        <summary className="flex cursor-pointer list-none items-center justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-500">
              WHY THIS SCORE?
            </p>
            <h3 className="mt-2 text-lg font-semibold text-slate-900">
              View score breakdown
            </h3>
          </div>

          <span className="rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-semibold text-slate-600">
            Expand
          </span>
        </summary>

        <div className="mt-5 space-y-4">
          ${BREAKDOWN_ITEMS.map(([label, key, max]) =>
            React.createElement(ScoreRow, {
              key,
              label,
              value: breakdown[key],
              max,
            }),
          )}

          <div className="border-t border-slate-200 pt-4">
            <ScoreRow
              label="TOTAL"
              value=${breakdown.total}
              max=${100}
              strong=${true}
            />
          </div>
        </div>
      </details>
    `,

    React.createElement(
      SectionErrorBoundary,
      { fallbackMessage: "Historical evidence is unavailable." },
      React.createElement(SimilarReportsSection, {
        reports: result.similar_reports,
        precursorPattern: precursorName,
        historicalReportCount,
      }),
    ),

    html`
      <details className="rounded-[1.75rem] border border-slate-200 bg-white p-5 shadow-sm">
        <summary className="flex cursor-pointer list-none items-center justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-500">
              VIEW DETAILED ANALYSIS
            </p>
            <h3 className="mt-2 text-lg font-semibold text-slate-900">
              Technical fields
            </h3>
          </div>

          <span className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs font-semibold text-slate-600">
            Expand
          </span>
        </summary>

        <div className="mt-5 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          ${detailItems.map((item) => html`
            <${ResultCard}
              key=${item.title}
              title=${item.title}
              value=${item.value}
            />
          `)}
        </div>
      </details>
    `,
  );
}

function buildRiskItems(result) {
  return [
    {
      label: "Critical control failure",
      value: compactSentence(
        result.critical_control
          ? `${compactText(result.critical_control)} was not fully effective.`
          : "A critical control was not fully effective.",
      ),
    },
    {
      label: "Worker / hazard exposure",
      value: compactSentence(
        result.unsafe_condition || result.hazard || "The worker remained exposed to the hazard.",
      ),
    },
    {
      label: "Likelihood / consequence",
      value: compactSentence(
        buildConsequenceSentence(result),
      ),
    },
  ];
}

function buildShortExplanation(result) {
  const unsafeAct = compactText(result.unsafe_act);
  const unsafeCondition = compactText(result.unsafe_condition || result.hazard);

  if (unsafeAct && unsafeCondition) {
    return compactSentence(`${unsafeAct} while ${unsafeCondition.toLowerCase()}.`);
  }

  if (unsafeCondition) {
    return compactSentence(unsafeCondition);
  }

  return "SAJAG detected a potentially unsafe work situation.";
}

function buildConsequenceSentence(result) {
  const likelihood = compactText(result.likelihood).toLowerCase();
  const consequence = compactText(result.potential_consequence);

  if (likelihood && consequence) {
    return `The event could lead to ${consequence.toLowerCase()} and the chance of exposure is ${likelihood}.`;
  }

  if (consequence) {
    return `The event could lead to ${consequence.toLowerCase()}.`;
  }

  if (likelihood) {
    return `The chance of exposure is ${likelihood}.`;
  }

  return "The observation shows a credible chance of harm if work continues.";
}

function buildActionNow(result) {
  if (result.critical_control) {
    return compactSentence(`Stop work and verify ${compactText(result.critical_control).toLowerCase()} before continuing.`);
  }

  if (result.life_saving_rule) {
    return compactSentence(result.life_saving_rule);
  }

  if (result.unsafe_condition) {
    return compactSentence(`Stop work and address this condition: ${result.unsafe_condition}`);
  }

  return "Stop work, verify controls, and make the area safe before continuing.";
}

function buildRuleSentence(result) {
  if (result.life_saving_rule) {
    return compactSentence(result.life_saving_rule);
  }

  if (result.critical_control) {
    return compactSentence(`Make sure ${compactText(result.critical_control).toLowerCase()} is in place before work starts.`);
  }

  return "Make sure the key protection is in place before work starts.";
}

function buildDetailItems(result) {
  return [
    { title: "Hazard", value: result.hazard || "Not available from report" },
    { title: "Energy Source", value: result.energy_source || "Not available from report" },
    { title: "Exposure Type", value: result.exposure_type || "Not available from report" },
    { title: "Unsafe Act", value: result.unsafe_act || "Not available from report" },
    { title: "Unsafe Condition", value: result.unsafe_condition || "Not available from report" },
    { title: "Critical Control", value: result.critical_control || "Not available from report" },
    { title: "Control Status", value: result.control_status || "Not available from report" },
    { title: "Potential Consequence", value: result.potential_consequence || "Not available from report" },
    { title: "Likelihood", value: result.likelihood || "Not available from report" },
    { title: "Site", value: result.site || "Not available from report" },
    { title: "Activity", value: result.activity || "Not available from report" },
  ];
}

function compactText(value, fallback = "") {
  return String(value || fallback).replace(/\s+/g, " ").trim();
}

function compactSentence(value) {
  const text = compactText(value);
  if (!text) {
    return "";
  }

  const withoutTrailing = text.replace(/[.?!]+$/, "");
  return `${withoutTrailing}.`;
}

function ScoreRow({ label, value, max, strong = false }) {
  const numericValue = Number(value) || 0;
  const progress = Math.max(0, Math.min(100, (numericValue / max) * 100));

  return html`
    <div className="space-y-2">
      <div className="flex items-center justify-between gap-4">
        <span className=${strong
          ? "text-sm font-semibold text-slate-900"
          : "text-sm text-slate-600"}>
          ${label}
        </span>

        <span className=${strong
          ? "text-sm font-bold text-slate-900"
          : "text-sm font-semibold text-slate-800"}>
          ${numericValue} / ${max}
        </span>
      </div>

      <div className="h-2 overflow-hidden rounded-full bg-slate-200">
        <div
          className=${strong ? "h-full rounded-full bg-slate-900" : "h-full rounded-full bg-cyan-500"}
          style=${{ width: `${progress}%` }}
        ></div>
      </div>
    </div>
  `;
}
