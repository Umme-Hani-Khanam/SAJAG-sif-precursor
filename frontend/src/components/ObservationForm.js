import { html } from "../ui.js";

export function ObservationForm({ description, isLoading, onChange, onSubmit }) {
  return html`
    <section className="rounded-[2rem] border border-white/10 bg-slatebase/70 p-6 shadow-panel backdrop-blur">
      <div className="mb-4 flex items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-semibold text-white">Safety Observation</h2>
          <p className="mt-1 text-sm text-slate-300">
            Enter the field observation and run the prototype analysis.
          </p>
        </div>
        <span className="rounded-full border border-amberaccent/25 bg-amberaccent/10 px-3 py-1 text-xs font-medium text-amberaccent">
          Prototype input
        </span>
      </div>

      <form className="space-y-4" onSubmit=${onSubmit}>
        <label className="block">
          <span className="mb-2 block text-sm font-medium text-slate-200">
            Observation description
          </span>
          <textarea
            value=${description}
            onChange=${(event) => onChange(event.target.value)}
            placeholder="Example: Worker climbed onto an elevated platform without tying off while lifting material near an open edge."
            className="min-h-40 w-full rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-white outline-none transition placeholder:text-slate-400 focus:border-cyanaccent/50 focus:ring-2 focus:ring-cyanaccent/25"
          ></textarea>
        </label>

        <div className="flex items-center justify-between gap-4">
          <p className="text-xs text-slate-400">
            Prototype uses synthetic safety data.
          </p>
          <button
            type="submit"
            disabled=${isLoading}
            className="inline-flex min-w-36 items-center justify-center rounded-2xl bg-cyanaccent px-6 py-3 text-sm font-semibold text-slate-950 transition hover:bg-[#73d8f4] disabled:cursor-not-allowed disabled:opacity-70"
          >
            ${isLoading ? "Analyzing..." : "ANALYZE"}
          </button>
        </div>
      </form>
    </section>
  `;
}
