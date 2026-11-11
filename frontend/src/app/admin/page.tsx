"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

const API_URL = "http://localhost:8000";

type Stats = {
  total_questions: number;
  avg_latency_ms: number;
  abstained: number;
  intents: Record<string, number>;
  thumbs_up: number;
  thumbs_down: number;
};

type Doc = { id: number; title: string; chunks_count: number; uploaded_at: string };

type Row = {
  id: number;
  question: string;
  intent: string;
  latency_ms: number;
  is_abstained: boolean;
};

export default function Admin() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [docs, setDocs] = useState<Doc[]>([]);
  const [history, setHistory] = useState<Row[]>([]);
  const [msg, setMsg] = useState("");
  const [dragging, setDragging] = useState(false);
  const [isDark, setIsDark] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [lastRefreshed, setLastRefreshed] = useState<string | null>(null);

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

  async function load() {
    setRefreshing(true);
    const start = Date.now();
    try {
      const ts = Date.now();
      const [s, d, h] = await Promise.all([
        fetch(`${API_URL}/api/admin/stats?t=${ts}`, { cache: "no-store" }).then((r) => r.json()),
        fetch(`${API_URL}/api/admin/documents?t=${ts}`, { cache: "no-store" }).then((r) => r.json()),
        fetch(`${API_URL}/api/admin/history?t=${ts}`, { cache: "no-store" }).then((r) => r.json()),
      ]);
      setStats(s);
      setDocs(d);
      setHistory(h);
      setLastRefreshed(new Date().toLocaleTimeString());
    } catch {
      setMsg("Failed to connect to backend API.");
    } finally {
      const elapsed = Date.now() - start;
      if (elapsed < 400) {
        await new Promise((resolve) => setTimeout(resolve, 400 - elapsed));
      }
      setRefreshing(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function upload(file: File) {
    setMsg("Uploading document...");
    const form = new FormData();
    form.append("file", file);
    try {
      const res = await fetch(`${API_URL}/api/admin/upload`, {
        method: "POST",
        body: form,
      });
      if (res.ok) {
        const data = await res.json();
        setMsg(`✅ Successfully indexed "${data.title}" (${data.chunks_count} chunks)`);
        load();
      } else {
        const err = await res.json();
        setMsg(`❌ ${err.detail || "Upload failed"}`);
      }
    } catch {
      setMsg("❌ Network error uploading document");
    }
  }

  return (
    <main className="min-h-screen bg-gray-50 dark:bg-gray-950 text-gray-900 dark:text-gray-100 p-4 sm:p-8 transition-colors">
      <div className="max-w-5xl mx-auto space-y-6">
        
        {/* Navigation / Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2 border-b border-gray-200 dark:border-gray-800">
          <div>
            <Link
              href="/"
              className="text-xs font-medium text-indigo-600 dark:text-indigo-400 hover:underline flex items-center gap-1 mb-1"
            >
              ← Back to Support Chat
            </Link>
            <h1 className="text-xl sm:text-2xl font-bold tracking-tight flex items-center gap-2">
              🛠️ NovaShop Admin & Metrics
            </h1>
            <p className="text-xs sm:text-sm text-gray-500 dark:text-gray-400">
              Real-time monitoring of support conversations, latencies, and knowledge base documents
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {lastRefreshed && (
              <span className="inline-flex items-center gap-1 text-[11px] font-mono text-emerald-700 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-950/60 px-2 py-1 rounded-md border border-emerald-200 dark:border-emerald-800">
                <span>✓</span> Updated {lastRefreshed}
              </span>
            )}
            <button
              onClick={() => {
                setMsg("");
                load();
              }}
              disabled={refreshing}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 hover:bg-gray-100 dark:hover:bg-gray-800 disabled:opacity-50 transition shadow-xs cursor-pointer"
            >
              <span className={refreshing ? "animate-spin inline-block" : "inline-block"}>🔄</span>
              <span>{refreshing ? "Refreshing..." : "Refresh"}</span>
            </button>
            <button
              onClick={toggleTheme}
              aria-label="Toggle theme"
              className="w-8 h-8 rounded-lg flex items-center justify-center text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 border border-gray-200 dark:border-gray-700 transition text-sm cursor-pointer"
            >
              {isDark ? "☀️" : "🌙"}
            </button>
          </div>
        </div>

        {/* Stats Grid */}
        {stats && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3.5">
            <StatCard
              icon="💬"
              label="Total Questions"
              value={stats.total_questions}
              subtext="Logged queries"
            />
            <StatCard
              icon="⚡"
              label="Avg Latency"
              value={`${stats.avg_latency_ms} ms`}
              subtext="Response time"
            />
            <StatCard
              icon="❓"
              label="Unanswered"
              value={stats.abstained}
              subtext="Fallback / Abstentions"
            />
            <StatCard
              icon="⭐"
              label="Feedback"
              value={`${stats.thumbs_up} 👍 / ${stats.thumbs_down} 👎`}
              subtext="User ratings"
            />
          </div>
        )}

        {/* Intents Distribution */}
        {stats && (
          <div className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-2xl p-5 shadow-xs">
            <h2 className="text-sm font-semibold mb-3 flex items-center gap-2">
              <span>🎯</span> Intent Distribution
            </h2>
            <div className="flex flex-wrap gap-2">
              {Object.entries(stats.intents).length === 0 ? (
                <p className="text-xs text-gray-400">No intents logged yet.</p>
              ) : (
                Object.entries(stats.intents).map(([k, v]) => (
                  <span
                    key={k}
                    className="inline-flex items-center gap-1.5 bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg px-2.5 py-1 text-xs font-medium text-gray-700 dark:text-gray-300"
                  >
                    <span>{k}</span>
                    <span className="bg-indigo-100 dark:bg-indigo-950 text-indigo-700 dark:text-indigo-400 px-1.5 py-0.2 rounded-md font-mono text-[11px]">
                      {v}
                    </span>
                  </span>
                ))
              )}
            </div>
          </div>
        )}

        {/* Document Ingestion Card */}
        <div className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-2xl p-5 shadow-xs space-y-3">
          <h2 className="text-sm font-semibold flex items-center gap-2">
            <span>📥</span> Ingest Knowledge Document
          </h2>
          <div
            onDragOver={(e) => {
              e.preventDefault();
              setDragging(true);
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={(e) => {
              e.preventDefault();
              setDragging(false);
              const f = e.dataTransfer.files[0];
              if (f) upload(f);
            }}
            className={`border-2 border-dashed rounded-xl p-6 sm:p-8 text-center transition-all ${
              dragging
                ? "border-indigo-500 bg-indigo-50/50 dark:bg-indigo-950/30"
                : "border-gray-200 dark:border-gray-800 bg-gray-50/50 dark:bg-gray-800/20"
            }`}
          >
            <div className="text-3xl mb-2">📄</div>
            <p className="text-xs sm:text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Drag and drop policy documents here, or browse files
            </p>
            <p className="text-[11px] text-gray-400 dark:text-gray-500 mb-4">
              Supported formats: .PDF, .DOCX, .TXT
            </p>
            <label className="inline-flex items-center px-3.5 py-1.5 rounded-lg text-xs font-medium bg-indigo-600 hover:bg-indigo-700 text-white cursor-pointer transition shadow-xs">
              Choose File
              <input
                type="file"
                accept=".pdf,.docx,.txt"
                onChange={(e) => e.target.files?.[0] && upload(e.target.files[0])}
                className="hidden"
              />
            </label>
            {msg && (
              <p className="mt-3 text-xs font-medium text-indigo-600 dark:text-indigo-400">
                {msg}
              </p>
            )}
          </div>
        </div>

        {/* Documents Table */}
        <div className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-2xl p-5 shadow-xs">
          <h2 className="text-sm font-semibold mb-3 flex items-center justify-between">
            <span className="flex items-center gap-2">
              <span>📚</span> Indexed Documents ({docs.length})
            </span>
          </h2>
          {docs.length === 0 ? (
            <p className="text-xs text-gray-400 py-4 text-center">No documents indexed yet.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-xs text-left">
                <thead className="bg-gray-50 dark:bg-gray-800/50 text-gray-500 dark:text-gray-400 uppercase text-[10px] tracking-wider font-semibold border-b border-gray-200 dark:border-gray-800">
                  <tr>
                    <th className="py-2.5 px-3">Title</th>
                    <th className="py-2.5 px-3">Chunks</th>
                    <th className="py-2.5 px-3">Uploaded At</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100 dark:divide-gray-800/80">
                  {docs.map((d) => (
                    <tr key={d.id} className="hover:bg-gray-50/50 dark:hover:bg-gray-800/30 transition">
                      <td className="py-2.5 px-3 font-medium text-gray-800 dark:text-gray-200 flex items-center gap-1.5">
                        <span>📄</span> {d.title}
                      </td>
                      <td className="py-2.5 px-3">
                        <span className="px-2 py-0.5 rounded-full text-[10px] font-mono bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-300 border border-gray-200 dark:border-gray-700">
                          {d.chunks_count} chunks
                        </span>
                      </td>
                      <td className="py-2.5 px-3 text-gray-400 dark:text-gray-500 font-mono text-[11px]">
                        {new Date(d.uploaded_at).toLocaleString()}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* History Table */}
        <div className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-2xl p-5 shadow-xs">
          <h2 className="text-sm font-semibold mb-3 flex items-center gap-2">
            <span>⏱️</span> Recent Inquiries (Last 20)
          </h2>
          {history.length === 0 ? (
            <p className="text-xs text-gray-400 py-4 text-center">No questions recorded yet.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-xs text-left">
                <thead className="bg-gray-50 dark:bg-gray-800/50 text-gray-500 dark:text-gray-400 uppercase text-[10px] tracking-wider font-semibold border-b border-gray-200 dark:border-gray-800">
                  <tr>
                    <th className="py-2.5 px-3">Question</th>
                    <th className="py-2.5 px-3">Intent</th>
                    <th className="py-2.5 px-3">Latency</th>
                    <th className="py-2.5 px-3">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100 dark:divide-gray-800/80">
                  {history.map((h) => (
                    <tr key={h.id} className="hover:bg-gray-50/50 dark:hover:bg-gray-800/30 transition">
                      <td className="py-2.5 px-3 max-w-xs truncate font-medium text-gray-800 dark:text-gray-200">
                        {h.question}
                      </td>
                      <td className="py-2.5 px-3">
                        <span className="px-2 py-0.5 rounded text-[11px] font-mono bg-indigo-50 dark:bg-indigo-950/60 text-indigo-700 dark:text-indigo-400 border border-indigo-200/50 dark:border-indigo-800/50">
                          {h.intent}
                        </span>
                      </td>
                      <td className="py-2.5 px-3 font-mono text-[11px] text-gray-500 dark:text-gray-400">
                        {h.latency_ms} ms
                      </td>
                      <td className="py-2.5 px-3">
                        {h.is_abstained ? (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium bg-amber-50 text-amber-700 border border-amber-200 dark:bg-amber-950/40 dark:text-amber-400 dark:border-amber-800/60">
                            Abstained
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium bg-emerald-50 text-emerald-700 border border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-400 dark:border-emerald-800/60">
                            Answered
                          </span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

      </div>
    </main>
  );
}

function StatCard({
  icon,
  label,
  value,
  subtext,
}: {
  icon: string;
  label: string;
  value: string | number;
  subtext: string;
}) {
  return (
    <div className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-2xl p-4 shadow-xs flex flex-col justify-between">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-medium text-gray-500 dark:text-gray-400">
          {label}
        </span>
        <span className="text-base">{icon}</span>
      </div>
      <div>
        <p className="text-xl sm:text-2xl font-bold tracking-tight text-gray-900 dark:text-gray-100">
          {value}
        </p>
        <p className="text-[11px] text-gray-400 dark:text-gray-500 mt-0.5 truncate">
          {subtext}
        </p>
      </div>
    </div>
  );
}
