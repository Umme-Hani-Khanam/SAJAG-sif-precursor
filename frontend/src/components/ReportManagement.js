import React from "react";
import { html } from "../ui.js";
import {
  uploadReports,
  getReports,
} from "../api/reports.js";

export function ReportManagement({ onReportsLoaded }) {
  const [datasetFile, setDatasetFile] = React.useState(null);

  const [uploadingDataset, setUploadingDataset] =
    React.useState(false);

  const [datasetResult, setDatasetResult] =
    React.useState(null);

  const [error, setError] = React.useState("");

  const [reports, setReports] = React.useState([]);
  const [loadingReports, setLoadingReports] =
    React.useState(false);

  async function handleDatasetUpload() {
    if (!datasetFile) {
      setError("Please select a CSV or XLSX file first.");
      return;
    }

    setUploadingDataset(true);
    setError("");
    setDatasetResult(null);

    try {
      const result = await uploadReports(datasetFile);

      setDatasetResult(result);
      setDatasetFile(null);

      await loadReports();
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to upload the dataset.",
      );
    } finally {
      setUploadingDataset(false);
    }
  }

  async function loadReports() {
    setLoadingReports(true);

    try {
      const result = await getReports();
      const nextReports = Array.isArray(result) ? result : [];
      setReports(nextReports);
      if (onReportsLoaded) {
        onReportsLoaded(nextReports);
      }
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to load historical reports.",
      );
      if (onReportsLoaded) {
        onReportsLoaded([]);
      }
    } finally {
      setLoadingReports(false);
    }
  }

  React.useEffect(() => {
    loadReports();
  }, []);

  const priorityAreas = getPriorityAreas(reports);

  return html`
    <section className="rounded-[2rem] border border-slate-200 bg-white p-6 shadow-sm">
      <div className="mb-6">
        <p className="text-xs font-semibold uppercase tracking-[0.28em] text-cyan-600">
          REPORT MANAGEMENT
        </p>

        <h2 className="mt-2 text-2xl font-semibold text-slate-900">
          Historical Report Base
        </h2>

        <p className="mt-2 text-sm leading-6 text-slate-500">
          Upload safety datasets and review the historical observations stored
          by the SAJAG backend.
        </p>
      </div>

      <div className="grid gap-5">

        <!-- Dataset upload -->

        <article className="rounded-2xl border border-slate-200 bg-slate-50 p-5">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-cyan-600">
            DATASET
          </p>

          <h3 className="mt-2 text-lg font-semibold text-slate-900">
            Upload Safety Reports
          </h3>

          <p className="mt-1 text-sm text-slate-500">
            Supported formats: CSV and XLSX
          </p>

          <input
            type="file"
            accept=".csv,.xlsx"
            className="mt-4 block w-full rounded-xl border border-slate-200 bg-white p-3 text-sm text-slate-600"
            onChange=${(event) =>
              setDatasetFile(event.target.files?.[0] || null)}
          />

          <button
            type="button"
            disabled=${uploadingDataset}
            onClick=${handleDatasetUpload}
            className="mt-4 rounded-xl bg-slate-900 px-5 py-3 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60"
          >
            ${uploadingDataset
              ? "Uploading..."
              : "Upload Dataset"}
          </button>

          ${datasetResult
            ? html`
                <div className="mt-4 rounded-xl border border-emerald-200 bg-emerald-50 p-4">
                  <p className="text-sm font-semibold text-emerald-800">
                    Upload successful
                  </p>

                  <div className="mt-2 grid grid-cols-3 gap-2 text-center">
                    <div>
                      <p className="text-lg font-bold text-slate-900">
                        ${datasetResult.total_rows}
                      </p>
                      <p className="text-xs text-slate-500">Rows</p>
                    </div>

                    <div>
                      <p className="text-lg font-bold text-slate-900">
                        ${datasetResult.inserted}
                      </p>
                      <p className="text-xs text-slate-500">Inserted</p>
                    </div>

                    <div>
                      <p className="text-lg font-bold text-slate-900">
                        ${datasetResult.updated}
                      </p>
                      <p className="text-xs text-slate-500">Updated</p>
                    </div>
                  </div>
                </div>
              `
            : null}
        </article>
      </div>


      ${error
        ? html`
            <div className="mt-5 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              ${error}
            </div>
          `
        : null}


      <!-- Historical reports -->

      <div className="mt-8">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-lg font-semibold text-slate-900">
              Historical Reports
            </h3>

            <p className="mt-1 text-sm text-slate-500">
              Reports currently stored in the backend database.
            </p>
          </div>

          <button
            type="button"
            onClick=${loadReports}
            className="rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            Refresh
          </button>
        </div>


        ${loadingReports
          ? html`
              <p className="mt-5 text-sm text-slate-500">
                Loading reports...
              </p>
            `
          : reports.length === 0
            ? html`
                <div className="mt-5 rounded-xl border border-dashed border-slate-200 p-6 text-center text-sm text-slate-500">
                  No historical reports have been loaded yet.
                </div>
              `
            : html`
                <div className="mt-5 overflow-x-auto rounded-xl border border-slate-200">
                  <table className="min-w-full text-left text-sm">
                    <thead className="bg-slate-50">
                      <tr>
                        <th className="px-4 py-3 font-semibold text-slate-700">
                          Report ID
                        </th>
                        <th className="px-4 py-3 font-semibold text-slate-700">
                          Date
                        </th>
                        <th className="px-4 py-3 font-semibold text-slate-700">
                          Site
                        </th>
                        <th className="px-4 py-3 font-semibold text-slate-700">
                          Activity
                        </th>
                      </tr>
                    </thead>

                    <tbody className="divide-y divide-slate-100">
                      ${reports.slice(0, 20).map(
                        (report) => html`
                          <tr key=${report.report_id}>
                            <td className="px-4 py-3 font-medium text-slate-900">
                              ${report.report_id}
                            </td>

                            <td className="px-4 py-3 text-slate-600">
                              ${report.date}
                            </td>

                            <td className="px-4 py-3 text-slate-600">
                              ${report.site || report.location_site || "—"}
                            </td>

                            <td className="px-4 py-3 text-slate-600">
                              ${report.activity || "—"}
                            </td>
                          </tr>
                        `,
                      )}
                    </tbody>
                  </table>
                </div>
              `}
      </div>

      ${priorityAreas.sites.length > 0 || priorityAreas.activities.length > 0
        ? html`
            <div className="mt-8 rounded-2xl border border-slate-200 bg-slate-50 p-5">
              <p className="text-xs font-semibold uppercase tracking-[0.22em] text-cyan-600">
                HSE PRIORITY AREAS
              </p>

              <div className="mt-4 grid gap-4 lg:grid-cols-2">
                ${priorityAreas.sites.length > 0
                  ? html`
                      <div>
                        <h4 className="text-sm font-semibold text-slate-900">
                          Top sites by precursor density
                        </h4>
                        <div className="mt-3 space-y-2">
                          ${priorityAreas.sites.map(
                            (item) => html`
                              <div className="flex items-center justify-between rounded-xl bg-white px-4 py-3">
                                <span className="text-sm text-slate-700">${item.name}</span>
                                <span className="text-sm font-semibold text-slate-900">${item.count}</span>
                              </div>
                            `,
                          )}
                        </div>
                      </div>
                    `
                  : null}

                ${priorityAreas.activities.length > 0
                  ? html`
                      <div>
                        <h4 className="text-sm font-semibold text-slate-900">
                          Top activities by precursor density
                        </h4>
                        <div className="mt-3 space-y-2">
                          ${priorityAreas.activities.map(
                            (item) => html`
                              <div className="flex items-center justify-between rounded-xl bg-white px-4 py-3">
                                <span className="text-sm text-slate-700">${item.name}</span>
                                <span className="text-sm font-semibold text-slate-900">${item.count}</span>
                              </div>
                            `,
                          )}
                        </div>
                      </div>
                    `
                  : null}
              </div>
            </div>
          `
        : null}
    </section>
  `;
}

function getPriorityAreas(reports) {
  return {
    sites: rankValues(reports, (report) => report.site || report.location_site),
    activities: rankValues(reports, (report) => report.activity),
  };
}

function rankValues(reports, pickValue) {
  const counts = new Map();

  for (const report of reports) {
    const value = String(pickValue(report) || "").trim();
    if (!value) {
      continue;
    }
    counts.set(value, (counts.get(value) || 0) + 1);
  }

  return Array.from(counts.entries())
    .sort((left, right) => right[1] - left[1])
    .slice(0, 3)
    .map(([name, count]) => ({ name, count }));
}
