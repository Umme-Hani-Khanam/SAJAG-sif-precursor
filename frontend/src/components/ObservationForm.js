import { html } from "../ui.js";

export function ObservationForm({
  description,
  site,
  activity,
  isLoading,
  onChange,
  onSiteChange,
  onActivityChange,
  onSubmit,
}) {
  return html`
    <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm sm:p-7">
      
      <div className="mb-6">
        <div className="flex items-center justify-between gap-4">
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.2em] text-cyan-600">
              Analyze Report
            </p>

            <h2 className="mt-2 text-2xl font-bold text-slate-900">
              Safety Observation
            </h2>
          </div>

          <div className="hidden rounded-full border border-slate-200 bg-slate-50 px-3 py-1.5 sm:block">
            <span className="text-xs font-medium text-slate-500">
              SIF Analysis
            </span>
          </div>
        </div>

        <p className="mt-2 text-sm leading-6 text-slate-500">
          Enter the observation details below to identify SIF precursors,
          risk level, critical controls, and similar historical reports.
        </p>
      </div>

      <form className="space-y-5" onSubmit=${onSubmit}>

        <label className="block">
          <span className="mb-2 block text-sm font-semibold text-slate-700">
            Observation Description
          </span>

          <textarea
            value=${description}
            onChange=${(event) => onChange(event.target.value)}
            placeholder="Describe what happened, what the worker was doing, hazards observed, controls that failed, and surrounding conditions..."
            className="min-h-44 w-full resize-y rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3.5 text-sm leading-6 text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-cyan-400 focus:bg-white focus:ring-4 focus:ring-cyan-100"
          ></textarea>

          <p className="mt-2 text-xs text-slate-400">
            Provide as much detail as possible for better analysis.
          </p>
        </label>

        <div className="grid gap-4 sm:grid-cols-2">

          <label className="block">
            <span className="mb-2 block text-sm font-semibold text-slate-700">
              Site
            </span>

            <input
              type="text"
              value=${site}
              onChange=${(event) => onSiteChange(event.target.value)}
              placeholder="Example: Plant A"
              className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-cyan-400 focus:bg-white focus:ring-4 focus:ring-cyan-100"
            />
          </label>

          <label className="block">
            <span className="mb-2 block text-sm font-semibold text-slate-700">
              Activity
            </span>

            <input
              type="text"
              value=${activity}
              onChange=${(event) => onActivityChange(event.target.value)}
              placeholder="Example: Material handling"
              className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-cyan-400 focus:bg-white focus:ring-4 focus:ring-cyan-100"
            />
          </label>

        </div>

        <div className="flex flex-col gap-4 border-t border-slate-100 pt-5 sm:flex-row sm:items-center sm:justify-between">

          <div className="flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-cyan-500"></span>

            <p className="text-xs text-slate-500">
              Analysis is performed by the SAJAG backend.
            </p>
          </div>

          <button
            type="submit"
            disabled=${isLoading}
            className="inline-flex min-h-12 items-center justify-center rounded-2xl bg-slate-900 px-7 py-3 text-sm font-bold text-white shadow-sm transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60"
          >
            ${
              isLoading
                ? "Analyzing..."
                : "Analyze Observation"
            }
          </button>

        </div>

      </form>
    </section>
  `;
}