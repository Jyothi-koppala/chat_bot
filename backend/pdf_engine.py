"""
Local PDF ingestion + RAG retrieval engine.

All PDFs are maintained in the project-level ``pdf/`` folder. PDFs are indexed
independently and cached using a content hash. The chat endpoint searches across
ALL PDFs automatically; the UI does not expose document selection.
"""
import hashlib
import json
import re
from pathlib import Path

import numpy as np
import pymupdf as fitz
from fastembed import TextEmbedding

PROJECT_DIR = Path(__file__).resolve().parent.parent
PDF_DIR = PROJECT_DIR / "pdf"
CACHE_DIR = Path(__file__).resolve().parent / "cache"
PDF_DIR.mkdir(exist_ok=True)
CACHE_DIR.mkdir(exist_ok=True)

CHUNK_SIZE = 900
CHUNK_OVERLAP = 150
TOP_K = 8
PER_DOCUMENT_K = 4

_embedder: TextEmbedding | None = None


def get_embedder() -> TextEmbedding:
    global _embedder
    if _embedder is None:
        _embedder = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
    return _embedder


def file_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:24]


def chunk_text(text: str) -> list[str]:
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []
    chunks = []
    start = 0
    n = len(text)
    while start < n:
        end = min(start + CHUNK_SIZE, n)
        chunks.append(text[start:end])
        if end == n:
            break
        start = end - CHUNK_OVERLAP
    return chunks


def extract_pages(pdf_path: Path) -> list[str]:
    doc = fitz.open(pdf_path)
    try:
        return [page.get_text() for page in doc]
    finally:
        doc.close()


def cache_paths(doc_id: str, create: bool = False):
    d = CACHE_DIR / doc_id
    if create:
        d.mkdir(exist_ok=True)
    return {
        "dir": d,
        "chunks": d / "chunks.json",
        "embeddings": d / "embeddings.npy",
        "meta": d / "meta.json",
    }


def process_pdf(pdf_bytes: bytes, filename: str) -> dict:
    """Extract, chunk, embed and cache one PDF."""
    doc_id = file_hash(pdf_bytes)
    paths = cache_paths(doc_id, create=True)

    if paths["chunks"].exists() and paths["embeddings"].exists() and paths["meta"].exists():
        meta = json.loads(paths["meta"].read_text(encoding="utf-8"))
        if filename and meta.get("filename") != filename:
            meta["filename"] = filename
            paths["meta"].write_text(json.dumps(meta), encoding="utf-8")
        return {"doc_id": doc_id, "cached": True, **meta}

    tmp_path = paths["dir"] / "source.pdf"
    tmp_path.write_bytes(pdf_bytes)
    try:
        pages = extract_pages(tmp_path)
    finally:
        tmp_path.unlink(missing_ok=True)

    all_chunks: list[str] = []
    for page_text in pages:
        all_chunks.extend(chunk_text(page_text))

    if not all_chunks:
        raise ValueError("No extractable text found. This may be a scanned/image-only PDF and needs OCR.")

    embedder = get_embedder()
    vectors = np.array(list(embedder.embed(all_chunks)), dtype=np.float32)
    vectors /= np.linalg.norm(vectors, axis=1, keepdims=True) + 1e-8

    paths["chunks"].write_text(json.dumps(all_chunks), encoding="utf-8")
    np.save(paths["embeddings"], vectors)
    meta = {"filename": filename, "num_pages": len(pages), "num_chunks": len(all_chunks)}
    paths["meta"].write_text(json.dumps(meta), encoding="utf-8")
    return {"doc_id": doc_id, "cached": False, **meta}


def index_local_pdfs() -> tuple[list[dict], list[dict]]:
    """Index every current PDF in the local pdf/ folder."""
    documents, errors = [], []
    for pdf_path in sorted(PDF_DIR.glob("*.pdf"), key=lambda p: p.name.lower()):
        try:
            documents.append(process_pdf(pdf_path.read_bytes(), pdf_path.name))
        except Exception as exc:
            errors.append({"filename": pdf_path.name, "error": str(exc)})
    return documents, errors


def list_local_documents() -> tuple[list[dict], list[dict]]:
    return index_local_pdfs()


def retrieve_many(doc_ids: list[str], question: str, top_k: int = TOP_K) -> list[dict]:
    """Retrieve relevant chunks from the supplied document IDs."""
    if not doc_ids:
        raise ValueError("No indexed documents are available.")
    embedder = get_embedder()
    q_vec = np.array(list(embedder.embed([question]))[0], dtype=np.float32)
    q_vec /= np.linalg.norm(q_vec) + 1e-8
    candidates, seen = [], set()
    for doc_id in doc_ids:
        paths = cache_paths(doc_id)
        if not all(paths[k].exists() for k in ("chunks", "embeddings", "meta")):
            continue
        chunks = json.loads(paths["chunks"].read_text(encoding="utf-8"))
        vectors = np.load(paths["embeddings"])
        meta = json.loads(paths["meta"].read_text(encoding="utf-8"))
        scores = vectors @ q_vec
        local_k = min(PER_DOCUMENT_K, len(chunks))
        for idx in np.argsort(-scores)[:local_k]:
            key = (doc_id, int(idx))
            if key in seen:
                continue
            seen.add(key)
            candidates.append({
                "doc_id": doc_id,
                "filename": meta.get("filename", doc_id),
                "text": chunks[int(idx)],
                "score": float(scores[int(idx)]),
            })
    candidates.sort(key=lambda item: item["score"], reverse=True)
    return candidates[:top_k]


def retrieve_all(question: str, top_k: int = TOP_K) -> list[dict]:
    """Index the current folder and search across every available PDF."""
    documents, errors = index_local_pdfs()
    if not documents:
        if errors:
            raise ValueError("No usable PDFs found: " + "; ".join(f"{e['filename']}: {e['error']}" for e in errors))
        raise ValueError(f"No PDF files found in {PDF_DIR}.")
    results = retrieve_many([d["doc_id"] for d in documents], question, top_k=top_k)
    return results


def retrieve(doc_id: str, question: str, top_k: int = 5) -> list[str]:
    return [item["text"] for item in retrieve_many([doc_id], question, top_k=top_k)]
