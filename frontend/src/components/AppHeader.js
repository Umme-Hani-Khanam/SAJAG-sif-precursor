import { html } from "../ui.js";

export function AppHeader() {
  return html`
    <header className="rounded-3xl border border-slate-200 bg-white px-6 py-6 shadow-sm sm:px-8">
      <div className="flex flex-col gap-5 md:flex-row md:items-center md:justify-between">
        
        <div>
          <div className="mb-2 flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-slate-900 text-lg font-bold text-white">
              S
            </div>

            <div>
              <p className="text-xs font-bold uppercase tracking-[0.25em] text-cyan-600">
                SAJAG
              </p>
              <p className="text-xs text-slate-500">
                Safety Intelligence Platform
              </p>
            </div>
          </div>

          <h1 className="mt-4 text-3xl font-bold tracking-tight text-slate-900 sm:text-4xl">
            SIF Precursor Detection
          </h1>

          <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-500">
            Analyze safety observations, identify serious injury and fatality
            precursors, and understand the factors contributing to risk.
          </p>
        </div>

        <div className="flex items-center gap-2 rounded-full border border-emerald-200 bg-emerald-50 px-4 py-2">
          <span className="h-2.5 w-2.5 rounded-full bg-emerald-500"></span>
          <span className="text-sm font-semibold text-emerald-700">
            Backend Online
          </span>
        </div>

      </div>
    </header>
  `;
}