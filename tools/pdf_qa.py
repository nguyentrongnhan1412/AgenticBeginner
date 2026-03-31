"""PDF Q&A Tool - Load a PDF and answer questions with grounded citations."""

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

_APP_ROOT = Path(__file__).resolve().parent.parent
# faiss-cpu probes AVX512/AVX2 wheels; missing AVX512 on Windows is normal — suppress noise.
logging.getLogger("faiss").setLevel(logging.WARNING)
logging.getLogger("faiss.loader").setLevel(logging.WARNING)

from langchain_community.document_loaders import PyPDFLoader
from langchain_community.vectorstores import FAISS
from langchain_google_genai import GoogleGenerativeAIEmbeddings

# Global FAISS index — populated by load_pdf()
db = None

# Legacy embedding IDs from older docs / .env files — not valid for current embedContent API.
_LEGACY_EMBEDDING_ALIASES = frozenset(
    {
        "text-embedding-001",
        "text-embedding-004",
        "models/text-embedding-001",
        "models/text-embedding-004",
    }
)
_DEFAULT_EMBEDDING_MODEL = "gemini-embedding-001"


def get_pdf_resource_dir() -> Path:
    """Directory where drop-in PDFs live.

    Set ``PDF_RESOURCE_DIR`` to an absolute path, or a path relative to the app root.
    Default: ``<app_root>/resource``.
    """
    raw = os.environ.get("PDF_RESOURCE_DIR", "").strip()
    if raw:
        p = Path(raw)
        return p.resolve() if p.is_absolute() else (_APP_ROOT / p).resolve()
    return (_APP_ROOT / "resource").resolve()


def list_pdf_resources() -> str:
    """Return a human-readable list of ``*.pdf`` files in the resource directory."""
    d = get_pdf_resource_dir()
    if not d.is_dir():
        return (
            f"No resource folder at: {d}\n"
            "Create it, or set PDF_RESOURCE_DIR to your PDF folder (relative to app root or absolute)."
        )
    pdfs = sorted(d.glob("*.pdf"), key=lambda p: p.name.lower())
    if not pdfs:
        return f"No .pdf files in {d}"
    lines = [f"  - {p.name}" for p in pdfs]
    return f"PDFs in {d}:\n" + "\n".join(lines)


def load_pdf_from_resource(filename: str) -> str:
    """Load a PDF from the resource directory by base file name only.

    Args:
        filename: e.g. ``Security.pdf`` or ``Security`` (.pdf added if missing).

    Returns:
        Success or error message (does not raise).
    """
    name = filename.strip()
    if not name:
        return "Error: empty filename."
    if "/" in name or "\\" in name or name in (".", ".."):
        return "Error: use a base file name only (no paths), e.g. Report.pdf or Report."
    if not name.lower().endswith(".pdf"):
        name = name + ".pdf"

    d = get_pdf_resource_dir().resolve()
    path = (d / name).resolve()
    try:
        path.relative_to(d)
    except ValueError:
        return "Error: invalid file name."

    if not path.is_file():
        return (
            f"Error: not found in resource folder: {name}\n"
            "Use list_pdf_resources_tool to see available files."
        )

    try:
        load_pdf(str(path))
        return f"PDF loaded and indexed from resource: {path.name}"
    except Exception as e:
        logger.exception("load_pdf_from_resource failed")
        return f"Error loading PDF: {e}"


def _resolve_embedding_model() -> str:
    raw = (os.environ.get("GEMINI_EMBEDDING_MODEL") or _DEFAULT_EMBEDDING_MODEL).strip()
    normalized = raw.replace("models/", "", 1) if raw.startswith("models/") else raw
    if normalized in _LEGACY_EMBEDDING_ALIASES or raw in _LEGACY_EMBEDDING_ALIASES:
        logger.warning(
            "GEMINI_EMBEDDING_MODEL=%r is not supported for embeddings; using %r",
            raw,
            _DEFAULT_EMBEDDING_MODEL,
        )
        return _DEFAULT_EMBEDDING_MODEL
    return normalized


def load_pdf(path: str = "sample.pdf") -> None:
    """Load a PDF file into a FAISS vector store for later retrieval.

    Args:
        path: Path to the PDF file.
    """
    global db
    if not os.path.exists(path):
        print(f"[pdf_qa] WARNING: PDF not found at '{path}'. PDF Q&A will be unavailable.")
        return

    logger.info("Loading PDF: %s", path)
    print(f"[pdf_qa] Loading PDF: {path} ...")
    loader = PyPDFLoader(path)
    docs = loader.load_and_split()

    model_id = _resolve_embedding_model()
    embeddings = GoogleGenerativeAIEmbeddings(
        model=model_id,
        google_api_key=os.environ.get("GOOGLE_API_KEY"),
    )

    db = FAISS.from_documents(docs, embeddings)
    logger.info("Indexed %s chunks from %s", len(docs), path)
    print(f"[pdf_qa] Indexed {len(docs)} chunks from '{path}'.")


def query_pdf(question: str, k: int = 4) -> str:
    """Search the PDF index and return relevant excerpts with citation.

    Args:
        question: The question to search for.
        k: Number of top chunks to retrieve.

    Returns:
        Formatted string with page-numbered excerpts, or an error message.
    """
    if db is None:
        return (
            "No PDF is loaded yet. Use load_pdf_tool (path) or load_pdf_resource_tool (file name) "
            "first, then ask again."
        )

    logger.debug("query_pdf k=%s", k)
    results = db.similarity_search(question, k=k)
    if not results:
        return "No relevant content found in the PDF."

    excerpts = []
    for doc in results:
        page = doc.metadata.get("page", "?")
        content = doc.page_content.strip()
        excerpts.append(f"[Page {page + 1}]\n{content}")

    return "\n\n---\n\n".join(excerpts)