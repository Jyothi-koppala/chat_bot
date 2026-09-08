# PDF Chatbot — Local PDF Folder + RAG + Ollama/Llama 3.2

This local POC answers questions from a PDF knowledge base stored in the project's `pdf/` folder.

## Key behavior

- Put any number of `.pdf` files in `pdf/`.
- The frontend does **not** display PDF filenames and does not ask the user to select files.
- Ask a question; the backend searches across all indexed PDFs automatically.
- PDFs are extracted with PyMuPDF, split into overlapping chunks, embedded with `BAAI/bge-small-en-v1.5` using FastEmbed, and cached locally as NumPy vectors.
- Retrieval uses cosine similarity and returns the most relevant chunks across the entire PDF set.
- The retrieved context is sent to local Ollama running `llama3.2`.
- No Anthropic API key or cloud LLM is required.

## Adding or replacing PDFs

Copy PDFs directly into:

```text
pdf/
```

Use descriptive, unique filenames. For example:

```text
pdf/
  HDFC_ERGO_Group_Health_Insurance.pdf
  SBI_General_Super_Health_Insurance.pdf
  ICICI_Lombard_Complete_Health_Insurance.pdf
```

You can add more PDFs at any time. Restarting the app re-indexes the current folder; unchanged files reuse their content-hash cache. Each question also refreshes the current folder index before retrieval, so new/changed PDFs are picked up automatically.

## RAG flow

```text
Local pdf/ folder
  -> PyMuPDF text extraction
  -> 900-character chunks / 150 overlap
  -> BGE-small vector embeddings
  -> local embeddings.npy cache
  -> question embedding
  -> cosine similarity across all PDFs
  -> top relevant chunks
  -> RAG prompt
  -> Ollama / Llama 3.2
  -> streaming answer in React
```

## Run on Windows

1. Install Python 3.11, Node.js 18+, and Ollama.
2. Make sure `py -3.11 --version`, `node --version`, and `ollama --version` work.
3. Make sure `ollama list` contains `llama3.2` (run `ollama pull llama3.2` if needed).
4. Open PowerShell in the project folder.
5. Run:

```powershell
.\start.bat
```

The script creates `backend/.venv`, installs dependencies, builds the React frontend, and starts FastAPI on port 8000.

Open `http://localhost:8000`.

## Local storage

Generated embeddings are stored under `backend/cache/`. They are local and are not sent to Ollama. The LLM receives only the retrieved text excerpts.
