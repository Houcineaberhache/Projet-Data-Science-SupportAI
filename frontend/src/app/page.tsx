"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";

type Source = { doc_name: string; snippet: string; score: number };

type Message = {
  role: "user" | "bot";
  text: string;
  sources?: Source[];
  abstained?: boolean;
  id?: number;
  rated?: 1 | -1;
  intent?: string;
  order_status?: string;
};

const API_URL = "http://localhost:8000";

const EXAMPLE_QUESTIONS = [
  {
    icon: "📦",
    label: "Return Policy",
    query: "Can I return my product?",
  },
  {
    icon: "🚚",
    label: "Track Order",
    query: "Where is my order ORD001?",
  },
  {
    icon: "🛡️",
    label: "Warranty",
    query: "What is your warranty policy?",
  },
];

function getOrderStatus(text: string): string | null {
  const match = text.match(/status is \*\*?([a-zA-Z]+)\*\*?/i);
  if (match) return match[1].toLowerCase();
  const lower = text.toLowerCase();
  for (const s of ["shipped", "processing", "delivered", "cancelled"]) {
    if (lower.includes(s)) return s;
  }
  return null;
}

function getStatusBadgeStyle(status: string): string {
  switch (status.toLowerCase()) {
    case "shipped":
      return "bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-950/60 dark:text-blue-300 dark:border-blue-800";
    case "processing":
      return "bg-amber-50 text-amber-800 border-amber-200 dark:bg-amber-950/60 dark:text-amber-300 dark:border-amber-800";
    case "delivered":
      return "bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/60 dark:text-emerald-300 dark:border-emerald-800";
    case "cancelled":
      return "bg-rose-50 text-rose-700 border-rose-200 dark:bg-rose-950/60 dark:text-rose-300 dark:border-rose-800";
    default:
      return "bg-gray-50 text-gray-700 border-gray-200 dark:bg-gray-800 dark:text-gray-300 dark:border-gray-700";
  }
}

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [isDark, setIsDark] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setIsDark(document.documentElement.classList.contains("dark"));
  }, []);

  function toggleTheme() {
    const isCurrentlyDark = document.documentElement.classList.contains("dark");
    const nextDark = !isCurrentlyDark;
    if (nextDark) {
      document.documentElement.classList.add("dark");
      localStorage.setItem("theme", "dark");
    } else {
      document.documentElement.classList.remove("dark");
      localStorage.setItem("theme", "light");
    }
    setIsDark(nextDark);
  }

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  async function handleSend(textToSend?: string) {
    const text = (textToSend ?? input).trim();
    if (!text || loading) return;

    setMessages((m) => [...m, { role: "user", text }]);
    if (!textToSend) setInput("");
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
          intent: data.intent,
          order_status: data.order_status,
        },
      ]);
    } catch {
      setMessages((m) => [
        ...m,
        { role: "bot", text: "We encountered a temporary server error. Please try again." },
      ]);
    }
    setLoading(false);
  }

  async function rate(i: number, rating: 1 | -1) {
    const m = messages[i];
    if (!m.id || m.rated) return;
    try {
      await fetch(`${API_URL}/api/feedback`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message_id: m.id, rating }),
      });
      setMessages((all) =>
        all.map((x, k) => (k === i ? { ...x, rated: rating } : x))
      );
    } catch {
      // feedback fail silently
    }
  }

  return (
    <main className="min-h-screen bg-gray-50 dark:bg-gray-950 text-gray-900 dark:text-gray-100 flex flex-col justify-center items-center p-3 sm:p-6 transition-colors">
      <div className="w-full max-w-3xl flex flex-col h-[94vh] sm:h-[88vh] bg-white dark:bg-gray-900 rounded-2xl shadow-sm border border-gray-200 dark:border-gray-800 overflow-hidden">
        
        {/* Header */}
        <header className="px-5 py-3.5 border-b border-gray-200 dark:border-gray-800 flex items-center justify-between bg-white dark:bg-gray-900 shrink-0">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-indigo-600 flex items-center justify-center text-white font-semibold text-lg shadow-sm">
              🛍️
            </div>
            <div>
              <h1 className="font-semibold text-sm sm:text-base text-gray-900 dark:text-gray-100 flex items-center gap-2">
                NovaShop Support
                <span className="inline-flex items-center gap-1 text-[11px] font-medium text-emerald-700 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-950/60 px-2 py-0.5 rounded-full border border-emerald-200 dark:border-emerald-800">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                  AI Agent
                </span>
              </h1>
              <p className="text-xs text-gray-500 dark:text-gray-400">
                Grounded support with semantic retrieval & order tracking
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <Link
              href="/admin"
              className="text-xs font-medium px-3 py-1.5 rounded-lg text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 border border-gray-200 dark:border-gray-700 transition"
            >
              Admin Dashboard
            </Link>
            <button
              onClick={toggleTheme}
              aria-label="Toggle theme"
              className="w-8 h-8 rounded-lg flex items-center justify-center text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 border border-gray-200 dark:border-gray-700 transition text-sm"
            >
              {isDark ? "☀️" : "🌙"}
            </button>
          </div>
        </header>

        {/* Chat Stream */}
        <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-4">
          {messages.length === 0 && (
            <div className="h-full flex flex-col justify-center items-center text-center max-w-md mx-auto py-8">
              <div className="w-14 h-14 rounded-2xl bg-indigo-50 dark:bg-indigo-950/50 text-indigo-600 dark:text-indigo-400 flex items-center justify-center text-2xl mb-3 shadow-inner">
                💬
              </div>
              <h2 className="text-base sm:text-lg font-semibold text-gray-900 dark:text-gray-100 mb-1">
                How can we help you today?
              </h2>
              <p className="text-xs sm:text-sm text-gray-500 dark:text-gray-400 mb-6">
                Ask about product returns, check your live shipment status, or inquire about warranties.
              </p>

              <div className="w-full space-y-2">
                <p className="text-[11px] font-semibold tracking-wider text-gray-400 dark:text-gray-500 uppercase text-left pl-1">
                  Suggested queries
                </p>
                <div className="grid grid-cols-1 gap-2">
                  {EXAMPLE_QUESTIONS.map((ex, idx) => (
                    <button
                      key={idx}
                      onClick={() => handleSend(ex.query)}
                      className="w-full flex items-center gap-3 p-3 rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900/60 hover:border-indigo-300 dark:hover:border-indigo-700 hover:bg-indigo-50/50 dark:hover:bg-indigo-950/30 text-left transition text-xs sm:text-sm shadow-xs group"
                    >
                      <span className="text-base p-1.5 rounded-lg bg-gray-50 dark:bg-gray-800 group-hover:bg-white dark:group-hover:bg-gray-700 transition">
                        {ex.icon}
                      </span>
                      <div className="flex-1 min-w-0">
                        <span className="font-medium text-gray-900 dark:text-gray-100 block truncate">
                          {ex.query}
                        </span>
                        <span className="text-[11px] text-gray-400 dark:text-gray-500">
                          {ex.label}
                        </span>
                      </div>
                      <span className="text-gray-400 group-hover:text-indigo-600 dark:group-hover:text-indigo-400 transition font-mono">
                        →
                      </span>
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}

          {messages.map((m, i) => (
            <div
              key={i}
              className={`flex ${m.role === "user" ? "justify-end" : "justify-start"} transition-all`}
            >
              <div
                className={
                  "max-w-[85%] sm:max-w-[78%] rounded-2xl px-4 py-3 text-sm shadow-xs transition-colors " +
                  (m.role === "user"
                    ? "bg-indigo-600 text-white rounded-br-xs"
                    : "bg-white dark:bg-gray-900/90 text-gray-800 dark:text-gray-200 border border-gray-200/80 dark:border-gray-800 rounded-bl-xs")
                }
              >
                {/* Status Badge for Order Tracking */}
                {m.role === "bot" && m.intent === "order_tracking" && !m.abstained && (() => {
                  const status = m.order_status || getOrderStatus(m.text);
                  return status ? (
                    <div className="mb-2">
                      <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold border ${getStatusBadgeStyle(status)}`}>
                        <span className="w-1.5 h-1.5 rounded-full bg-current" />
                        {status.toUpperCase()}
                      </span>
                    </div>
                  ) : null;
                })()}

                {/* Message Body */}
                <p className="leading-relaxed whitespace-pre-wrap">{m.text}</p>

                {/* Sources Cards */}
                {m.sources && m.sources.length > 0 && (
                  <div className="mt-3 pt-2.5 border-t border-gray-100 dark:border-gray-800/80 space-y-2">
                    <p className="text-[11px] font-semibold uppercase tracking-wider text-gray-400 dark:text-gray-500">
                      Sources & Evidence
                    </p>
                    <div className="space-y-1.5">
                      {m.sources.map((s, j) => (
                        <div
                          key={j}
                          className="p-2.5 rounded-xl bg-gray-50 dark:bg-gray-800/60 border border-gray-200/70 dark:border-gray-700/60 text-xs text-gray-600 dark:text-gray-300"
                        >
                          <div className="flex items-center justify-between gap-2 mb-1">
                            <span className="font-medium text-gray-800 dark:text-gray-200 flex items-center gap-1.5 truncate">
                              📄 {s.doc_name}
                            </span>
                            <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-indigo-50 dark:bg-indigo-950 text-indigo-600 dark:text-indigo-400 border border-indigo-200/50 dark:border-indigo-800/50 shrink-0">
                              {Math.round(s.score * 100)}% match
                            </span>
                          </div>
                          <p className="text-gray-500 dark:text-gray-400 leading-normal line-clamp-2">
                            {s.snippet}
                          </p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Abstained Notice */}
                {m.abstained && (
                  <div className="mt-2 text-xs text-amber-700 dark:text-amber-400 bg-amber-50 dark:bg-amber-950/40 border border-amber-200/60 dark:border-amber-800/60 rounded-lg p-2">
                    ℹ️ Information not found in knowledge base. Would you like to connect with a human agent?
                  </div>
                )}

                {/* Feedback Controls */}
                {m.role === "bot" && m.id && (
                  <div className="mt-2.5 pt-1.5 border-t border-gray-100 dark:border-gray-800 flex items-center justify-between text-xs text-gray-400 dark:text-gray-500">
                    <span>Was this helpful?</span>
                    <div className="flex items-center gap-1">
                      <button
                        onClick={() => rate(i, 1)}
                        aria-label="Thumbs up"
                        className={`p-1 rounded-md hover:bg-gray-100 dark:hover:bg-gray-800 transition ${
                          m.rated === 1 ? "text-emerald-600 dark:text-emerald-400 font-bold bg-emerald-50 dark:bg-emerald-950/50" : ""
                        }`}
                      >
                        👍
                      </button>
                      <button
                        onClick={() => rate(i, -1)}
                        aria-label="Thumbs down"
                        className={`p-1 rounded-md hover:bg-gray-100 dark:hover:bg-gray-800 transition ${
                          m.rated === -1 ? "text-rose-600 dark:text-rose-400 font-bold bg-rose-50 dark:bg-rose-950/50" : ""
                        }`}
                      >
                        👎
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </div>
          ))}

          {/* Typing Indicator */}
          {loading && (
            <div className="flex justify-start">
              <div className="bg-white dark:bg-gray-900 border border-gray-200/80 dark:border-gray-800 rounded-2xl rounded-bl-xs px-4 py-3 shadow-xs">
                <div className="flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-indigo-600 animate-bounce" style={{ animationDelay: "0ms" }} />
                  <span className="w-2 h-2 rounded-full bg-indigo-600 animate-bounce" style={{ animationDelay: "150ms" }} />
                  <span className="w-2 h-2 rounded-full bg-indigo-600 animate-bounce" style={{ animationDelay: "300ms" }} />
                </div>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Input Footer */}
        <div className="p-3 sm:p-4 border-t border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleSend();
            }}
            className="flex items-center gap-2 bg-gray-50 dark:bg-gray-800/70 border border-gray-200 dark:border-gray-700/80 rounded-xl px-3 py-1.5 focus-within:ring-2 focus-within:ring-indigo-500 focus-within:border-transparent transition"
          >
            <input
              className="flex-1 bg-transparent py-2 text-sm text-gray-900 dark:text-gray-100 placeholder-gray-400 dark:placeholder-gray-500 focus:outline-none"
              placeholder="Ask about returns, policies, or type an order ID (e.g. ORD001)..."
              value={input}
              onChange={(e) => setInput(e.target.value)}
              disabled={loading}
            />
            <button
              type="submit"
              disabled={!input.trim() || loading}
              className="bg-indigo-600 hover:bg-indigo-700 disabled:opacity-40 disabled:cursor-not-allowed text-white px-3.5 py-1.5 rounded-lg text-sm font-medium transition flex items-center gap-1 shadow-xs"
            >
              Send
            </button>
          </form>
          <div className="mt-2 text-center text-[11px] text-gray-400 dark:text-gray-500">
            SupportAI prototype · Answers verified with knowledge base retrieval
          </div>
        </div>

      </div>
    </main>
  );
}
