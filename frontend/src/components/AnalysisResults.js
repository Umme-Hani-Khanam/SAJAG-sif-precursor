import React from "react";
import { html } from "../ui.js";
import { SectionErrorBoundary } from "./SectionErrorBoundary.js";
import { ScoreHighlights } from "./ScoreHighlights.js";
import { ResultCard } from "./ResultCard.js";
import { SimilarReportsSection } from "./SimilarReportsSection.js";
import { submitReview } from "../api/governance.js";

const BREAKDOWN_ITEMS = [
  ["Potential consequence", "potential_consequence", 30],
  ["Hazardous energy/exposure", "hazardous_energy_exposure", 25],
  ["Critical-control failure", "critical_control_failure", 25],
  ["Likelihood/exposure", "likelihood", 10],
  ["Historical recurrence", "historical_recurrence", 10],
];

export function AnalysisResults({ result, historicalReportCount = 0, actor }) {
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

    React.createElement(PatternDecision, { result }),

    React.createElement(EvidenceConfidence, { result }),

    React.createElement(GuidanceAndMemory, { result }),

    result.report_id ? React.createElement(HSEReviewPanel, { result, actor }) : null,

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

function PatternDecision({ result }) {
  const cluster = result.current_cluster;
  const pattern = result.pattern_status || {};
  const trend = result.cluster_trend;
  return html`
    <section className="grid gap-4 lg:grid-cols-2">
      <article className="rounded-[1.75rem] border border-slate-200 bg-slate-50 p-5">
        <p className="eyebrow">PATTERN DECISION</p>
        <h3 className="mt-2 text-lg font-bold text-slate-900">
          ${cluster ? `${cluster.cluster_code} · ${cluster.cluster_name}` : pattern.label || "Unrecognized precursor candidate"}
        </h3>
        <p className="mt-2 text-sm leading-6 text-slate-600">
          ${cluster
            ? `${cluster.assignment_similarity_percent}% semantic fit to the established cluster centroid.`
            : pattern.state === "monitor"
              ? "One isolated event is monitored; SAJAG does not claim an emerging pattern yet."
              : `${pattern.related_unclassified_count || 0} related unclassified reports support this ${String(pattern.state || "candidate").replaceAll("_", " ")}.`}
        </p>
      </article>
      <article className=${`rounded-[1.75rem] border p-5 ${result.emerging_risk ? "border-amber-200 bg-amber-50" : "border-slate-200 bg-white"}`}>
        <p className="eyebrow">TREND EVIDENCE</p>
        ${trend ? html`
          <div className="mt-3 grid grid-cols-3 gap-2 text-center">
            <div><p className="text-2xl font-bold">${trend.last_30_days}</p><p className="text-xs text-slate-500">Current 30d</p></div>
            <div><p className="text-2xl font-bold">${trend.previous_30_days}</p><p className="text-xs text-slate-500">Previous 30d</p></div>
            <div><p className="text-2xl font-bold">${trend.growth_percent === null ? "New" : `${trend.growth_percent}%`}</p><p className="text-xs text-slate-500">Growth</p></div>
          </div>
          <p className="mt-3 text-sm font-semibold ${result.emerging_risk ? "text-amber-800" : "text-slate-700"}">${result.emerging_risk ? "Emerging SIF precursor pattern detected" : "Configured emerging-risk rule not met"}</p>
        ` : html`<p className="mt-3 text-sm text-slate-600">No established cluster trend applies. Stage: ${String(pattern.state || "monitor").replaceAll("_", " ")}.</p>`}
      </article>
    </section>
  `;
}

function GuidanceAndMemory({ result }) {
  const guidance = result.grounded_guidance || { recommended_action: "No approved safety reference was retrieved.", retrieved_sources: [] };
  const recommendation = result.role_recommendation;
  return html`
    <section className="grid gap-5 lg:grid-cols-2">
      <article className="rounded-[1.75rem] border border-cyan-100 bg-cyan-50/60 p-5">
        <p className="eyebrow">GROUNDED SAFETY GUIDANCE</p><h3 className="mt-2 font-bold">Suggested safety action</h3>
        <p className="mt-2 text-sm leading-6 text-slate-700">${guidance.recommended_action}</p>
        ${guidance.retrieved_sources?.length ? html`<div className="mt-4 space-y-2">${guidance.retrieved_sources.map((source) => html`<article className="rounded-xl bg-white p-3" key=${`${source.document_id}-${source.page}-${source.section}`}><p className="text-xs font-bold text-cyan-700">${source.document_title}</p><p className="mt-1 text-xs text-slate-500">${source.organization} · v${source.version || "unspecified"} · ${source.status} · effective ${source.effective_date || "unspecified"}</p><p className="mt-1 text-xs text-slate-500">${source.section || "Section unavailable"}${source.page ? ` · Page ${source.page}` : ""} · ${source.retrieval_score}% retrieval</p><p className="mt-2 text-xs leading-5 text-slate-600">${source.relevant_snippet}</p><p className="mt-1 text-[10px] text-slate-400">Reference: ${source.source_reference || source.document_id}</p></article>`)}</div>` : html`<p className="mt-3 text-xs text-slate-500">No citation is shown because no approved, temporally eligible source was retrieved. ${guidance.temporal_note || ""}</p>`}
      </article>
      <article className="rounded-[1.75rem] border border-slate-200 bg-white p-5">
        <p className="eyebrow">ROLE-AWARE PRESENTATION</p><p className="mt-2 text-xs font-bold text-slate-500">Safety facts remain unchanged</p>
        <p className="mt-2 text-sm leading-6 text-slate-700">${recommendation?.recommendation || "Role-specific guidance unavailable."}</p>
        <p className="mt-3 text-xs text-slate-500">Presented for ${String(recommendation?.role || "current role").replaceAll("_", " ")}; risk classification is not recalculated.</p>
      </article>
    </section>
    ${result.historical_actions?.length ? html`<section className="rounded-[1.75rem] border border-emerald-200 bg-emerald-50/50 p-5"><p className="eyebrow">PREVIOUSLY USED CORRECTIVE ACTIONS</p><p className="mt-2 text-sm text-slate-600">Verified actions from similar incidents are suggestions only and are never applied automatically.</p><div className="mt-4 space-y-3">${result.historical_actions.map((action) => html`<article className="rounded-xl bg-white p-4" key=${action.capa_id}><div className="flex justify-between gap-3"><b className="text-sm">${action.title}</b><span className="text-xs font-bold text-emerald-700">${action.related_percent}% related</span></div><p className="mt-2 text-sm text-slate-700">${action.action}</p><p className="mt-2 text-xs text-slate-500">Report ${action.report_id} · ${action.outcome} · ${action.verified_by}</p></article>`)}</div></section>` : null}
  `;
}

function EvidenceConfidence({ result }) {
  const confidence = result.confidence; const provenance = result.input_provenance; const photo = result.photo_findings;
  if (!confidence && !provenance && !photo && !result.document_extraction) return null;
  return html`<section className=${`rounded-[1.75rem] border p-5 ${result.hse_review_recommended ? "border-amber-300 bg-amber-50" : "border-slate-200 bg-white"}`}><div className="flex flex-wrap items-start justify-between gap-3"><div><p className="eyebrow">CONFIDENCE / UNCERTAINTY</p><h3 className="mt-2 text-xl font-bold">${confidence?.label || "Not assessed"}</h3></div>${result.hse_review_recommended ? html`<span className="rounded-full bg-amber-600 px-3 py-1 text-xs font-bold text-white">HSE REVIEW RECOMMENDED</span>` : null}</div><p className="mt-2 text-xs text-slate-500">Evidence signal label—not a calibrated probability. Risk is not downgraded when confidence is low.</p>${confidence?.reasons?.length ? html`<ul className="mt-3 list-disc space-y-1 pl-5 text-sm text-slate-700">${confidence.reasons.map((reason) => html`<li key=${reason}>${reason}</li>`)}</ul>` : null}${result.document_extraction ? html`<p className="mt-3 rounded-xl bg-slate-50 p-3 text-xs"><b>Text source:</b> ${result.document_extraction.text_source}${result.document_extraction.ocr_confidence ? ` · OCR confidence ${result.document_extraction.ocr_confidence}` : ""}</p>` : null}${photo ? html`<div className="mt-4 grid gap-3 md:grid-cols-3"><${EvidenceList} title="Observed visual evidence" values=${[...(photo.visible_hazards || []), ...(photo.visible_controls || [])]} /><${EvidenceList} title="AI inferred possibilities" values=${[...(photo.possible_missing_controls || []), ...(photo.possible_exposures || [])]} /><article className="rounded-xl bg-slate-50 p-3"><p className="text-xs font-bold uppercase text-slate-500">Image summary</p><p className="mt-2 text-sm">${photo.image_summary}</p><p className="mt-2 text-xs font-bold text-amber-700">${photo.disclaimer}</p></article></div>` : null}${provenance ? html`<div className="mt-4 grid gap-3 md:grid-cols-3"><${EvidenceList} title="Reported by user" values=${provenance.REPORTED_BY_USER || provenance.reported_by_user} /><${EvidenceList} title="Observed in image" values=${provenance.OBSERVED_IN_IMAGE || provenance.observed_in_image} /><${EvidenceList} title="AI inference" values=${provenance.AI_INFERRED || provenance.ai_inferred} /></div>` : null}</section>`;
}

function EvidenceList({ title, values = [] }) { return html`<article className="rounded-xl bg-slate-50 p-3"><p className="text-xs font-bold uppercase text-slate-500">${title}</p>${values?.length ? html`<ul className="mt-2 list-disc space-y-1 pl-4 text-xs text-slate-700">${values.map((value) => html`<li key=${value}>${value}</li>`)}</ul>` : html`<p className="mt-2 text-xs text-slate-400">None supplied</p>`}</article>`; }

function HSEReviewPanel({ result, actor }) {
  const canReview = ["HSE_OFFICER", "HSE_MANAGER", "ADMIN"].includes(actor?.role);
  const [mode, setMode] = React.useState(""); const [message, setMessage] = React.useState(""); const [error, setError] = React.useState("");
  const [fields, setFields] = React.useState({ reviewed_hazard: result.hazard, reviewed_energy_source: result.energy_source, reviewed_exposure_type: result.exposure_type, reviewed_critical_control: result.critical_control, reviewed_control_status: result.control_status, reviewed_potential_consequence: result.potential_consequence, reviewed_likelihood: result.likelihood, reviewed_precursor: result.precursor_pattern, reviewed_risk_level: result.risk_level, review_note: "" });
  if (!canReview) return html`<section className="rounded-[1.75rem] border border-slate-200 bg-slate-50 p-5"><p className="eyebrow">HSE HUMAN REVIEW</p><p className="mt-2 text-sm text-slate-600">Review status: <b>Unreviewed</b>. Switch to an HSE Officer or Manager role to review. The AI analysis remains preserved.</p></section>`;
  async function submit(decision) { try { await submitReview(result.report_id, { decision, review_note: fields.review_note, ...(decision === "corrected" ? fields : {}) }); setMessage(`Review stored: ${decision.replaceAll("_", " ")}. AI analysis preserved.`); setError(""); setMode(""); } catch (err) { setError(err.message); } }
  return html`<section className="rounded-[1.75rem] border border-violet-200 bg-violet-50/50 p-5"><p className="eyebrow">HSE HUMAN REVIEW</p><div className="mt-3 grid gap-4 lg:grid-cols-2"><div className="rounded-xl bg-white p-4"><p className="text-xs font-bold uppercase text-slate-500">AI Analysis · preserved</p><p className="mt-2 text-sm"><b>${result.risk_level}</b> · ${result.hazard}</p><p className="mt-1 text-xs text-slate-500">${result.precursor_pattern}</p></div><div className="rounded-xl border border-dashed border-violet-200 p-4"><p className="text-xs font-bold uppercase text-violet-700">HSE Reviewed Analysis</p><p className="mt-2 text-sm">${message || "Unreviewed"}</p></div></div>
    <div className="mt-4 flex flex-wrap gap-2"><button className="primary-button" onClick=${() => submit("confirmed")}>Confirm Analysis</button><button className="secondary-button" onClick=${() => setMode("corrected")}>Correct Analysis</button><button className="secondary-button" onClick=${() => setMode("rejected")}>Reject Flag</button><button className="secondary-button" onClick=${() => setMode("needs_more_information")}>Needs More Information</button></div>
    ${mode ? html`<div className="mt-4 rounded-xl bg-white p-4">${mode === "corrected" ? html`<div className="grid gap-3 md:grid-cols-2">${Object.entries(fields).filter(([key]) => key !== "review_note").map(([key, value]) => html`<label key=${key}><span className="filter-label">${key.replace("reviewed_", "").replaceAll("_", " ")}</span><input className="filter-control" value=${value || ""} onChange=${(e) => setFields({ ...fields, [key]: e.target.value })} /></label>`)}</div>` : null}<label className="mt-3 block"><span className="filter-label">Review note</span><textarea className="filter-control min-h-24" value=${fields.review_note} onChange=${(e) => setFields({ ...fields, review_note: e.target.value })}></textarea></label><button className="primary-button mt-3" onClick=${() => submit(mode)}>Store ${mode.replaceAll("_", " ")}</button></div>` : null}${error ? html`<div className="error-box mt-3">${error}</div>` : null}</section>`;
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
