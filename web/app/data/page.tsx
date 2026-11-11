"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { useApp } from "@/lib/store";
import type { Dataset, PreviewResult } from "@/lib/types";
import { Btn, Card, ErrorBox, Expander, Note, PageHeader, Section, SuccessBox, Table, Tabs, Td } from "@/components/ui";

const MAP_KEYS = ["text", "date", "source", "category", "customer_id", "rating"] as const;
const err = (e: unknown) => (e instanceof Error ? e.message : String(e));

export default function DataManagement() {
  const app = useApp();
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [flash, setFlash] = useState<string | null>(null);
  const cid = app.company?.id ?? null;
  const fetchDatasets = useCallback(async () => {
    try { return await (cid === null ? Promise.resolve([] as Dataset[]) : api.listDatasets(cid)); } catch { return [] as Dataset[]; }
  }, [cid]);
  const reload = useCallback(async () => { setDatasets(await fetchDatasets()); }, [fetchDatasets]);
  useEffect(() => {
    let live = true;
    void fetchDatasets().then((d) => { if (live) setDatasets(d); });
    return () => { live = false; };
  }, [fetchDatasets]);
  const saved = async (msg: string) => { setFlash(msg); await reload(); await app.refreshCompanies(); };

  if (!app.ready) return null;
  if (!app.company) return (<><PageHeader title="Data Management" subtitle="Collect customer and company data, validate it, and run the analysis" /><Note>👈 Create a company in the sidebar to get started.</Note></>);
  return (
    <>
      <PageHeader title="Data Management" subtitle="Collect customer and company data, validate it, and run the analysis" />
      {flash && <SuccessBox>{flash}</SuccessBox>}
      <Tabs tabs={["🚀 Quick start", "1 · Customer data", "2 · Company data", "3 · Run analysis", "📜 History"]}>
        {(tab) => tab.startsWith("🚀") ? <QuickStart cid={app.company!.id} onDone={saved} />
          : tab.startsWith("1") ? <InputPanel cid={app.company!.id} kind="customer" onSaved={saved} />
          : tab.startsWith("2") ? <InputPanel cid={app.company!.id} kind="company" onSaved={saved} />
          : tab.startsWith("3") ? <RunPanel cid={app.company!.id} datasets={datasets} reload={reload} />
          : <History />}
      </Tabs>
    </>
  );
}

function QuickStart({ cid, onDone }: { cid: number; onDone: (m: string) => Promise<void> }) {
  const [busy, setBusy] = useState(false);
  const [e, setE] = useState<string | null>(null);
  return (
    <Section title="Try it instantly with the NovaCart demo" subtitle="A fictional e-commerce company with 130+ synthetic customer conversations and 34 synthetic company messages. No API keys needed.">
      <Note warn>All demo records are SYNTHETIC — generated to demonstrate the pipeline, not real customer feedback. They are labelled as such everywhere in the app.</Note>
      <Btn variant="primary" disabled={busy} onClick={async () => { setBusy(true); setE(null); try { const r = await api.loadSample(cid); await onDone(r.message); } catch (x) { setE(err(x)); } finally { setBusy(false); } }}>
        📥 {busy ? "Loading…" : "Load NovaCart demo data into this company"}
      </Btn>
      {e && <ErrorBox>{e}</ErrorBox>}
      <p className="mt-3 text-sm text-slate-500">Then open the <b>Run analysis</b> tab. Tip: create a separate company for your own data so demo and real data never mix.</p>
    </Section>
  );
}

function InputPanel({ cid, kind, onSaved }: { cid: number; kind: "customer" | "company"; onSaved: (m: string) => Promise<void> }) {
  const [method, setMethod] = useState<"file" | "text" | "url">("file");
  return (
    <div>
      <h3 className="text-lg font-bold">{kind === "customer" ? "Customer data" : "Company data"}</h3>
      <p className="mb-3 text-sm text-slate-500">{kind === "customer" ? "Reviews, social comments, forum posts, complaints, feedback — what customers say." : "Website copy, product descriptions, ads, announcements, social posts — what the company says."}</p>
      <div className="mb-4 flex gap-4 text-sm">
        {([["file", "Upload file (CSV / Excel / TXT)"], ["text", "Type or paste text"], ["url", "Website URL"]] as const).map(([k, l]) => <label key={k} className="flex items-center gap-1.5"><input type="radio" checked={method === k} onChange={() => setMethod(k)} className="accent-indigo-600" />{l}</label>)}
      </div>
      {method === "file" ? <FileUpload cid={cid} kind={kind} onSaved={onSaved} /> : method === "text" ? <TextEntry cid={cid} kind={kind} onSaved={onSaved} /> : <UrlEntry cid={cid} kind={kind} onSaved={onSaved} />}
    </div>
  );
}

