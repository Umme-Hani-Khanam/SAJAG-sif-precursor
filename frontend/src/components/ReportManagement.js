import React from "react";
import { html } from "../ui.js";
import {
  uploadReports,
  uploadPdfReport,
  getReports,
} from "../api/reports.js";

export function ReportManagement({ onPdfAnalysis }) {
  const [datasetFile, setDatasetFile] = React.useState(null);
  const [pdfFile, setPdfFile] = React.useState(null);

  const [uploadingDataset, setUploadingDataset] =
    React.useState(false);

  const [uploadingPdf, setUploadingPdf] =
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

  async function handlePdfUpload() {
    if (!pdfFile) {
      setError("Please select a PDF file first.");
      return;
    }

    setUploadingPdf(true);
    setError("");

    try {
      const result = await uploadPdfReport(pdfFile);

      setPdfFile(null);

      if (onPdfAnalysis) {
        onPdfAnalysis(result);
      }
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to analyze the PDF.",
      );
    } finally {
      setUploadingPdf(false);
    }
  }

  async function loadReports() {
    setLoadingReports(true);

    try {
      const result = await getReports();
      setReports(Array.isArray(result) ? result : []);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to load historical reports.",
      );
    } finally {
      setLoadingReports(false);
    }
  }

  React.useEffect(() => {
    loadReports();
  }, []);

  return html`
    <section className="rounded-[2rem] border border-slate-200 bg-white p-6 shadow-sm">
      <div className="mb-6">
        <p className="text-xs font-semibold uppercase tracking-[0.28em] text-cyan-600">
          REPORT MANAGEMENT
        </p>

        <h2 className="mt-2 text-2xl font-semibold text-slate-900">
          Safety Reports
        </h2>

        <p className="mt-2 text-sm leading-6 text-slate-500">
          Upload safety datasets, analyze PDF reports, and review historical
          observations stored by the SAJAG backend.
        </p>
      </div>

      <div className="grid gap-5 lg:grid-cols-2">

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


        <!-- PDF upload -->

        <article className="rounded-2xl border border-slate-200 bg-slate-50 p-5">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-cyan-600">
            PDF ANALYSIS
          </p>

          <h3 className="mt-2 text-lg font-semibold text-slate-900">
            Analyze PDF Report
          </h3>

          <p className="mt-1 text-sm text-slate-500">
            Upload a text-based PDF safety report.
          </p>

          <input
            type="file"
            accept=".pdf"
            className="mt-4 block w-full rounded-xl border border-slate-200 bg-white p-3 text-sm text-slate-600"
            onChange=${(event) =>
              setPdfFile(event.target.files?.[0] || null)}
          />

          <button
            type="button"
            disabled=${uploadingPdf}
            onClick=${handlePdfUpload}
            className="mt-4 rounded-xl bg-cyan-600 px-5 py-3 text-sm font-semibold text-white transition hover:bg-cyan-700 disabled:cursor-not-allowed disabled:opacity-60"
          >
            ${uploadingPdf
              ? "Analyzing PDF..."
              : "Analyze PDF"}
          </button>
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
                  No historical reports available.
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
    </section>
  `;
}