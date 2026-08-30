# SAJAG pre-change implementation audit

Baseline inspected at commit `0185e1e` before Phase 1 changes.

| Observation requested for verification | Baseline finding | Evidence in the baseline |
|---|---|---|
| Historical similarity uses MiniLM embeddings and cosine similarity | **True** | `backend/intelligence.py` loaded `sentence-transformers/all-MiniLM-L6-v2`, encoded all descriptions per request, and called `cosine_similarity`. |
| The UI hardcodes similarity percentages | **False** | `SimilarReportsSection.js` calculated display text from `Number(report.similarity) * 100`; it did not contain a fixed 47.6% value. |
| Repeated descriptions / near-identical similarity can occur | **True** | The supplied XLSX has 100 unique report IDs but only 10 unique descriptions. Each description occurs 8–12 times. Description-only historical embeddings are therefore identical for those rows. |
| Stale state or duplicate IDs cause the repeated evidence cards | **False** | IDs in the XLSX are unique, React renders the current response directly, and the API creates one result per database row. The repeated content originates in the workbook. |
| DBSCAN runs but its result is discarded | **True** | `_cluster_label()` returned the new row's label, but `analyze_description()` called it without assigning the return value; no schema/API/UI field used it. |
| Historical uploads are stored but not pre-analysed and persisted | **True** | `SafetyReport` contained source columns only. Upload upserted those fields; there was no analysis or embedding table. |
| “Top sites by precursor density” is report count rather than SIF risk density | **True** | Backend `_site_activity_rankings()` divided raw counts by total, and the visible frontend independently ranked raw site/activity counts. The backend result was itself discarded. |
| Cluster explorer exists | **False** | No cluster endpoint, view, or drill-down existed. |
| Emerging pattern engine exists | **False** | No timestamp-window or acceleration logic existed. |
| Temporal trend chart exists | **False** | No analytics endpoint or chart existed. |
| CSV export exists | **False** | Only CSV/XLSX import existed. |
| Real application navigation exists | **False** | `App.js` rendered one long analysis/report-management page. |
| Genuine document RAG exists | **False** | PDF text was extracted and sent through the same single-document analysis function; no chunking, retrieval index, or grounded retrieval existed. |
| Human HSE feedback/override loop exists | **False** | No review schema, API, or interface existed. |
| Audit trail exists | **False** | No append-only event/history model existed. |
| CAPA workflow exists | **False** | No action model, lifecycle, ownership, or due-date workflow existed. |
| Photo analysis exists | **False** | The only file-analysis route accepted text-based PDF files. |

## Controlled reproduction and root cause

Two rows with different IDs and the exact same description produce the exact same historical embedding because the baseline embedding input is only the description. Cosine comparison against the same query must therefore produce the same score. The supplied workbook reproduces this condition at scale: 90 of its 100 rows repeat content already present elsewhere.

The defect is consequently a combination of content-duplicated source descriptions and a description-only, non-diversified retrieval result. It is not a hardcoded UI value, duplicate primary key, or stale React state. The Phase 1 tests retain a controlled two-ID/same-description case and assert identical stored embeddings, while the evidence service suppresses repeated normalized descriptions in the returned cards.
