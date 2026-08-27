import os
from io import BytesIO

import pandas as pd
from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from database import Base, engine, get_db
from models import SafetyReport
from schemas import HealthResponse, SafetyReportResponse, UploadResponse
from schemas import AnalyzeRequest, AnalyzeResponse
from intelligence import analyze_description


APP_NAME = os.getenv("APP_NAME", "SAJAG Phase 1 API")

REQUIRED_COLUMNS = [
    "Report ID",
    "Date",
    "Location/Site",
    "Department",
    "Activity",
    "Report Type",
    "Shift",
    "Source",
    "Company",
    "Region",
    "Site",
    "Description",
]

COLUMN_MAPPING = {
    "Report ID": "report_id",
    "Date": "date",
    "Location/Site": "location_site",
    "Department": "department",
    "Activity": "activity",
    "Report Type": "report_type",
    "Shift": "shift",
    "Source": "source",
    "Company": "company",
    "Region": "region",
    "Site": "site",
    "Description": "description",
}

app = FastAPI(title=APP_NAME)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8080",
        "http://127.0.0.1:8080",
        "http://localhost:5500",
        "http://127.0.0.1:5500",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)


def read_uploaded_dataframe(upload_file: UploadFile) -> pd.DataFrame:
    extension = os.path.splitext(upload_file.filename or "")[1].lower()

    try:
        file_bytes = upload_file.file.read()
        if not file_bytes:
            raise HTTPException(status_code=400, detail="Uploaded file is empty.")

        if extension == ".csv":
            return pd.read_csv(
                BytesIO(file_bytes),
                dtype=str,
                keep_default_na=False,
                na_filter=False,
            )

        if extension == ".xlsx":
            return pd.read_excel(
                BytesIO(file_bytes),
                dtype=str,
                keep_default_na=False,
                na_filter=False,
            )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to read file: {exc}") from exc

    raise HTTPException(
        status_code=400,
        detail="Unsupported file type. Please upload a .csv or .xlsx file.",
    )


def validate_required_columns(dataframe: pd.DataFrame) -> None:
    missing_columns = [column for column in REQUIRED_COLUMNS if column not in dataframe.columns]
    if missing_columns:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Uploaded file is missing required columns.",
                "missing_columns": missing_columns,
                "required_columns": REQUIRED_COLUMNS,
            },
        )


@app.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    return HealthResponse(status="ok", message="SAJAG Phase 1 backend is running.")


@app.post("/analyze", response_model=AnalyzeResponse)
def analyze_report(
    request: AnalyzeRequest,
    db: Session = Depends(get_db),
) -> AnalyzeResponse:
    return analyze_description(
        description=request.description,
        site=request.site,
        activity=request.activity,
        stored_reports=db.query(SafetyReport).all(),
    )


@app.post("/reports/upload", response_model=UploadResponse)
def upload_reports(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> UploadResponse:
    dataframe = read_uploaded_dataframe(file)
    validate_required_columns(dataframe)

    inserted = 0
    updated = 0

    for row in dataframe[REQUIRED_COLUMNS].to_dict(orient="records"):
        payload = {COLUMN_MAPPING[column]: value for column, value in row.items()}
        existing_report = db.get(SafetyReport, payload["report_id"])

        if existing_report is None:
            db.add(SafetyReport(**payload))
            inserted += 1
            continue

        for field_name, value in payload.items():
            setattr(existing_report, field_name, value)
        updated += 1

    db.commit()

    return UploadResponse(
        message="Synthetic safety dataset processed successfully.",
        total_rows=len(dataframe.index),
        inserted=inserted,
        updated=updated,
    )


@app.get("/reports", response_model=list[SafetyReportResponse])
def list_reports(db: Session = Depends(get_db)) -> list[SafetyReport]:
    return db.query(SafetyReport).order_by(SafetyReport.report_id.asc()).all()


@app.get("/reports/{report_id}", response_model=SafetyReportResponse)
def get_report(report_id: str, db: Session = Depends(get_db)) -> SafetyReport:
    report = db.get(SafetyReport, report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found.")
    return report
