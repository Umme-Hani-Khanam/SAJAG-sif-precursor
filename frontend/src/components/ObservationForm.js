import { html } from "../ui.js";

export function ObservationForm({
  description,
  inputMode,
  site,
  activity,
  observedAt,
  isLoading,
  isPdfLoading,
  pdfFileName,
  pdfError,
  photoFileName,
  photoError,
  isPhotoLoading,
  onChange,
  onModeChange,
  onPdfSelect,
  onSiteChange,
  onActivityChange,
  onObservedAtChange,
  onPhotoSelect,
  onPhotoSubmit,
  onSubmit,
  onPdfSubmit,
}) {
  return html`
    <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm sm:p-7">

      <div className="mb-6">
        <div className="flex items-center justify-between gap-4">
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.2em] text-cyan-600">
              New Safety Observation
            </p>

            <h2 className="mt-2 text-2xl font-bold text-slate-900">
              SIF Precursor Detection & Early Warning
            </h2>
          </div>

          <div className="hidden rounded-full border border-slate-200 bg-slate-50 px-3 py-1.5 sm:block">
            <span className="text-xs font-medium text-slate-500">
              SIF Analysis
            </span>
          </div>
        </div>

        <p className="mt-2 text-sm leading-6 text-slate-500">
          Choose a text observation or PDF report, run SAJAG analysis, and
          review the score, evidence, and control actions in one place.
        </p>
      </div>

      <div className="mb-5 flex flex-wrap gap-3">
        <button
          type="button"
          onClick=${() => onModeChange("text")}
          className=${`rounded-2xl px-4 py-2.5 text-sm font-semibold transition ${
            inputMode === "text"
              ? "bg-slate-900 text-white shadow-sm"
              : "border border-slate-200 bg-slate-50 text-slate-700 hover:bg-slate-100"
          }`}
        >
          Write Observation
        </button>

        <button
          type="button"
          onClick=${() => onModeChange("pdf")}
          className=${`rounded-2xl px-4 py-2.5 text-sm font-semibold transition ${
            inputMode === "pdf"
              ? "bg-slate-900 text-white shadow-sm"
              : "border border-slate-200 bg-slate-50 text-slate-700 hover:bg-slate-100"
          }`}
        >
          Upload PDF
        </button>
        <button type="button" onClick=${() => onModeChange("photo")} className=${`rounded-2xl px-4 py-2.5 text-sm font-semibold transition ${inputMode === "photo" ? "bg-slate-900 text-white shadow-sm" : "border border-slate-200 bg-slate-50 text-slate-700 hover:bg-slate-100"}`}>Upload Photo</button>
      </div>

      ${inputMode === "text"
        ? html`
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

              <div className="grid gap-4 sm:grid-cols-3">

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

                <label className="block"><span className="mb-2 block text-sm font-semibold text-slate-700">Observed at</span><input type="datetime-local" value=${observedAt} onChange=${(event) => onObservedAtChange(event.target.value)} className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm" /></label>

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
                    1. Give report 2. Analyze 3. See risk 4. Understand why
                  </p>
                </div>

                <button
                  type="submit"
                  disabled=${isLoading}
                  className="inline-flex min-h-12 items-center justify-center rounded-2xl bg-slate-900 px-7 py-3 text-sm font-bold text-white shadow-sm transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  ${isLoading ? "Analyzing..." : "Analyze"}
                </button>

              </div>

            </form>
          `
        : inputMode === "pdf" ? html`
            <form className="space-y-5" onSubmit=${onPdfSubmit}>
              <label className="block">
                <span className="mb-2 block text-sm font-semibold text-slate-700">
                  Safety Report PDF
                </span>

                <div className="rounded-3xl border border-dashed border-cyan-200 bg-cyan-50/60 p-5">
                  <input
                    type="file"
                    accept=".pdf,application/pdf"
                    className="block w-full rounded-2xl border border-slate-200 bg-white p-3 text-sm text-slate-600 file:mr-4 file:rounded-xl file:border-0 file:bg-slate-900 file:px-4 file:py-2 file:text-sm file:font-semibold file:text-white"
                    onChange=${(event) =>
                      onPdfSelect(event.target.files?.[0] || null)}
                  />

                  <p className="mt-3 text-sm text-slate-600">
                    ${pdfFileName || "No PDF selected yet."}
                  </p>

                  <p className="mt-2 text-xs text-slate-500">
                    Native text is used when readable; scanned PDFs automatically use OCR fallback.
                  </p>
                </div>
              </label>
              <div className="grid gap-3 sm:grid-cols-3"><input className="filter-control" placeholder="Site" value=${site} onChange=${(e) => onSiteChange(e.target.value)} /><input className="filter-control" placeholder="Activity" value=${activity} onChange=${(e) => onActivityChange(e.target.value)} /><input className="filter-control" type="datetime-local" value=${observedAt} onChange=${(e) => onObservedAtChange(e.target.value)} /></div>

              ${pdfError
                ? html`
                    <div className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                      ${pdfError}
                    </div>
                  `
                : null}

              <div className="flex flex-col gap-4 border-t border-slate-100 pt-5 sm:flex-row sm:items-center sm:justify-between">
                <div className="flex items-center gap-2">
                  <span className="h-2 w-2 rounded-full bg-cyan-500"></span>

                  <p className="text-xs text-slate-500">
                    Upload PDF, analyze, and review the same result cards below.
                  </p>
                </div>

                <button
                  type="submit"
                  disabled=${isPdfLoading}
                  className="inline-flex min-h-12 items-center justify-center rounded-2xl bg-slate-900 px-7 py-3 text-sm font-bold text-white shadow-sm transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  ${isPdfLoading ? "Analyzing PDF..." : "Analyze"}
                </button>
              </div>
            </form>
          ` : html`<form className="space-y-5" onSubmit=${onPhotoSubmit}><label className="block"><span className="mb-2 block text-sm font-semibold text-slate-700">Hazard photo</span><input type="file" accept=".jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp" className="block w-full rounded-2xl border border-slate-200 bg-white p-3 text-sm" onChange=${(event) => onPhotoSelect(event.target.files?.[0] || null)} /><p className="mt-2 text-xs text-slate-500">${photoFileName || "JPG, PNG, or WEBP up to the configured upload limit."}</p></label><label><span className="filter-label">Reporter description (optional)</span><textarea className="filter-control min-h-28" value=${description} onChange=${(event) => onChange(event.target.value)} placeholder="Worker entered lifting zone during pipe handling."></textarea></label><div className="grid gap-3 sm:grid-cols-3"><input className="filter-control" placeholder="Site" value=${site} onChange=${(e) => onSiteChange(e.target.value)} /><input className="filter-control" placeholder="Activity" value=${activity} onChange=${(e) => onActivityChange(e.target.value)} /><input className="filter-control" type="datetime-local" value=${observedAt} onChange=${(e) => onObservedAtChange(e.target.value)} /></div>${photoError ? html`<div className="error-box">${photoError}</div>` : null}<div className="rounded-xl bg-amber-50 p-3 text-xs text-amber-800">Image-derived findings require HSE confirmation. The visual model supplies evidence only; the existing SAJAG pipeline decides final SIF risk.</div><button className="primary-button w-full" disabled=${isPhotoLoading}>${isPhotoLoading ? "Analyzing photo…" : "Analyze photo + text"}</button></form>`}
    </section>
  `;
}
