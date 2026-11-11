"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState, type ReactNode } from "react";
import { useApp } from "@/lib/store";
import { SEVERITIES } from "@/lib/constants";
import { api } from "@/lib/api";
import { Btn, ErrorBox, MultiSelect } from "./ui";

const NAV = [
  { href: "/", label: "Overview", icon: "📊" },
  { href: "/customers", label: "Customer Intelligence", icon: "🗣️" },
  { href: "/company", label: "Company Communication", icon: "📣" },
  { href: "/blind-spots", label: "Blind Spot Analysis", icon: "🎯" },
  { href: "/trends", label: "Trend Analysis", icon: "📈" },
  { href: "/recommendations", label: "Recommendations", icon: "💡" },
  { href: "/data", label: "Data Management", icon: "🗂️" },
  { href: "/methodology", label: "Methodology & Limits", icon: "📘" },
];

const selectCls = "w-full rounded-lg border border-slate-300 bg-white px-2.5 py-2 text-sm text-slate-900 outline-none focus:border-indigo-500";
const labelCls = "mb-1 mt-3 text-[0.7rem] font-semibold uppercase tracking-wider text-slate-400";

export function Shell({ children }: { children: ReactNode }) {
  const path = usePathname();
  const app = useApp();
  const [menu, setMenu] = useState(false);
  const [showNew, setShowNew] = useState(false);
  const [newName, setNewName] = useState("");
  const [newIndustry, setNewIndustry] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [showApi, setShowApi] = useState(false);
  const [apiDraft, setApiDraft] = useState("");
  const v = app.view;

  async function createCompany() {
    setErr(null);
    try {
      const c = await api.createCompany(newName, newIndustry);
      await app.refreshCompanies();
      app.selectCompany(c.id);
      setNewName(""); setNewIndustry(""); setShowNew(false);
    } catch (e) { setErr(e instanceof Error ? e.message : String(e)); }
  }

  const sidebar = (
    <div className="flex h-full flex-col overflow-y-auto bg-slate-900 px-4 py-5 text-slate-200">
      <div className="mb-1 text-lg font-bold text-white">🔍 Blind Spot Detector</div>
      <div className="mb-4 text-xs text-slate-400">Customer intelligence &amp; business gap analysis</div>
      <nav className="space-y-0.5">
        {NAV.map((n) => {
          const active = n.href === "/" ? path === "/" : path.startsWith(n.href);
          return (
            <Link key={n.href} href={n.href} onClick={() => setMenu(false)} className={`flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium transition ${active ? "bg-slate-700/70 text-white" : "text-slate-300 hover:bg-slate-800"}`}>
              <span>{n.icon}</span>{n.label}
            </Link>
          );
        })}
      </nav>
      <hr className="my-4 border-slate-800" />

      <div className={labelCls.replace("mt-3", "mt-0")}>Company</div>
      {app.companies.length > 0 ? (
        <select className={selectCls} value={app.company?.id ?? ""} onChange={(e) => app.selectCompany(Number(e.target.value))}>
          {app.companies.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>
      ) : <div className="text-xs text-slate-400">No companies yet</div>}
      <button onClick={() => setShowNew(!showNew)} className="mt-2 text-left text-xs font-medium text-indigo-300 hover:text-indigo-200">＋ New company</button>
      {showNew && (
        <div className="mt-2 space-y-2 rounded-lg border border-slate-700 p-2.5">
          <input className={selectCls} placeholder="Company name" value={newName} onChange={(e) => setNewName(e.target.value)} />
          <input className={selectCls} placeholder="Industry (optional)" value={newIndustry} onChange={(e) => setNewIndustry(e.target.value)} />
          <Btn variant="primary" className="w-full" disabled={!newName.trim()} onClick={createCompany}>Create company</Btn>
          {err && <div className="text-xs text-red-300">{err}</div>}
        </div>
      )}

      {app.company && (
        <>
          <div className={labelCls}>Analysis</div>
          {app.sessions.some((s) => s.status === "completed") ? (
            <select className={selectCls} value={app.sessionId ?? ""} onChange={(e) => app.selectSession(Number(e.target.value))}>
              {app.sessions.filter((s) => s.status === "completed").map((s) => (
                <option key={s.id} value={s.id}>#{s.id} · {s.started_at.slice(0, 16).replace("T", " ")} · {s.n_customer} conv.{s.is_synthetic ? " · demo" : ""}</option>
              ))}
            </select>
          ) : <div className="text-xs text-slate-400">No completed analysis yet</div>}
        </>
      )}

      {v && app.bundle && (
        <>
          <hr className="my-4 border-slate-800" />
          <div className="mb-2 text-sm font-semibold text-white">Filters</div>
          <MultiSelect dark label="Topic" options={app.bundle.topics.map((t) => ({ value: String(t.topic_id), label: t.label }))} value={app.filters.topics.map(String)} onChange={(x) => app.setFilters({ ...app.filters, topics: x.map(Number) })} />
          <MultiSelect dark label="Sentiment" options={["positive", "neutral", "negative"].map((s) => ({ value: s, label: s }))} value={app.filters.sentiments} onChange={(x) => app.setFilters({ ...app.filters, sentiments: x })} />
          <MultiSelect dark label="Severity" options={SEVERITIES.map((s) => ({ value: s, label: s }))} value={app.filters.severities} onChange={(x) => app.setFilters({ ...app.filters, severities: x })} />
          <MultiSelect dark label="Data source" options={v.sources.map((s) => ({ value: s, label: s }))} value={app.filters.sources} onChange={(x) => app.setFilters({ ...app.filters, sources: x })} />
          {v.dateBounds ? (
            <div>
              <div className="mb-1 text-[0.7rem] font-semibold uppercase tracking-wider text-slate-400">Date range</div>
              <div className="grid gap-1.5">
                <input type="date" className={selectCls} min={v.dateBounds[0]} max={v.dateBounds[1]} value={app.filters.dateFrom || v.dateBounds[0]} onChange={(e) => app.setFilters({ ...app.filters, dateFrom: e.target.value })} />
                <input type="date" className={selectCls} min={v.dateBounds[0]} max={v.dateBounds[1]} value={app.filters.dateTo || v.dateBounds[1]} onChange={(e) => app.setFilters({ ...app.filters, dateTo: e.target.value })} />
              </div>
            </div>
          ) : <div className="text-xs text-slate-400">No dates in this dataset.</div>}
          <button onClick={() => app.setFilters({ topics: [], sentiments: [], severities: [], sources: [], dateFrom: "", dateTo: "" })} className="mt-3 text-left text-xs font-medium text-indigo-300 hover:text-indigo-200">Clear all filters</button>
        </>
      )}

      <div className="mt-auto pt-6 text-xs text-slate-400">
        <div className="flex items-center gap-1.5">
          <span className={`h-2 w-2 rounded-full ${app.apiStatus === "online" ? "bg-emerald-400" : app.apiStatus === "offline" ? "bg-red-400" : "bg-amber-400"}`} />
          Backend {app.apiStatus}
        </div>
        <div className="mt-1 break-all">{app.apiUrl}</div>
        <div className="mt-1">Embeddings: {app.bundle?.meta.embedding_backend ?? "—"}</div>
        <button onClick={() => { setApiDraft(app.apiUrl); setShowApi(!showApi); }} className="mt-2 font-medium text-indigo-300 hover:text-indigo-200">⚙ Backend settings</button>
        {showApi && (
          <div className="mt-2 space-y-2">
            <input className={selectCls} value={apiDraft} onChange={(e) => setApiDraft(e.target.value)} placeholder="http://localhost:8000" />
            <Btn variant="primary" className="w-full" onClick={() => { app.changeApiUrl(apiDraft); setShowApi(false); }}>Save &amp; reconnect</Btn>
          </div>
        )}
      </div>
    </div>
  );

  return (
    <div className="flex min-h-screen">
      <aside className="sticky top-0 hidden h-screen w-72 shrink-0 lg:block">{sidebar}</aside>
      {menu && (
        <div className="fixed inset-0 z-40 flex lg:hidden">
          <div className="w-72 shrink-0">{sidebar}</div>
          <div className="flex-1 bg-black/40" onClick={() => setMenu(false)} />
        </div>
      )}
      <main className="min-w-0 flex-1">
        <div className="sticky top-0 z-30 flex items-center gap-3 border-b border-slate-200 bg-white/90 px-4 py-2.5 backdrop-blur lg:hidden">
          <button onClick={() => setMenu(true)} className="rounded-lg border border-slate-300 px-2.5 py-1 text-sm">☰ Menu</button>
          <span className="text-sm font-semibold">Blind Spot Detector</span>
        </div>
        <div className="mx-auto max-w-[1400px] px-5 py-7 lg:px-8">
          {app.apiStatus === "offline" && (
            <ErrorBox>
              <b>Backend unreachable.</b> {app.apiError} Start it with <code className="rounded bg-red-100 px-1">uvicorn backend.main:app --port 8000</code>, or change the URL under ⚙ Backend settings.
              <div className="mt-2"><Btn onClick={app.recheck}>Retry connection</Btn></div>
            </ErrorBox>
          )}
          {children}
        </div>
      </main>
    </div>
  );
}
