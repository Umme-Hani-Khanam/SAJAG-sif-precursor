import os
import re
from collections import Counter
from datetime import datetime, timezone
from io import BytesIO
from uuid import uuid4

import numpy as np
from fastapi import HTTPException
from pypdf import PdfReader
from sqlalchemy.orm import Session

from models import DocumentChunk, SafetyDocument
from services.audit import append_audit
from services.config import GEMINI_MODEL
from services.embeddings import encode_texts, serialize_embedding
from services.roles import Actor
from services.vector_store import get_vector_store, preferred_document_model


CHUNK_SIZE = 900
CHUNK_OVERLAP = 140
RETRIEVAL_LIMIT = 4
RETRIEVAL_MIN_SCORE = 0.12


def ingest_document(db: Session, actor: Actor, metadata: dict, filename: str, content: bytes) -> SafetyDocument:
    extension = os.path.splitext(filename or "")[1].lower()
    if extension not in {".pdf", ".txt"}:
        raise HTTPException(status_code=400, detail="Knowledge sources must be PDF or TXT files.")
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded knowledge document is empty.")
    document = SafetyDocument(
        document_id=f"DOC-{uuid4().hex[:12].upper()}",
        title=str(metadata.get("title", "")).strip(),
        organization=str(metadata.get("organization", "")).strip(),
        version=str(metadata.get("version", "")).strip() or None,
        effective_date=str(metadata.get("effective_date", "")).strip() or None,
        source_reference=str(metadata.get("source_reference", "")).strip() or None,
        filename=filename,
        uploaded_by=actor.name,
        chunk_count=0,
        status=str(metadata.get("status", "APPROVED")).strip().upper(),
        review_date=str(metadata.get("review_date", "")).strip() or None,
        supersedes_document_id=metadata.get("supersedes_document_id") or None,
        attachment_id=metadata.get("attachment_id") or None,
        indexing_status="pending",
    )
    if not document.title or not document.organization:
        raise HTTPException(status_code=400, detail="Document title and organization are required.")
    db.add(document)
    db.flush()
    index_document_content(db, document, actor, content)
    return document


def index_document_content(
    db: Session, document: SafetyDocument, actor: Actor, content: bytes,
    progress_callback=None,
) -> SafetyDocument:
    extension = os.path.splitext(document.filename or "")[1].lower()
    pages = _extract_pages(extension, content)
    chunks = []
    for page_number, page_text in pages:
        for index, text in enumerate(chunk_text(page_text)):
            chunks.append((page_number, f"Page {page_number}" if page_number else f"Section {index + 1}", text))
    if not chunks:
        document.indexing_status = "failed"
        raise HTTPException(status_code=400, detail="No indexable text was found in the document.")
    vectors, model = encode_texts([text for _, _, text in chunks])
    store = get_vector_store(db)
    for index, ((page, section, text), vector) in enumerate(zip(chunks, vectors), start=1):
        chunk = DocumentChunk(
                chunk_id=f"CHK-{uuid4().hex[:16].upper()}", document_id=document.document_id,
                page=page, section=section, text=text,
                embedding=serialize_embedding(vector), embedding_model=model,
        )
        store.persist_document_embedding(chunk, vector, model)
        db.add(chunk)
        if progress_callback:
            progress_callback(index, len(chunks))
    document.chunk_count = len(chunks)
    document.indexing_status = "completed"
    append_audit(db, actor, "KNOWLEDGE_DOCUMENT_INDEXED", "DOCUMENT", document.document_id, new_value={"title": document.title, "organization": document.organization, "version": document.version, "chunks": len(chunks), "source_reference": document.source_reference})
    db.flush()
    return document


def _extract_pages(extension: str, content: bytes) -> list[tuple[int | None, str]]:
    if extension == ".txt":
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            text = content.decode("latin-1")
        return [(None, _clean(text))]
    try:
        reader = PdfReader(BytesIO(content))
        return [(index, _clean(page.extract_text() or "")) for index, page in enumerate(reader.pages, start=1)]
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Knowledge PDF content could not be parsed.") from exc


def _clean(text: str) -> str:
    return re.sub(r"[ \t]+", " ", str(text or "")).replace("\r", "").strip()


def chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    normalized = re.sub(r"\s+", " ", str(text or "")).strip()
    if not normalized:
        return []
    chunks, start = [], 0
    while start < len(normalized):
        end = min(len(normalized), start + size)
        if end < len(normalized):
            boundary = normalized.rfind(". ", start + size // 2, end)
            if boundary > start:
                end = boundary + 1
        chunks.append(normalized[start:end].strip())
        if end >= len(normalized):
            break
        start = max(start + 1, end - overlap)
    return chunks


def retrieve_guidance(
    db: Session, analysis: dict, limit: int = RETRIEVAL_LIMIT,
    observed_at: datetime | None = None,
) -> dict:
    preferred_model = preferred_document_model(db)
    if not preferred_model:
        return no_source_guidance()
    query = " ".join(
        str(analysis.get(field, ""))
        for field in ("hazard", "energy_source", "exposure_type", "critical_control", "precursor_pattern", "life_saving_rule")
        if analysis.get(field)
    )
    vectors, actual_model = encode_texts([query], force_model=preferred_model)
    selected = [
        pair for pair in get_vector_store(db).search_document_chunks(
            db, vectors[0], actual_model, limit=limit, observed_at=observed_at,
        ) if pair[0] >= RETRIEVAL_MIN_SCORE
    ]
    if not selected:
        result = no_source_guidance()
        if observed_at and db.query(SafetyDocument).filter(
            SafetyDocument.status == "APPROVED", SafetyDocument.effective_date > observed_at.date().isoformat()
        ).count():
            result["temporal_note"] = "Approved sources effective after the observation date were excluded."
        return result
    sources = [source_dict(score, chunk) for score, chunk in selected]
    return {
        "recommended_action": grounded_action(query, selected),
        "retrieved_sources": sources,
        "grounding_status": "grounded",
    }


def source_dict(score: float, chunk: DocumentChunk) -> dict:
    return {
        "document_id": chunk.document_id,
        "document_title": chunk.document.title,
        "organization": chunk.document.organization,
        "version": chunk.document.version,
        "status": chunk.document.status,
        "effective_date": chunk.document.effective_date,
        "section": chunk.section,
        "page": chunk.page,
        "source_reference": chunk.document.source_reference,
        "relevant_snippet": chunk.text[:420],
        "retrieval_score": round(score * 100, 1),
    }


def grounded_action(query: str, selected: list[tuple[float, DocumentChunk]]) -> str:
    key = os.getenv("GEMINI_API_KEY", "").strip()
    evidence = "\n".join(f"[{chunk.chunk_id}] {chunk.text}" for _, chunk in selected)
    if key:
        try:
            from google import genai

            response = genai.Client(api_key=key).models.generate_content(
                model=GEMINI_MODEL,
                contents=(
                    "Write one concise workplace safety action using ONLY the supplied approved evidence. "
                    "Do not add standards, facts, or citations that are not present.\n"
                    f"Safety context: {query}\nApproved evidence:\n{evidence}"
                ),
            )
            value = re.sub(r"\s+", " ", response.text or "").strip()
            if value:
                return value
        except Exception:
            pass
    # Extractive fallback is still strictly grounded in an indexed approved source.
    text = selected[0][1].text
    sentences = re.split(r"(?<=[.!?])\s+", text)
    return next((sentence.strip() for sentence in sentences if len(sentence.strip()) >= 35), text[:300].strip())


def no_source_guidance() -> dict:
    return {
        "recommended_action": "No approved safety reference was retrieved.",
        "retrieved_sources": [],
        "grounding_status": "no_source",
    }


def document_to_dict(document: SafetyDocument, include_chunks: bool = False) -> dict:
    result = {column.name: getattr(document, column.name) for column in document.__table__.columns}
    if include_chunks:
        result["chunks"] = [
            {"chunk_id": chunk.chunk_id, "section": chunk.section, "page": chunk.page, "text": chunk.text}
            for chunk in sorted(document.chunks, key=lambda item: (item.page or 0, item.chunk_id))
        ]
    return result


def transition_document(
    db: Session, document: SafetyDocument, actor: Actor, action: str,
    *, supersedes: SafetyDocument | None = None,
) -> SafetyDocument:
    action = action.upper()
    old = document.status
    if action == "APPROVE":
        if document.indexing_status != "completed":
            raise HTTPException(status_code=409, detail="Document indexing must complete before approval.")
        if document.status not in {"DRAFT", "APPROVED"}:
            raise HTTPException(status_code=409, detail=f"A {document.status} document cannot be approved.")
        document.status = "APPROVED"
        document.approved_by = actor.name
        document.approved_at = datetime.now(timezone.utc)
        if supersedes:
            if supersedes.status != "APPROVED":
                raise HTTPException(status_code=409, detail="Only an approved document may be superseded.")
            supersedes.status = "SUPERSEDED"
            document.supersedes_document_id = supersedes.document_id
    elif action == "RETIRE":
        if document.status not in {"APPROVED", "SUPERSEDED"}:
            raise HTTPException(status_code=409, detail="Only approved or superseded documents may be retired.")
        document.status = "RETIRED"
    else:
        raise HTTPException(status_code=400, detail="Document action must be APPROVE or RETIRE.")
    append_audit(
        db, actor, f"KNOWLEDGE_DOCUMENT_{document.status}", "DOCUMENT", document.document_id,
        old_value={"status": old}, new_value={"status": document.status, "supersedes": document.supersedes_document_id},
    )
    db.flush()
    return document
