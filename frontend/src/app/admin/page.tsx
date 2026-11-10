"use client";

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

  async function load() {
    const [s, d, h] = await Promise.all([
      fetch(`${API_URL}/api/admin/stats`).then((r) => r.json()),
      fetch(`${API_URL}/api/admin/documents`).then((r) => r.json()),
      fetch(`${API_URL}/api/admin/history`).then((r) => r.json()),
    ]);
    setStats(s);
    setDocs(d);
    setHistory(h);
  }

  useEffect(() => {
    load();
  }, []);

  async function upload(file: File) {
    setMsg("Uploading...");
    const form = new FormData();
    form.append("file", file);
    const res = await fetch(`${API_URL}/api/admin/upload`, {
      method: "POST",
      body: form,
    });
    if (res.ok) {
      const data = await res.json();
      setMsg(`✅ ${data.title} uploaded (${data.chunks_count} chunks)`);
      load();
    } else {
      const err = await res.json();
      setMsg(`❌ ${err.detail || "Upload failed"}`);
    }
  }

  return (
    <main className="min-h-screen bg-gray-50 text-gray-900 p-6">
      <div className="max-w-4xl mx-auto space-y-6">
        <h1 className="text-xl font-semibold">🛠️ NovaShop Admin</h1>

        {/* Stats */}
        {stats && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <Card label="Questions" value={stats.total_questions} />
            <Card label="Avg latency (ms)" value={stats.avg_latency_ms} />
            <Card label="Unanswered" value={stats.abstained} />
            <Card label="👍 / 👎" value={`${stats.thumbs_up} / ${stats.thumbs_down}`} />
          </div>
        )}

        {/* Intents */}
        {stats && (
          <div className="bg-white border rounded-xl p-4">
            <h2 className="font-medium mb-2">Intents</h2>
            <div className="flex flex-wrap gap-2 text-sm">
              {Object.entries(stats.intents).map(([k, v]) => (
                <span key={k} className="bg-gray-100 rounded px-2 py-1">
                  {k}: {v}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Upload */}
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
          className={
            "border-2 border-dashed rounded-xl p-8 text-center bg-white " +
            (dragging ? "border-blue-500" : "border-gray-300")
          }
        >
          <p className="text-sm text-gray-600 mb-2">
            Drag a PDF, DOCX or TXT here, or
          </p>
          <input
            type="file"
            accept=".pdf,.docx,.txt"
            onChange={(e) => e.target.files?.[0] && upload(e.target.files[0])}
            className="text-sm"
          />
          {msg && <p className="mt-3 text-sm">{msg}</p>}
        </div>

        {/* Documents */}
        <div className="bg-white border rounded-xl p-4">
          <h2 className="font-medium mb-2">Documents</h2>
          {docs.length === 0 ? (
            <p className="text-sm text-gray-400">No documents yet.</p>
          ) : (
            <table className="w-full text-sm">
              <tbody>
                {docs.map((d) => (
                  <tr key={d.id} className="border-t">
                    <td className="py-1">📄 {d.title}</td>
                    <td>{d.chunks_count} chunks</td>
                    <td className="text-gray-500">
                      {new Date(d.uploaded_at).toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* History */}
        <div className="bg-white border rounded-xl p-4">
          <h2 className="font-medium mb-2">Recent questions</h2>
          <table className="w-full text-sm">
            <thead className="text-left text-gray-500">
              <tr>
                <th>Question</th>
                <th>Intent</th>
                <th>ms</th>
                <th>Answered</th>
              </tr>
            </thead>
            <tbody>
              {history.map((h) => (
                <tr key={h.id} className="border-t">
                  <td className="py-1">{h.question}</td>
                  <td>{h.intent}</td>
                  <td>{h.latency_ms}</td>
                  <td>{h.is_abstained ? "❌" : "✅"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </main>
  );
}

function Card({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="bg-white border rounded-xl p-4">
      <p className="text-xs text-gray-500">{label}</p>
      <p className="text-xl font-semibold">{value}</p>
    </div>
  );
}