import re
from abc import ABC, abstractmethod
from io import BytesIO

from fastapi import HTTPException
from pypdf import PdfReader


class OCRProvider(ABC):
    @abstractmethod
    def extract_pdf(self, content: bytes) -> tuple[str, float | None]: ...

    @abstractmethod
    def extract_image(self, content: bytes) -> tuple[str, float | None]: ...


class TesseractOCRProvider(OCRProvider):
    def extract_pdf(self, content: bytes) -> tuple[str, float | None]:
        try:
            import fitz
            import pytesseract
            from PIL import Image

            pages, confidences = [], []
            document = fitz.open(stream=content, filetype="pdf")
            for page in document:
                pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
                image = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)
                page_text, confidence = _tesseract_image(pytesseract, image)
                pages.append(page_text)
                if confidence is not None:
                    confidences.append(confidence)
            return normalize_text("\n".join(pages)), (sum(confidences) / len(confidences) if confidences else None)
        except Exception as exc:
            raise RuntimeError("OCR engine is unavailable or failed to process the scanned PDF.") from exc

    def extract_image(self, content: bytes) -> tuple[str, float | None]:
        try:
            import pytesseract
            from PIL import Image
            return _tesseract_image(pytesseract, Image.open(BytesIO(content)))
        except Exception as exc:
            raise RuntimeError("OCR engine is unavailable or failed to process the image.") from exc


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _tesseract_image(pytesseract, image) -> tuple[str, float | None]:
    data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
    words, scores = [], []
    for text, raw_confidence in zip(data.get("text", []), data.get("conf", [])):
        cleaned = str(text or "").strip()
        try:
            confidence = float(raw_confidence)
        except (TypeError, ValueError):
            confidence = -1
        if cleaned:
            words.append(cleaned)
        if confidence >= 0:
            scores.append(confidence / 100)
    return normalize_text(" ".join(words)), (round(sum(scores) / len(scores), 4) if scores else None)


def readable(text: str) -> bool:
    normalized = normalize_text(text)
    letters = sum(character.isalpha() for character in normalized)
    return len(normalized) >= 60 and letters / max(1, len(normalized)) >= 0.45


def extract_pdf_with_fallback(content: bytes, provider: OCRProvider | None = None) -> dict:
    try:
        reader = PdfReader(BytesIO(content))
        native = normalize_text("\n".join(page.extract_text() or "" for page in reader.pages))
    except Exception as exc:
        raise HTTPException(status_code=400, detail="PDF could not be parsed.") from exc
    if readable(native):
        return {"text": native, "text_source": "native_pdf", "ocr_confidence": None}
    try:
        text, confidence = (provider or TesseractOCRProvider()).extract_pdf(content)
    except Exception as exc:
        raise HTTPException(status_code=422, detail="Native text was insufficient and OCR failed.") from exc
    if not readable(text):
        raise HTTPException(status_code=422, detail="OCR produced insufficient readable text; analysis was not run.")
    return {"text": normalize_text(text), "text_source": "ocr", "ocr_confidence": confidence}
