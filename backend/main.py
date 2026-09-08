import json
import os
from pathlib import Path

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import pdf_engine

load_dotenv()

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2")
OLLAMA_TIMEOUT = float(os.environ.get("OLLAMA_TIMEOUT_SECONDS", "300"))

app = FastAPI(title="PDF Chatbot - Local Folder RAG + Ollama")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class AskRequest(BaseModel):
    question: str
    history: list[dict] = Field(default_factory=list)


def ollama_messages(req: AskRequest, context: str) -> list[dict]:
    system_prompt = (
        "You answer questions using ONLY the provided PDF excerpts. "
        "The excerpts come from the local PDF knowledge base. "
        "Use source document names to distinguish documents when useful. "
        "If the excerpts do not contain the answer, say so plainly instead of guessing. "
        "Do not invent facts or rely on outside knowledge."
    )
    messages = [{"role": "system", "content": system_prompt}]
    for item in req.history:
        role, content = item.get("role"), item.get("content")
        if role in {"user", "assistant"} and isinstance(content, str) and content.strip():
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": f"PDF excerpts:\n\n{context}\n\n---\n\nQuestion: {req.question}"})
    return messages


def ollama_is_reachable() -> bool:
    try:
        with httpx.Client(timeout=5.0) as client:
            response = client.get(f"{OLLAMA_BASE_URL}/api/tags")
            response.raise_for_status()
        return True
    except Exception:
        return False


@app.on_event("startup")
def index_startup_pdfs():
    documents, errors = pdf_engine.index_local_pdfs()
    print(f"Indexed {len(documents)} local PDF(s).")
    for error in errors:
        print(f"PDF index error: {error['filename']}: {error['error']}")


@app.get("/api/health")
def health():
    return {"ok": True, "ollama_reachable": ollama_is_reachable(), "model": OLLAMA_MODEL, "pdf_folder": str(pdf_engine.PDF_DIR)}


@app.get("/api/status")
def status():
    docs, errors = pdf_engine.list_local_documents()
    return {"pdf_count": len(docs), "errors": errors, "message": "Questions search across all PDFs in the local pdf folder."}


@app.post("/api/ask")
async def ask(req: AskRequest):
    question = req.question.strip()
    if not question:
        raise HTTPException(400, "Question cannot be empty.")
    try:
        retrieved = pdf_engine.retrieve_all(question)
    except ValueError as exc:
        raise HTTPException(404, str(exc))

    context = "\n\n---\n\n".join(
        f"Source document: {item['filename']}\n{item['text']}" for item in retrieved
    )
    payload = {"model": OLLAMA_MODEL, "messages": ollama_messages(req, context), "stream": True, "options": {"temperature": 0.1}}

    def event_stream():
        try:
            with httpx.Client(timeout=OLLAMA_TIMEOUT) as client:
                with client.stream("POST", f"{OLLAMA_BASE_URL}/api/chat", json=payload) as response:
                    if response.status_code >= 400:
                        body = response.read().decode("utf-8", errors="replace")
                        try:
                            detail = json.loads(body).get("error", body)
                        except json.JSONDecodeError:
                            detail = body
                        yield f"data: {json.dumps({'error': f'Ollama error: {detail}'})}\n\n"
                        return
                    for line in response.iter_lines():
                        if not line:
                            continue
                        try:
                            chunk = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        if chunk.get("error"):
                            yield f"data: {json.dumps({'error': chunk['error']})}\n\n"
                            return
                        text = chunk.get("message", {}).get("content", "")
                        if text:
                            yield f"data: {json.dumps({'delta': text})}\n\n"
                        if chunk.get("done"):
                            yield f"data: {json.dumps({'done': True})}\n\n"
                            return
        except httpx.ConnectError:
            yield f"data: {json.dumps({'error': 'Cannot connect to Ollama. Start Ollama and make sure it is listening on http://localhost:11434.'})}\n\n"
        except httpx.ReadTimeout:
            yield f"data: {json.dumps({'error': 'Ollama timed out while generating the answer.'})}\n\n"
        except Exception as exc:
            yield f"data: {json.dumps({'error': str(exc)})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


FRONTEND_DIST = Path(__file__).parent.parent / "frontend" / "dist"
if FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