function FileUpload({ cid, kind, onSaved }: { cid: number; kind: "customer" | "company"; onSaved: (m: string) => Promise<void> }) {
  const [file, setFile] = useState<File | null>(null);
  const [pv, setPv] = useState<PreviewResult | null>(null);
  const [mapping, setMapping] = useState<Record<string, string | null> | null>(null);
  const [name, setName] = useState("");
  const [e, setE] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const input = useRef<HTMLInputElement>(null);

  const preview = useCallback(async (f: File, m?: Record<string, string | null>) => {
    setE(null);
    try { const r = await api.previewUpload(f, kind, m); setPv(r); if (!m) setMapping(r.mapping_used); }
    catch (x) { setPv(null); setE(err(x)); }
  }, [kind]);

  function pick(f: File | null) { setFile(f); setPv(null); setMapping(null); setName(f?.name ?? ""); if (f) void preview(f); }
  const ok = pv?.report.ok;
  return (
    <div>
      <input ref={input} type="file" accept=".csv,.tsv,.xlsx,.xls,.txt,.json" onChange={(ev) => pick(ev.target.files?.[0] ?? null)} className="block w-full max-w-lg rounded-xl border border-dashed border-slate-300 bg-white p-3 text-sm file:mr-3 file:rounded-lg file:border-0 file:bg-indigo-50 file:px-3 file:py-1.5 file:font-semibold file:text-indigo-700" />
      <p className="mt-1 text-xs text-slate-500">CSV/Excel need a text column (review, comment, text …). Optional: date, source, category, customer_id, rating.</p>
      {e && <ErrorBox>❌ {e}</ErrorBox>}
      {pv && file && (
        <div className="mt-3">
          <Expander title="Column mapping (auto-detected — adjust if needed)">
            <div className="grid gap-3 sm:grid-cols-3">
              {MAP_KEYS.map((k) => (
                <label key={k} className="text-sm"><div className="mb-1 font-medium capitalize">{k.replace("_", " ")}</div>
                  <select value={(mapping?.[k] ?? "") as string} onChange={(ev) => { const m = { ...(mapping ?? {}), [k]: ev.target.value || null }; setMapping(m); void preview(file, m); }} className="w-full rounded-lg border border-slate-300 bg-white px-2 py-1.5 text-sm">
                    <option value="">(none)</option>{pv.columns.map((c) => <option key={c} value={c}>{c}</option>)}
                  </select></label>
              ))}
            </div>
          </Expander>
          {pv.report.errors.map((x, i) => <ErrorBox key={i}>❌ {x}</ErrorBox>)}
          {pv.report.warnings.map((x, i) => <Note key={i} warn>{x}</Note>)}
          {ok && <SuccessBox>✔ {pv.report.rows_valid} of {pv.report.rows_in} rows are valid</SuccessBox>}
          {pv.preview.length > 0 && (
            <Table head={["text", "source", "date", "category", "customer_id"]} className="mt-2">
              {pv.preview.map((r, i) => <tr key={i}><Td className="min-w-64">{String(r.text ?? "")}</Td><Td>{String(r.source ?? "")}</Td><Td className="whitespace-nowrap">{String(r.date ?? "").slice(0, 10)}</Td><Td>{String(r.category ?? "")}</Td><Td>{String(r.customer_id ?? "")}</Td></tr>)}
            </Table>
          )}
          <div className="mt-3 flex items-end gap-3">
            <label className="text-sm"><div className="mb-1 font-medium">Dataset name</div><input value={name} onChange={(ev) => setName(ev.target.value)} className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm" /></label>
            <Btn variant="primary" disabled={!ok || busy} onClick={async () => {
              setBusy(true); setE(null);
              try { const ds = await api.uploadDataset(cid, file, kind, mapping ?? undefined, name); await onSaved(`Saved '${ds.name}' (${ds.n_records} records).`); setFile(null); setPv(null); if (input.current) input.current.value = ""; }
              catch (x) { setE(err(x)); } finally { setBusy(false); }
            }}>💾 Save dataset</Btn>
          </div>
        </div>
      )}
    </div>
  );
}

