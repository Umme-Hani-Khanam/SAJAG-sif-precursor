import React from "react";
import { getAudit } from "../api/governance.js";
import { html } from "../ui.js";
import { PageTitle } from "./AnalyzePage.js";

export function AuditPage({ actor }) {
  const [events, setEvents] = React.useState([]); const [error, setError] = React.useState("");
  const [filters, setFilters] = React.useState({ date: "", actor: "", role: "", event_type: "", report_id: "", capa_id: "" });
  async function load() { try { setEvents(await getAudit(filters)); setError(""); } catch (err) { setEvents([]); setError(err.message); } }
  React.useEffect(() => { load(); }, [actor.role]);
  return html`<div className="space-y-6"><${PageTitle} eyebrow="AUDIT" title="Append-only safety timeline" subtitle="Every material review, action, evidence, closure, and escalation is attributed to an actor and retained as immutable evidence." />${error ? html`<div className="error-box">${error}</div>` : null}
    <section className="panel"><div className="grid gap-3 md:grid-cols-3 lg:grid-cols-6">${Object.entries(filters).map(([key, value]) => html`<label key=${key}><span className="filter-label">${key.replaceAll("_", " ")}</span><input className="filter-control" type=${key === "date" ? "date" : "text"} value=${value} onChange=${(e) => setFilters({ ...filters, [key]: e.target.value })} /></label>`)}</div><button className="primary-button mt-4" onClick=${load}>Apply filters</button></section>
    <section className="panel"><div className="space-y-0">${events.map((event, index) => html`<article key=${event.event_id} className="relative border-l-2 border-cyan-200 pb-6 pl-6"><span className="absolute -left-[7px] top-1 h-3 w-3 rounded-full bg-cyan-500"></span><p className="text-xs text-slate-500">${new Date(event.timestamp).toLocaleString()}</p><h2 className="mt-1 font-bold">${event.event_type.replaceAll("_", " ")}</h2><p className="mt-1 text-sm text-slate-600">${event.actor_name} · ${event.actor_role.replaceAll("_", " ")} · ${event.entity_type} ${event.entity_id}</p>${event.reason ? html`<p className="mt-2 rounded-lg bg-slate-50 p-2 text-sm">${event.reason}</p>` : null}</article>`)}</div>${!events.length && !error ? html`<p className="py-8 text-center text-sm text-slate-500">No audit events match the filters.</p>` : null}</section>
  </div>`;
}
