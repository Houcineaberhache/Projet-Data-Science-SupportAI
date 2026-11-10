"use client";

import { useState } from "react";

type Source = { doc_name: string; snippet: string; score: number };
type Message = {
  role: "user" | "bot";
  text: string;
  sources?: Source[];
  abstained?: boolean;
  id?: number;
  rated?: 1 | -1;
};

const API_URL = "http://localhost:8000";

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);

  async function send() {
    const text = input.trim();
    if (!text || loading) return;

    setMessages((m) => [...m, { role: "user", text }]);
    setInput("");
    setLoading(true);

    try {
      const res = await fetch(`${API_URL}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text, session_id: sessionId }),
      });
      if (!res.ok) throw new Error("Server error");
      const data = await res.json();
      setSessionId(data.session_id);
      setMessages((m) => [
        ...m,
        {
          role: "bot",
          text: data.answer,
          sources: data.sources,
          abstained: data.is_abstained,
          id: data.message_id,
        },
      ]);
    } catch {
      setMessages((m) => [
        ...m,
        { role: "bot", text: "Server error. Please try again." },
      ]);
    }
    setLoading(false);
  }
    async function rate(i: number, rating: 1 | -1) {
    const m = messages[i];
    if (!m.id || m.rated) return;
    await fetch(`${API_URL}/api/feedback`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message_id: m.id, rating }),
    });
    setMessages((all) =>
      all.map((x, k) => (k === i ? { ...x, rated: rating } : x))
    );
  }

  return (
    <main className="min-h-screen bg-gray-50 text-gray-900 flex justify-center p-4">
      <div className="w-full max-w-2xl flex flex-col h-[90vh] bg-white rounded-xl shadow border">
        <div className="p-4 border-b font-semibold">🛍️ NovaShop Support</div>

        <div className="flex-1 overflow-y-auto p-4 space-y-3">
          {messages.length === 0 && (
            <p className="text-gray-400 text-sm">
              Ask a question, for example: Can I return my product?
            </p>
          )}

          {messages.map((m, i) => (
            <div
              key={i}
              className={m.role === "user" ? "flex justify-end" : "flex justify-start"}
            >
              <div
                className={
                  "max-w-[80%] rounded-lg px-3 py-2 text-sm " +
                  (m.role === "user"
                    ? "bg-blue-600 text-white"
                    : "bg-gray-100 text-gray-900")
                }
              >
                <p>{m.text}</p>

                {m.sources &&
                  m.sources.map((s, j) => (
                    <details key={j} className="mt-2 bg-white border rounded p-2">
                      <summary className="cursor-pointer text-blue-700">
                        📄 {s.doc_name}
                      </summary>
                      <p className="mt-1 text-gray-600">{s.snippet}</p>
                    </details>
                  ))}

                {m.abstained && (
                  <p className="mt-2 text-xs text-gray-500">
                    Would you like to talk to a human agent?
                  </p>
                )}
                                {m.role === "bot" && m.id && (
                  <div className="mt-2 flex gap-2 text-sm">
                    <button
                      onClick={() => rate(i, 1)}
                      className={m.rated === 1 ? "" : "opacity-50 hover:opacity-100"}
                    >
                      👍
                    </button>
                    <button
                      onClick={() => rate(i, -1)}
                      className={m.rated === -1 ? "" : "opacity-50 hover:opacity-100"}
                    >
                      👎
                    </button>
                  </div>
                )}
              </div>
            </div>
          ))}

          {loading && <p className="text-gray-400 text-sm">Typing...</p>}
        </div>

        <div className="p-3 border-t flex gap-2">
          <input
            className="flex-1 border rounded-lg px-3 py-2 text-sm"
            placeholder="Type your question..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && send()}
          />
          <button
            onClick={send}
            className="bg-blue-600 text-white px-4 py-2 rounded-lg text-sm"
          >
            Send
          </button>
        </div>
      </div>
    </main>
  );
}