function TextEntry({ cid, kind, onSaved }: { cid: number; kind: "customer" | "company"; onSaved: (m: string) => Promise<void> }) {
  const [text, setText] = useState("");
  const [src, setSrc] = useState("manual_entry");
  const [e, setE] = useState<string | null>(null);
  return (
    <div>
      <textarea value={text} onChange={(ev) => setText(ev.target.value)} rows={7} className="w-full max-w-3xl rounded-xl border border-slate-300 bg-white p-3 text-sm" placeholder={kind === "customer" ? "The refund took 12 days.\nSupport never replied to my ticket." : "Free delivery on all orders above 499.\nOur new app is twice as fast."} />
      <div className="mt-1 text-xs text-slate-500">One record per line (or separate records with a blank line).</div>
      <label className="mt-2 block text-sm"><div className="mb-1 font-medium">Source label</div><input value={src} onChange={(ev) => setSrc(ev.target.value)} className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm" /></label>
      <div className="mt-3"><Btn variant="primary" disabled={!text.trim()} onClick={async () => { setE(null); try { const ds = await api.addText(cid, kind, text, src); await onSaved(`Added ${ds.n_records} records. Note: manual text has no dates, so it does not contribute to trend analysis.`); setText(""); } catch (x) { setE(err(x)); } }}>➕ Add records</Btn></div>
      {e && <ErrorBox>❌ {e}</ErrorBox>}
    </div>
  );
}

function UrlEntry({ cid, kind, onSaved }: { cid: number; kind: "customer" | "company"; onSaved: (m: string) => Promise<void> }) {
  const [url, setUrl] = useState("");
  const [busy, setBusy] = useState(false);
  const [e, setE] = useState<string | null>(null);
  return (
    <div>
      <input value={url} onChange={(ev) => setUrl(ev.target.value)} placeholder="https://example.com/about" className="w-full max-w-xl rounded-xl border border-slate-300 bg-white px-3.5 py-2 text-sm" />
      <Note>Only public pages are fetched. robots.txt is respected; logins, CAPTCHAs and private network addresses are never bypassed. Pages rendered purely by JavaScript may return no text.</Note>
      <Btn variant="primary" disabled={!url.trim() || busy} onClick={async () => { setBusy(true); setE(null); try { const ds = await api.addUrl(cid, kind, url); await onSaved(`Extracted ${ds.n_records} text blocks.`); setUrl(""); } catch (x) { setE(err(x)); } finally { setBusy(false); } }}>🌐 {busy ? "Fetching…" : "Extract text & save"}</Btn>
      {e && <ErrorBox>❌ {e}</ErrorBox>}
    </div>
  );
}

