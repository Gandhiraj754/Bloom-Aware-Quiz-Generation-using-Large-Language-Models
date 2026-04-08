
import io


def extract_text_from_pdf(uploaded_file) -> tuple[str, int]:
    """
    Extract text from a Streamlit UploadedFile (PDF).
    Returns (extracted_text, page_count).
    Tries pdfplumber first (better), falls back to PyPDF2.
    """
    file_bytes = uploaded_file.read()
    uploaded_file.seek(0)  # reset so it can be read again if needed

    try:
        import pdfplumber
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            pages     = pdf.pages
            page_count = len(pages)
            text = "\n\n".join(
                (p.extract_text() or "") for p in pages
            ).strip()
            if text:
                return text, page_count
    except ImportError:
        pass
    except Exception:
        pass


    try:
        import PyPDF2
        reader     = PyPDF2.PdfReader(io.BytesIO(file_bytes))
        page_count = len(reader.pages)
        text = "\n\n".join(
            (p.extract_text() or "") for p in reader.pages
        ).strip()
        return text, page_count
    except ImportError:
        raise ImportError(
            "No PDF library found. Install one:\n"
            "  pip install pdfplumber\n"
            "or\n"
            "  pip install PyPDF2"
        )
    except Exception as e:
        raise RuntimeError(f"Could not read PDF: {e}")


def chunk_text(text: str, max_chars: int = 4000) -> str:
    """
    Return the first `max_chars` characters of text —
    enough context for the LLM without hitting token limits.
    """
    if len(text) <= max_chars:
        return text
    # Cut at a sentence boundary if possible
    cut = text[:max_chars]
    last_period = cut.rfind(".")
    if last_period > max_chars * 0.7:
        cut = cut[: last_period + 1]
    return cut + "\n\n[Content truncated for length]"
