import React from "react";
import { SectionErrorBoundary } from "./SectionErrorBoundary.js";
import { ScoreHighlights } from "./ScoreHighlights.js";
import { ResultCard } from "./ResultCard.js";
import { SimilarReportsSection } from "./SimilarReportsSection.js";
import { InsightActions } from "./InsightActions.js";

export function AnalysisResults({ result }) {
  return React.createElement(
    "div",
    { className: "space-y-6" },
    React.createElement(
      SectionErrorBoundary,
      { fallbackMessage: "Score highlights could not be rendered." },
      React.createElement(ScoreHighlights, {
        sifScore: result.sif_score,
        riskLevel: result.risk_level,
      }),
    ),
    React.createElement(
      "section",
      { className: "grid gap-4 md:grid-cols-2 xl:grid-cols-3" },
      React.createElement(
        SectionErrorBoundary,
        { fallbackMessage: "Precursor pattern section is unavailable." },
        React.createElement(ResultCard, {
          title: "Precursor Pattern",
          value: result.precursor_pattern,
        }),
      ),
      React.createElement(
        SectionErrorBoundary,
        { fallbackMessage: "Hazard section is unavailable." },
        React.createElement(ResultCard, {
          title: "Hazard",
          value: result.hazard,
        }),
      ),
      React.createElement(
        SectionErrorBoundary,
        { fallbackMessage: "Unsafe act section is unavailable." },
        React.createElement(ResultCard, {
          title: "Unsafe Act",
          value: result.unsafe_act,
        }),
      ),
      React.createElement(
        SectionErrorBoundary,
        { fallbackMessage: "Unsafe condition section is unavailable." },
        React.createElement(ResultCard, {
          title: "Unsafe Condition",
          value: result.unsafe_condition,
        }),
      ),
      React.createElement(
        SectionErrorBoundary,
        { fallbackMessage: "Site section is unavailable." },
        React.createElement(ResultCard, {
          title: "Site",
          value: result.site,
        }),
      ),
      React.createElement(
        SectionErrorBoundary,
        { fallbackMessage: "Activity section is unavailable." },
        React.createElement(ResultCard, {
          title: "Activity",
          value: result.activity,
        }),
      ),
    ),
    React.createElement(
      SectionErrorBoundary,
      { fallbackMessage: "Action placeholders are unavailable." },
      React.createElement(InsightActions),
    ),
    React.createElement(
      SectionErrorBoundary,
      { fallbackMessage: "Similar historical reports are unavailable." },
      React.createElement(SimilarReportsSection, {
        reports: result.similar_reports,
      }),
    ),
  );
}
