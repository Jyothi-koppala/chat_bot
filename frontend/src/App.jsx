import { useEffect, useRef, useState } from "react";

const API = "/api";

export default function App() {
  const [pdfCount, setPdfCount] = useState(null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [asking, setAsking] = useState(false);
  const [statusError, setStatusError] = useState("");
  const bottomRef = useRef(null);

  useEffect(() => {
    loadStatus();
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function loadStatus() {
    try {
      const res = await fetch(`${API}/status`);
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Could not load PDF knowledge base");
      setPdfCount(data.pdf_count ?? 0);
      setStatusError(data.errors?.length ? "Some PDFs could not be indexed." : "");
    } catch (err) {
      setStatusError(err.message);
    }
  }

  async function handleAsk(e) {
    e.preventDefault();
    const question = input.trim();
    if (!question || asking) return;

    const history = messages.map(({ role, content }) => ({ role, content }));
    setMessages((m) => [...m, { role: "user", content: question }, { role: "assistant", content: "" }]);
    setInput("");
    setAsking(true);

    try {
      const res = await fetch(`${API}/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question, history }),
      });
      if (!res.ok || !res.body) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || "Request failed");
      }
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n\n");
        buffer = lines.pop();
        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          const payload = JSON.parse(line.slice(6));
          if (payload.error) throw new Error(payload.error);
          if (payload.delta) {
            setMessages((m) => {
              const copy = [...m];
              copy[copy.length - 1] = { role: "assistant", content: copy[copy.length - 1].content + payload.delta };
              return copy;
            });
          }
        }
      }
    } catch (err) {
      setMessages((m) => {
        const copy = [...m];
        copy[copy.length - 1] = { role: "assistant", content: `⚠ ${err.message}` };
        return copy;
      });
    } finally {
      setAsking(false);
      loadStatus();
    }
  }

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">PDF</div>
          <div>
            <div className="brand-title">Doc Chat</div>
            <div className="brand-sub">Ask questions about your local PDF knowledge base using RAG, vector embeddings, and Llama 3.2.</div>
          </div>
        </div>

        <div className="folder-note">
          <strong>Local knowledge base</strong>
          <span>PDFs are managed in the project&apos;s <code>pdf</code> folder. The chat automatically searches across all available PDFs.</span>
        </div>

        <div className="knowledge-status">
          <span className="status-dot" />
          {pdfCount === null ? "Loading knowledge base…" : `${pdfCount} PDF${pdfCount === 1 ? "" : "s"} indexed`}
        </div>
        {statusError && <div className="error-text">{statusError}</div>}

        <div className="hint">Add, replace, or remove PDF files in the local <code>pdf</code> folder. You do not need to select documents in the UI—the question determines which chunks are retrieved.</div>
      </aside>

      <main className="chat">
        <div className="messages">
          {messages.length === 0 && (
            <div className="empty-state">
              <div className="empty-title">Ask anything about your PDFs</div>
              <div className="empty-sub">Your question is searched across the entire local PDF knowledge base.</div>
            </div>
          )}
          {messages.map((m, i) => (
            <div key={i} className={`bubble ${m.role}`}>
              <div className="bubble-role">{m.role === "user" ? "You" : "Llama 3.2"}</div>
              <div className="bubble-content">{m.content || (asking && i === messages.length - 1 ? "…" : "")}</div>
            </div>
          ))}
          <div ref={bottomRef} />
        </div>

        <form className="composer" onSubmit={handleAsk}>
          <input
            type="text"
            placeholder="Ask a question about your PDFs…"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={asking}
            aria-label="Ask a question"
          />
          <button className="send-button" type="submit" disabled={asking || !input.trim()} aria-label="Send question" title="Send question">
            {asking ? "…" : "↵"}
          </button>
        </form>
      </main>
    </div>
  );
}
