from certifi import contents
import fitz
from pydantic import BaseModel, field_validator
from fastapi import UploadFile

MAX_TEXT_LENGTH = 8_000_000
MAX_FILE_SIZE = 1024*1024*5     # 5MB in bytes
ALLOWED_MIME = ["text/plain", "application/pdf"]


class TextInput(BaseModel):
    text: str

    @field_validator("text")
    @classmethod
    def validate_text(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Text cannot be empty.")
        if len(v) > MAX_TEXT_LENGTH:
            raise ValueError(
                f"Text exceeds {MAX_TEXT_LENGTH} characters "
                f"(got {len(v)})."
            )
        return v
    

def _extract_pdf_text(data: bytes) -> str:
    """Extract plain text from PDF bytes using PyMuPDF."""
    try:
        doc = fitz.open(stream=data, filetype="pdf")
    except Exception as e:
        raise ValueError(f"Failed to parse PDF: {e}")
    
    if doc.is_encrypted:
        raise ValueError("Encrypted PDFs are not supported.")
    
    pages = [page.get_text() for page in doc]
    doc.close()
    text = "\n".join(pages).strip()

    if not text:
        raise ValueError("PDF file contains no extractable text.")
    return text


async def validate_upload(file: UploadFile) -> str:
    if file.content_type not in ALLOWED_MIME:
        raise ValueError(f"Only .txt files are allowed (got {file.content_type}).")
    
    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise ValueError(f"File size exceeds 1MB (got {len(contents)} bytes).")
    

    if file.content_type == "application/pdf":
        text = _extract_pdf_text(contents)
    else:
        try:
            text = contents.decode("utf-8")
        except UnicodeDecodeError:
            text = contents.decode("latin-1")  # fallback
        text = text.strip()
        if not text:
            raise ValueError("File cannot be empty.")
            
    if len(text) > MAX_TEXT_LENGTH:
        raise ValueError(
            f"Text in file exceeds {MAX_TEXT_LENGTH} characters "
            f"(got {len(text)})."
        )
    return text