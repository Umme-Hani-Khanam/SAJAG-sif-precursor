import hashlib
import os
import re
from abc import ABC, abstractmethod
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy.orm import Session

from models import Attachment
from services.roles import Actor


ALLOWED_MEDIA = {
    ".jpg": {"image/jpeg"}, ".jpeg": {"image/jpeg"}, ".png": {"image/png"},
    ".webp": {"image/webp"}, ".pdf": {"application/pdf"}, ".txt": {"text/plain"},
    ".csv": {"text/csv", "application/vnd.ms-excel"},
}


class Storage(ABC):
    @abstractmethod
    def put(self, key: str, content: bytes) -> None: ...

    @abstractmethod
    def path_for(self, key: str) -> Path: ...


class LocalFileStorage(Storage):
    def __init__(self, root: str | Path | None = None):
        self.root = Path(root or os.getenv("UPLOAD_STORAGE_DIR", Path(__file__).resolve().parents[1] / "uploads")).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _resolved(self, key: str) -> Path:
        if "/" in key or "\\" in key or key in {"", ".", ".."}:
            raise ValueError("Invalid storage key.")
        path = (self.root / key).resolve()
        if path.parent != self.root:
            raise ValueError("Storage key escaped configured root.")
        return path

    def put(self, key: str, content: bytes) -> None:
        self._resolved(key).write_bytes(content)

    def path_for(self, key: str) -> Path:
        path = self._resolved(key)
        if not path.is_file():
            raise FileNotFoundError(key)
        return path


def sanitize_filename(filename: str) -> str:
    # Discard every caller-supplied directory component before normalization.
    leaf = filename.replace("\\", "/").split("/")[-1]
    cleaned = re.sub(r"[^A-Za-z0-9._ -]", "_", leaf).strip(" .")
    if not cleaned or cleaned in {".", ".."}:
        raise HTTPException(status_code=400, detail="A valid filename is required.")
    return cleaned[:180]


def validate_file(filename: str, media_type: str, content: bytes, *, allowed_extensions: set[str] | None = None) -> str:
    safe_name = sanitize_filename(filename)
    extension = Path(safe_name).suffix.lower()
    allowed = allowed_extensions or set(ALLOWED_MEDIA)
    if extension not in allowed or extension not in ALLOWED_MEDIA:
        raise HTTPException(status_code=400, detail="This file type is not allowed.")
    if media_type.lower() not in ALLOWED_MEDIA[extension]:
        raise HTTPException(status_code=400, detail="File extension and declared media type do not match.")
    maximum = max(1024, int(os.getenv("MAX_UPLOAD_BYTES", str(10 * 1024 * 1024))))
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    if len(content) > maximum:
        raise HTTPException(status_code=413, detail=f"Upload exceeds the {maximum}-byte limit.")
    signatures = {".pdf": b"%PDF", ".jpg": b"\xff\xd8\xff", ".jpeg": b"\xff\xd8\xff", ".png": b"\x89PNG\r\n\x1a\n", ".webp": b"RIFF"}
    signature = signatures.get(extension)
    if signature and not content.startswith(signature):
        raise HTTPException(status_code=400, detail="File content does not match its declared type.")
    if extension == ".webp" and (len(content) < 12 or content[8:12] != b"WEBP"):
        raise HTTPException(status_code=400, detail="File content is not a valid WEBP container.")
    return safe_name


def save_attachment(
    db: Session, actor: Actor, *, entity_type: str, entity_id: str, filename: str,
    media_type: str, content: bytes, description: str = "", storage: Storage | None = None,
    allowed_extensions: set[str] | None = None,
) -> Attachment:
    safe_name = validate_file(filename, media_type, content, allowed_extensions=allowed_extensions)
    extension = Path(safe_name).suffix.lower()
    key = f"{uuid4().hex}{extension}"
    (storage or LocalFileStorage()).put(key, content)
    item = Attachment(
        attachment_id=f"ATT-{uuid4().hex[:16].upper()}", entity_type=entity_type.upper(),
        entity_id=entity_id, filename=safe_name, storage_key=key, media_type=media_type.lower(),
        size=len(content), uploaded_by=actor.name, uploaded_by_user_id=actor.user_id,
        description=description.strip() or None, sha256=hashlib.sha256(content).hexdigest(),
    )
    db.add(item)
    db.flush()
    return item


def attachment_to_dict(item: Attachment) -> dict:
    # storage_key is intentionally not exposed.
    return {
        "attachment_id": item.attachment_id, "entity_type": item.entity_type,
        "entity_id": item.entity_id, "filename": item.filename, "media_type": item.media_type,
        "size": item.size, "uploaded_by": item.uploaded_by, "uploaded_at": item.uploaded_at,
        "description": item.description, "sha256": item.sha256,
    }
