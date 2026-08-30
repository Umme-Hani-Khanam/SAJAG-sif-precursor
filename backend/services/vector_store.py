"""Database-specific vector persistence and retrieval.

SQLite intentionally uses deterministic in-process cosine search for demo/tests.
PostgreSQL uses pgvector's distance operator so the database can use an HNSW/IVFFlat
index without loading the corpus into application memory.
"""

from abc import ABC, abstractmethod
from collections import Counter
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.orm import Session

from models import DocumentChunk, HistoricalAnalysis, SafetyDocument
from services.embeddings import cosine_score, deserialize_embedding, serialize_embedding


class VectorStore(ABC):
    @abstractmethod
    def persist_report_embedding(self, analysis: HistoricalAnalysis, vector, model: str) -> None: ...

    @abstractmethod
    def persist_document_embedding(self, chunk: DocumentChunk, vector, model: str) -> None: ...

    @abstractmethod
    def search_similar_reports(self, db: Session, vector, model: str, limit: int = 5): ...

    @abstractmethod
    def search_document_chunks(
        self, db: Session, vector, model: str, limit: int = 4, observed_at: datetime | None = None,
    ): ...


class SQLiteVectorStore(VectorStore):
    def persist_report_embedding(self, analysis, vector, model):
        analysis.embedding = serialize_embedding(vector)
        analysis.embedding_vector = analysis.embedding
        analysis.embedding_model = model

    def persist_document_embedding(self, chunk, vector, model):
        chunk.embedding = serialize_embedding(vector)
        chunk.embedding_vector = chunk.embedding
        chunk.embedding_model = model

    def search_similar_reports(self, db, vector, model, limit=5):
        scored = []
        for item in db.query(HistoricalAnalysis).filter(HistoricalAnalysis.embedding_model == model).all():
            candidate = deserialize_embedding(item.embedding)
            if candidate is not None and candidate.shape == vector.shape:
                scored.append((cosine_score(vector, candidate), item))
        return sorted(scored, key=lambda pair: (-pair[0], pair[1].report_id))[:limit]

    def search_document_chunks(self, db, vector, model, limit=4, observed_at=None):
        query = (
            db.query(DocumentChunk).join(DocumentChunk.document)
            .filter(SafetyDocument.status == "APPROVED", DocumentChunk.embedding_model == model)
        )
        if observed_at is not None:
            query = query.filter(
                (SafetyDocument.effective_date.is_(None)) |
                (SafetyDocument.effective_date == "") |
                (SafetyDocument.effective_date <= observed_at.date().isoformat())
            )
        scored = []
        for chunk in query.all():
            candidate = deserialize_embedding(chunk.embedding)
            if candidate is not None and candidate.shape == vector.shape:
                scored.append((cosine_score(vector, candidate), chunk))
        return sorted(scored, key=lambda pair: (-pair[0], pair[1].chunk_id))[:limit]


class PostgresVectorStore(VectorStore):
    """pgvector adapter. Its SQL is public for adapter/integration verification."""

    DOCUMENT_SEARCH_SQL = """
        SELECT dc.chunk_id, 1 - (dc.embedding_vector <=> CAST(:query_vector AS vector)) AS score
        FROM document_chunks dc JOIN safety_documents sd ON sd.document_id = dc.document_id
        WHERE sd.status = 'APPROVED' AND dc.embedding_model = :model
          AND (:observed_date IS NULL OR sd.effective_date IS NULL OR sd.effective_date = '' OR sd.effective_date <= :observed_date)
        ORDER BY dc.embedding_vector <=> CAST(:query_vector AS vector) LIMIT :limit
    """
    REPORT_SEARCH_SQL = """
        SELECT report_id, 1 - (embedding_vector <=> CAST(:query_vector AS vector)) AS score
        FROM historical_analyses WHERE status = 'analysed' AND embedding_model = :model
        ORDER BY embedding_vector <=> CAST(:query_vector AS vector) LIMIT :limit
    """

    @staticmethod
    def _literal(vector) -> str:
        return "[" + ",".join(f"{float(value):.10g}" for value in vector) + "]"

    def persist_report_embedding(self, analysis, vector, model):
        analysis.embedding = serialize_embedding(vector)
        analysis.embedding_model = model
        analysis.embedding_vector = [float(value) for value in vector]

    def persist_document_embedding(self, chunk, vector, model):
        chunk.embedding = serialize_embedding(vector)
        chunk.embedding_model = model
        chunk.embedding_vector = [float(value) for value in vector]

    def search_similar_reports(self, db, vector, model, limit=5):
        rows = db.execute(text(self.REPORT_SEARCH_SQL), {"query_vector": self._literal(vector), "model": model, "limit": limit}).all()
        return [(float(row.score), db.get(HistoricalAnalysis, row.report_id)) for row in rows]

    def search_document_chunks(self, db, vector, model, limit=4, observed_at=None):
        rows = db.execute(text(self.DOCUMENT_SEARCH_SQL), {
            "query_vector": self._literal(vector), "model": model, "limit": limit,
            "observed_date": observed_at.date().isoformat() if observed_at else None,
        }).all()
        return [(float(row.score), db.get(DocumentChunk, row.chunk_id)) for row in rows]


def get_vector_store(db: Session) -> VectorStore:
    return PostgresVectorStore() if db.bind and db.bind.dialect.name == "postgresql" else SQLiteVectorStore()


def preferred_document_model(db: Session) -> str | None:
    counts = Counter(
        row[0] for row in db.query(DocumentChunk.embedding_model).join(DocumentChunk.document)
        .filter(SafetyDocument.status == "APPROVED").all()
    )
    return counts.most_common(1)[0][0] if counts else None
