import { html } from "../ui.js";

export function AppHeader() {
  return html`
    <header className="relative overflow-hidden rounded-[2rem] border border-white/10 bg-white/8 p-8 shadow-panel backdrop-blur">
      <div className="absolute inset-0 bg-grid bg-[size:36px_36px] opacity-20"></div>
      <div className="relative flex flex-col gap-3">
        <span className="w-fit rounded-full border border-cyanaccent/30 bg-cyanaccent/10 px-4 py-1 text-xs font-semibold uppercase tracking-[0.35em] text-cyanaccent">
          SAJAG
        </span>
        <div className="max-w-3xl">
          <h1 className="text-3xl font-semibold text-white sm:text-5xl">
            SIF Precursor Detection & Early Warning
          </h1>
          <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-300 sm:text-base">
            Industrial safety observation analysis dashboard for rapid screening,
            precursor visibility, and presentation-ready review.
          </p>
        </div>
      </div>
    </header>
  `;
}
