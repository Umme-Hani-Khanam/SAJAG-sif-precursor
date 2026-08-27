import { html } from "../ui.js";

const actionItems = [
  {
    title: "Life-Saving Rule",
    description: "Reserved for backend-integrated guidance in the next prototype phase.",
  },
  {
    title: "Preventive Measures",
    description: "Placeholder UI block for future prevention recommendations.",
  },
  {
    title: "Why This Score?",
    description: "Placeholder UI block for score rationale and explainability.",
  },
];

export function InsightActions() {
  return html`
    <section className="grid gap-4 md:grid-cols-3">
      ${actionItems.map(
        (item) => html`
          <article
            key=${item.title}
            className="rounded-[1.75rem] border border-white/10 bg-steel/50 p-5 shadow-panel"
          >
            <h3 className="text-lg font-semibold text-white">${item.title}</h3>
            <p className="mt-2 text-sm leading-6 text-slate-300">${item.description}</p>
            <button
              type="button"
              className="mt-4 rounded-xl border border-white/10 px-4 py-2 text-sm font-medium text-slate-200"
            >
              Coming Soon
            </button>
          </article>
        `,
      )}
    </section>
  `;
}
