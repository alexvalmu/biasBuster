import hashlib

import pymupdf

PDF_MAGIC = b"%PDF-"


class InvalidPdfError(ValueError):
    pass


def sha256_of(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def is_pdf(data: bytes) -> bool:
    # Some generators prepend a few bytes of junk before the header.
    return PDF_MAGIC in data[:1024]


def extract_text(data: bytes, max_chars: int) -> str:
    if not is_pdf(data):
        raise InvalidPdfError("File is not a PDF")
    try:
        with pymupdf.open(stream=data, filetype="pdf") as doc:
            if doc.needs_pass:
                raise InvalidPdfError("PDF is password protected")
            parts: list[str] = []
            total = 0
            for page in doc:
                text = page.get_text("text")
                parts.append(text)
                total += len(text)
                if total >= max_chars:
                    break
    except InvalidPdfError:
        raise
    except Exception as exc:  # pymupdf raises a variety of internal errors
        raise InvalidPdfError(f"Could not read PDF: {exc}") from exc

    text = "\n".join(parts)[:max_chars].strip()
    if len(text) < 500:
        raise InvalidPdfError(
            "PDF has no extractable text (scanned documents are not supported yet)"
        )
    return text
