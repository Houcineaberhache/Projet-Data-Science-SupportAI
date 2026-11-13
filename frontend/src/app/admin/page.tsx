"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function Admin() {
  const [msg, setMsg] = useState("");
  const [uploading, setUploading] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [isDark, setIsDark] = useState(false);

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

  async function upload(file: File) {
    setUploading(true);
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
      } else {
        const err = await res.json();
        setMsg(`❌ ${err.detail || "Upload failed"}`);
      }
    } catch {
      setMsg("❌ Network error uploading document");
    } finally {
      setUploading(false);
    }
  }

  return (
    <main className="min-h-screen bg-gray-50 dark:bg-gray-950 text-gray-900 dark:text-gray-100 p-4 sm:p-8 transition-colors">
      <div className="max-w-3xl mx-auto space-y-6">
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
              🛠️ Document Administration
            </h1>
            <p className="text-xs sm:text-sm text-gray-500 dark:text-gray-400">
              Upload documents to index into the knowledge base
            </p>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={toggleTheme}
              aria-label="Toggle theme"
              className="w-8 h-8 rounded-lg flex items-center justify-center text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 border border-gray-200 dark:border-gray-700 transition text-sm cursor-pointer"
            >
              {isDark ? "☀️" : "🌙"}
            </button>
          </div>
        </div>

        {/* Document Ingestion Card */}
        <div className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-2xl p-6 sm:p-8 shadow-xs space-y-4">
          <h2 className="text-base font-semibold flex items-center gap-2">
            <span>📥</span> Upload Document
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
            className={`border-2 border-dashed rounded-xl p-8 sm:p-12 text-center transition-all ${
              dragging
                ? "border-indigo-500 bg-indigo-50/50 dark:bg-indigo-950/30"
                : "border-gray-200 dark:border-gray-800 bg-gray-50/50 dark:bg-gray-800/20"
            }`}
          >
            <div className="text-4xl mb-3">📄</div>
            <p className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Drag and drop knowledge base documents here, or browse files
            </p>
            <p className="text-xs text-gray-400 dark:text-gray-500 mb-5">
              Supported formats: .PDF, .DOCX, .TXT
            </p>
            <label className="inline-flex items-center px-4 py-2 rounded-lg text-xs font-medium bg-indigo-600 hover:bg-indigo-700 text-white cursor-pointer transition shadow-xs">
              {uploading ? "Uploading..." : "Choose File"}
              <input
                type="file"
                accept=".pdf,.docx,.txt"
                disabled={uploading}
                onChange={(e) => e.target.files?.[0] && upload(e.target.files[0])}
                className="hidden"
              />
            </label>
            {msg && (
              <p className="mt-4 text-xs sm:text-sm font-medium text-indigo-600 dark:text-indigo-400">
                {msg}
              </p>
            )}
          </div>
        </div>
      </div>
    </main>
  );
}
