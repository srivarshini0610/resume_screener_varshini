import os
import re
from pathlib import Path
import pymupdf as fitz


def clean_text(text: str) -> str:
    """
    Cleans extracted text by normalizing whitespace, removing null characters,
    and collapsing excessive empty lines while preserving structural linebreaks.
    """
    if not text:
        return ""
    # Remove null bytes or non-printable controls except tabs/newlines
    text = text.replace("\x00", " ")
    # Replace multiple spaces with a single space
    text = re.sub(r"[ \t]+", " ", text)
    # Replace 3 or more consecutive newlines with 2 newlines
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)
    return text.strip()


def extract_text_from_file(file_path: str) -> str:
    """
    Extracts plain text from a given PDF or TXT resume file.

    Args:
        file_path: Path to the target .pdf or .txt file.

    Returns:
        Cleaned, extracted text string.

    Raises:
        FileNotFoundError: If the specified file does not exist.
        ValueError: If file extension is unsupported, file is empty,
                    or PDF contains no extractable text.
    """
    path = Path(file_path)

    # 1. Validate file existence
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"File not found: '{file_path}'")

    # 2. Check file size
    if path.stat().st_size == 0:
        raise ValueError(f"File is empty (0 bytes): '{file_path}'")

    ext = path.suffix.lower()

    # 3. Handle PDF files
    if ext == ".pdf":
        text_chunks = []
        doc = None
        try:
            doc = fitz.open(str(path))
            if len(doc) == 0:
                raise ValueError(f"PDF contains no pages: '{file_path}'")

            for page_num in range(len(doc)):
                page = doc[page_num]
                page_text = page.get_text("text")
                if page_text:
                    text_chunks.append(page_text.strip())

        except Exception as e:
            if isinstance(e, ValueError):
                raise
            raise ValueError(f"Failed to parse PDF document '{file_path}': {str(e)}") from e
        finally:
            if doc is not None:
                doc.close()

        full_text = "\n\n".join(text_chunks)
        cleaned = clean_text(full_text)
        if not cleaned:
            raise ValueError(f"No extractable text found in PDF: '{file_path}' (may be a scanned image)")
        return cleaned

    # 4. Handle TXT files
    elif ext == ".txt":
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
        except UnicodeDecodeError:
            # Fallback to latin-1 / cp1252 if UTF-8 decode fails
            with open(path, "r", encoding="latin-1") as f:
                content = f.read()

        cleaned = clean_text(content)
        if not cleaned:
            raise ValueError(f"TXT file contains no readable text: '{file_path}'")
        return cleaned

    # 5. Unsupported file format
    else:
        raise ValueError(
            f"Unsupported file format '{ext}'. Only PDF (.pdf) and Text (.txt) files are supported."
        )
