import { html } from "../ui.js";
import { PageTitle } from "./AnalyzePage.js";
import { ReportManagement } from "./ReportManagement.js";

export function ReportsPage({ actor }) {
  return html`<div className="space-y-6"><${PageTitle} eyebrow="REPORTS" title="Historical report base" subtitle="Import, batch-analyse, filter, inspect, review, and export the persistent safety intelligence dataset." /><${ReportManagement} actor=${actor} /></div>`;
}