function RunPanel({ cid, datasets, reload }: { cid: number; datasets: Dataset[]; reload: () => Promise<void> }) {
  const app = useApp();
  const cust = datasets.filter((d) => d.kind === "customer");
  const comp = datasets.filter((d) => d.kind === "company");
  const [selC, setSelC] = useState<number[] | null>(null);
  const [selK, setSelK] = useState<number[] | null>(null);
  const sc = selC ?? cust.map((d) => d.id);
  const sk = selK ?? comp.map((d) => d.id);
  const [progress, setProgress] = useState<{ pct: number; msg: string } | null>(null);
  const [result, setResult] = useState<{ ok: boolean; text: string } | null>(null);
  const [preview, setPreview] = useState<{ id: number; rows: Record<string, string | null>[] } | null>(null);
  const running = progress !== null;
  const toggle = (arr: number[], id: number) => (arr.includes(id) ? arr.filter((x) => x !== id) : [...arr, id]);

  async function run() {
    setResult(null); setProgress({ pct: 0, msg: "Starting…" });
    try {
      const { session_id } = await api.startAnalysis(cid, sc, sk);
      for (;;) {
        const s = await api.analysisStatus(session_id);
        setProgress({ pct: s.progress, msg: s.message ?? "" });
        if (s.status !== "running") {
          if (s.status === "completed") { await app.refreshSessions(); app.selectSession(session_id); setResult({ ok: true, text: "✅ Analysis complete." }); }
          else setResult({ ok: false, text: `❌ Analysis failed: ${s.error}` });
          break;
        }
        await new Promise((r) => setTimeout(r, 1000));
      }
    } catch (x) { setResult({ ok: false, text: `❌ ${err(x)}` }); }
    finally { setProgress(null); await app.refreshSessions(); }
  }
  const mixed = sc.length + sk.length > 0 && datasets.filter((d) => [...sc, ...sk].includes(d.id)).some((d) => d.is_synthetic) && !datasets.filter((d) => [...sc, ...sk].includes(d.id)).every((d) => d.is_synthetic);
  return (
    <div>
      <Section title="Datasets for this company">
        {datasets.length === 0 ? <Note>No datasets yet. Load the demo data or add your own in the previous tabs.</Note> : (
          <Table head={["ID", "Kind", "Name", "Type", "Records", "Synthetic", "Added", ""]}>
            {datasets.map((d) => (
              <tr key={d.id}><Td>{d.id}</Td><Td>{d.kind}</Td><Td className="font-medium">{d.name}</Td><Td>{d.source_type}</Td><Td>{d.n_records}</Td><Td>{d.is_synthetic ? "yes (demo)" : ""}</Td><Td className="whitespace-nowrap">{d.created_at.slice(0, 16).replace("T", " ")}</Td>
                <Td className="whitespace-nowrap">
                  <button className="mr-3 text-xs font-semibold text-indigo-600" onClick={async () => setPreview({ id: d.id, rows: await api.datasetRecords(d.id, 50) })}>Preview</button>
                  <button className="text-xs font-semibold text-red-600" onClick={async () => { await api.deleteDataset(d.id); setSelC(null); setSelK(null); setPreview(null); await reload(); }}>Delete</button></Td></tr>
            ))}
          </Table>
        )}
        {preview && <div className="mt-3"><Table head={["text", "source", "date", "category"]}>{preview.rows.map((r, i) => <tr key={i}><Td className="min-w-64">{r.text}</Td><Td>{r.source}</Td><Td>{r.date?.slice(0, 10)}</Td><Td>{r.category}</Td></tr>)}</Table></div>}
      </Section>

      <Section title="Run the full analysis" subtitle="Sentiment → topics → expectations → company analysis → semantic gap → scoring → trends → recommendations">
        <div className="grid gap-4 sm:grid-cols-2">
          {([["Customer datasets", cust, sc, setSelC], ["Company datasets", comp, sk, setSelK]] as const).map(([title, list, sel, setSel]) => (
            <Card key={title}><div className="mb-2 text-sm font-semibold">{title}</div>
              {list.length === 0 ? <div className="text-sm text-slate-500">None yet</div> : list.map((d) => <label key={d.id} className="mb-1 flex items-center gap-2 text-sm"><input type="checkbox" className="accent-indigo-600" checked={sel.includes(d.id)} onChange={() => setSel(toggle(sel, d.id))} />{d.name} <span className="text-xs text-slate-400">({d.n_records})</span></label>)}
            </Card>
          ))}
        </div>
        {(cust.length === 0 || comp.length === 0) && <Note warn>You need at least one customer dataset AND one company dataset.</Note>}
        {mixed && <Note warn>You selected both synthetic demo data and other data. Results will mix them.</Note>}
        <div className="mt-3"><Btn variant="primary" disabled={running || sc.length === 0 || sk.length === 0} onClick={run}>🚀 {running ? "Running…" : "Run analysis"}</Btn></div>
        {progress && (
          <div className="mt-3 max-w-xl">
            <div className="mb-1 text-sm text-slate-600">{progress.msg} ({progress.pct}%)</div>
            <div className="h-2.5 overflow-hidden rounded-full bg-slate-200"><div className="h-full rounded-full bg-indigo-600 transition-all" style={{ width: `${progress.pct}%` }} /></div>
          </div>
        )}
        {result && (result.ok ? <SuccessBox>{result.text} <Link href="/" className="font-semibold underline">Go to Overview →</Link></SuccessBox> : <ErrorBox>{result.text}</ErrorBox>)}
      </Section>
    </div>
  );
}

function History() {
  const app = useApp();
  return (
    <Section title="Analysis history" subtitle="Every run is stored with its data, settings and results">
      {app.sessions.length === 0 ? <Note>No analyses yet.</Note> : (
        <Table head={["ID", "Status", "Started", "Customer records", "Company messages", "Topics", "Blind spots", "Avg score", "Runtime (s)", "Demo", "Error", ""]}>
          {app.sessions.map((s) => (
            <tr key={s.id}><Td>{s.id}</Td><Td>{s.status}</Td><Td className="whitespace-nowrap">{s.started_at.slice(0, 16).replace("T", " ")}</Td><Td>{s.n_customer}</Td><Td>{s.n_company}</Td><Td>{s.total_topics ?? ""}</Td><Td>{s.total_blind_spots ?? ""}</Td>
              <Td>{s.avg_blind_spot_score?.toFixed(1) ?? ""}</Td><Td>{s.runtime_seconds ?? ""}</Td><Td>{s.is_synthetic ? "yes" : ""}</Td><Td className="max-w-56 text-red-600">{s.error}</Td>
              <Td className="whitespace-nowrap">
                {s.status === "completed" && <button className="mr-3 text-xs font-semibold text-indigo-600" onClick={() => app.selectSession(s.id)}>Open</button>}
                <button className="text-xs font-semibold text-red-600" onClick={async () => { await api.deleteAnalysis(s.id); await app.refreshSessions(); }}>Delete</button></Td></tr>
          ))}
        </Table>
      )}
    </Section>
  );
}
