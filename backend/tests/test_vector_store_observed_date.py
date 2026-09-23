from datetime import datetime
from io import BytesIO

import numpy as np
from fastapi.testclient import TestClient
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject
from sqlalchemy import String

import main
from database import get_db
from models import DocumentChunk, SafetyDocument
from services.embeddings import serialize_embedding
from services.knowledge import ingest_document
from services.roles import Actor
from services.vector_store import PostgresVectorStore, SQLiteVectorStore


MANAGER_HEADERS = {"X-Actor-Name": "QA Manager", "X-Actor-Role": "HSE_MANAGER"}
OBSERVED_AT = datetime.fromisoformat("2026-09-23T07:11:00")


class EmptyRows:
    def all(self):
        return []


class RecordingSession:
    def __init__(self):
        self.executions = []

    def execute(self, statement, parameters):
        self.executions.append((statement, parameters))
        return EmptyRows()


def readable_pdf(text):
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    font = DictionaryObject({
        NameObject("/Type"): NameObject("/Font"),
        NameObject("/Subtype"): NameObject("/Type1"),
        NameObject("/BaseFont"): NameObject("/Helvetica"),
    })
    page[NameObject("/Resources")] = DictionaryObject({
        NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)}),
    })
    content = DecodedStreamObject()
    escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    content.set_data(f"BT /F1 10 Tf 72 720 Td ({escaped}) Tj ET".encode("latin-1"))
    page[NameObject("/Contents")] = writer._add_object(content)
    stream = BytesIO()
    writer.write(stream)
    return stream.getvalue()


def test_postgres_document_search_observed_date_bind_is_typed_for_value_and_none():
    session = RecordingSession()
    store = PostgresVectorStore()
    vector = np.array([1.0, 0.0, 0.0])

    store.search_document_chunks(session, vector, "test-model", observed_at=OBSERVED_AT)
    store.search_document_chunks(session, vector, "test-model", observed_at=None)

    statement = store.DOCUMENT_SEARCH_STATEMENT
    assert isinstance(statement._bindparams["observed_date"].type, String)
    assert [parameters["observed_date"] for _, parameters in session.executions] == ["2026-09-23", None]
    assert all(executed is statement for executed, _ in session.executions)


def test_document_search_temporal_eligibility_before_future_and_null_observation(db_session):
    vector = np.array([1.0, 0.0, 0.0])
    store = SQLiteVectorStore()

    def document(document_id, effective_date):
        item = SafetyDocument(
            document_id=document_id,
            title=f"{document_id} standard",
            organization="SAJAG QA",
            effective_date=effective_date,
            filename=f"{document_id}.txt",
            uploaded_by="QA Manager",
            chunk_count=1,
            status="APPROVED",
            indexing_status="completed",
        )
        chunk = DocumentChunk(
            chunk_id=f"CHK-{document_id}",
            document=item,
            text=f"Approved control guidance from {document_id}.",
            embedding=serialize_embedding(vector),
            embedding_model="test-model",
        )
        store.persist_document_embedding(chunk, vector, "test-model")
        return item

    db_session.add_all([document("BEFORE", "2026-01-01"), document("FUTURE", "2026-10-01")])
    db_session.commit()

    dated = store.search_document_chunks(db_session, vector, "test-model", observed_at=OBSERVED_AT)
    undated = store.search_document_chunks(db_session, vector, "test-model", observed_at=None)

    assert [chunk.document_id for _, chunk in dated] == ["BEFORE"]
    assert {chunk.document_id for _, chunk in undated} == {"BEFORE", "FUTURE"}


def test_analyze_and_readable_pdf_succeed_with_temporally_governed_rag(db_session):
    actor = Actor("QA Manager", "HSE_MANAGER")
    before = ingest_document(
        db_session,
        actor,
        {
            "title": "Electrical Isolation Standard",
            "organization": "SAJAG QA",
            "version": "1",
            "effective_date": "2026-01-01",
            "source_reference": "QA-ELEC-001",
        },
        "electrical-before.txt",
        b"Before electrical maintenance, isolate the circuit, lock out the energy source, and verify absence of voltage before work starts.",
    )
    future = ingest_document(
        db_session,
        actor,
        {
            "title": "Future Electrical Isolation Standard",
            "organization": "SAJAG QA",
            "version": "2",
            "effective_date": "2026-10-01",
            "source_reference": "QA-ELEC-002",
        },
        "electrical-future.txt",
        b"Future electrical maintenance guidance must not be used for earlier observations.",
    )
    db_session.commit()

    def override_db():
        yield db_session

    main.app.dependency_overrides[get_db] = override_db
    client = TestClient(main.app)
    payload = {
        "description": "During maintenance at an electrical panel, the circuit was not isolated and the absence of voltage was not verified before work started.",
        "site": "Plant A",
        "activity": "Electrical maintenance",
        "observed_at": "2026-09-23T07:11:00",
    }
    try:
        response = client.post("/analyze", headers=MANAGER_HEADERS, json=payload)
        assert response.status_code == 200, response.text
        source_ids = {source["document_id"] for source in response.json()["grounded_guidance"]["retrieved_sources"]}
        assert before.document_id in source_ids
        assert future.document_id not in source_ids

        pdf_bytes = readable_pdf(payload["description"])
        pdf_response = client.post(
            "/reports/upload-pdf",
            headers=MANAGER_HEADERS,
            data={
                "site": payload["site"],
                "activity": payload["activity"],
                "observed_at": payload["observed_at"],
            },
            files={"file": ("electrical-observation.pdf", pdf_bytes, "application/pdf")},
        )
        assert pdf_response.status_code == 200, pdf_response.text
        assert pdf_response.json()["document_extraction"]["text_source"] == "native_pdf"
        pdf_source_ids = {
            source["document_id"]
            for source in pdf_response.json()["grounded_guidance"]["retrieved_sources"]
        }
        assert before.document_id in pdf_source_ids
        assert future.document_id not in pdf_source_ids
    finally:
        main.app.dependency_overrides.clear()
