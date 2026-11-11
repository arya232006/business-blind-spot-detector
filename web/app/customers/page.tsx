"use client";

import { useMemo, useState } from "react";
import { Gate } from "@/components/Gate";
import { Badge, Bar, Btn, Empty, Expander, KpiRow, Note, PageHeader, Quote, Section, Table, Tabs, Td } from "@/components/ui";
import { SentimentDonut, SentimentHistogram, SourceNegBar, TopicBar, TopicStack } from "@/components/charts";
import { COLORS, KIND_COLORS, KIND_NAMES, SENT_COLORS } from "@/lib/constants";
import { downloadCsv, mean, pct, type MentionX, type View } from "@/lib/derive";
import type { Bundle } from "@/lib/types";

const dot = (l: string) => <span className="mr-1 inline-block h-2.5 w-2.5 rounded-full" style={{ background: SENT_COLORS[l] }} />;

export default function CustomerIntelligence() {
  return (
    <>
      <PageHeader title="Customer Intelligence" subtitle="What customers talk about, how they feel, and what they actually want" />
      <Gate>{({ bundle, view }) => <Content bundle={bundle} view={view} />}</Gate>
    </>
  );
}

function Content({ bundle, view }: { bundle: Bundle; view: View }) {
  const labels = useMemo(() => Object.fromEntries(bundle.topics.map((t) => [t.topic_id, t.label])), [bundle]);
  return (
    <Tabs key={bundle.session.id} tabs={["Sentiment", "Topics", "Needs & expectations", "Negative feedback", "Review explorer"]}>
      {(tab) => tab === "Sentiment" ? <SentimentTab bundle={bundle} view={view} labels={labels} />
        : tab === "Topics" ? <TopicsTab bundle={bundle} view={view} />
        : tab === "Needs & expectations" ? <NeedsTab view={view} />
        : tab === "Negative feedback" ? <NegativeTab view={view} labels={labels} />
        : <ExplorerTab view={view} labels={labels} />}
    </Tabs>
  );
}

function SentimentTab({ bundle, view, labels }: { bundle: Bundle; view: View; labels: Record<number, string> }) {
  const c = view.customer;
  const p = (l: string) => pct(c.filter((r) => r.label === l).length, c.length);
  const mixed = useMemo(() => {
    const byRec = new Map<number, MentionX[]>();
    view.mentions.forEach((m) => byRec.set(m.record_id, [...(byRec.get(m.record_id) ?? []), m]));
    return [...byRec.entries()].filter(([, g]) => g.some((m) => m.label === "positive") && g.some((m) => m.label === "negative")).slice(0, 12);
  }, [view]);
  const text = new Map(c.map((r) => [r.record_id, r.text_original]));
  return (
    <>
      <KpiRow items={[
        { label: "Positive", value: `${p("positive").toFixed(0)}%`, sub: "of conversations", accent: COLORS.pos },
        { label: "Neutral", value: `${p("neutral").toFixed(0)}%`, sub: "of conversations", accent: COLORS.neu },
        { label: "Negative", value: `${p("negative").toFixed(0)}%`, sub: "of conversations", accent: COLORS.neg },
        { label: "Mean score", value: `${mean(c.map((r) => r.compound)) >= 0 ? "+" : ""}${mean(c.map((r) => r.compound)).toFixed(2)}`, sub: bundle.meta.sentiment_model, accent: COLORS.primary },
      ]} />
      <div className="grid gap-6 lg:grid-cols-2">
        <Section title="Sentiment distribution"><SentimentDonut rows={c} /></Section>
        <Section title="Score histogram" subtitle="Compound score from -1 (very negative) to +1 (very positive)"><SentimentHistogram rows={c} /></Section>
      </div>
      <Section title="Sentiment by topic (aspect-level)" subtitle="Each statement (clause) is scored separately and linked to its topic — one review can be positive about one topic and negative about another">
        <TopicStack topics={view.topics} />
      </Section>
      {mixed.length > 0 && (
        <Expander title={`Reviews with mixed aspect sentiment (${mixed.length})`}>
          {mixed.map(([rid, g]) => (
            <div key={rid} className="mb-3">
              <div className="text-sm font-semibold">{text.get(rid)}</div>
              {g.map((m, i) => <div key={i} className="pl-3 text-sm text-slate-700">{dot(m.label)}<b>{labels[m.topic_id] ?? m.topic_id}</b> → <i>{m.clause}</i> ({m.compound >= 0 ? "+" : ""}{m.compound.toFixed(2)})</div>)}
            </div>
          ))}
        </Expander>
      )}
    </>
  );
}

function TopicsTab({ bundle, view }: { bundle: Bundle; view: View }) {
  const topics = view.topics.filter((t) => t.mentions > 0).sort((a, b) => b.mentions - a.mentions);
  const [sel, setSel] = useState<number | null>(null);
  const selected = topics.find((t) => t.topic_id === sel);
  const rows = useMemo(() => {
    if (sel === null) return [];
    const text = new Map(view.customer.map((r) => [r.record_id, r.text_original]));
    return view.mentions.filter((m) => m.topic_id === sel).sort((a, b) => a.compound - b.compound).map((m) => ({ ...m, full: text.get(m.record_id) ?? "" }));
  }, [sel, view]);
  if (!topics.length) return <Empty>No topic statements under the current filters.</Empty>;
  return (
    <>
      <Section title="Discovered topics" subtitle={`Found automatically by ${bundle.meta.topic_backend.toUpperCase()} from your data. Click a row to read the underlying conversations.`}>
        <Table head={["Topic", "Statements", "Conversations", "Customers", "Avg sentiment", "% negative", "% positive", "Importance", "Volume change"]}>
          {topics.map((t) => (
            <tr key={t.topic_id} onClick={() => setSel(t.topic_id === sel ? null : t.topic_id)} className={`cursor-pointer hover:bg-indigo-50/50 ${sel === t.topic_id ? "bg-indigo-50" : ""}`}>
              <Td className="font-medium">{t.label}</Td><Td>{t.mentions}</Td><Td>{t.conversations}</Td><Td>{t.unique_customers}</Td>
              <Td className="tabular-nums">{t.avg_sentiment.toFixed(2)}</Td><Td><Bar value={t.negative_pct} color={COLORS.neg} label={`${t.negative_pct.toFixed(0)}%`} /></Td>
              <Td className="tabular-nums">{t.positive_pct.toFixed(0)}%</Td><Td><Bar value={t.importance} /></Td>
              <Td className="tabular-nums">{t.volume_change_pct === null ? "new/NA" : `${t.volume_change_pct > 0 ? "+" : ""}${t.volume_change_pct.toFixed(0)}%`}</Td>
            </tr>
          ))}
        </Table>
      </Section>
      <div className="grid gap-6 lg:grid-cols-2">
        <Section title="Statements per topic"><TopicBar topics={topics} /></Section>
        <Section title="Sentiment per topic"><TopicStack topics={topics} /></Section>
      </div>
      <Section title={selected ? `Conversations about: ${selected.label}` : "Conversation drill-down"} subtitle={selected ? "Most negative first. 'Statement' is the clause matched to this topic." : undefined}>
        {!selected ? <Note>Click a topic row above to inspect its customer conversations.</Note> : (
          <Table head={["Date", "Source", "Customer", "Sentiment", "Score", "Statement", "Full text"]}>
            {rows.map((m, i) => (
              <tr key={i}>
                <Td className="whitespace-nowrap">{m.date?.slice(0, 10) ?? "—"}</Td><Td>{m.source}</Td><Td>{m.customer_id}</Td><Td>{dot(m.label)}{m.label}</Td>
                <Td className="tabular-nums">{m.compound.toFixed(2)}</Td><Td className="min-w-48">{m.clause}</Td><Td className="min-w-64 text-slate-500">{m.full}</Td>
              </tr>
            ))}
          </Table>
        )}
      </Section>
    </>
  );
}

function NeedsTab({ view }: { view: View }) {
  const ex = view.expectations;
  const [kinds, setKinds] = useState<string[]>(Object.keys(KIND_NAMES));
  const labels = Object.fromEntries(view.expectations.map((e) => [e.topic_id, e.topic_label]));
  if (!ex.length) return <Empty>No expectations detected for the current filters.</Empty>;
  const inferred = ex.filter((e) => e.kind === "inferred_expectation").sort((a, b) => b.support_count - a.support_count);
  const byTopic = new Map<number, typeof ex>();
  ex.filter((e) => kinds.includes(e.kind)).forEach((e) => byTopic.set(e.topic_id, [...(byTopic.get(e.topic_id) ?? []), e]));
  return (
    <>
      <Section title="What customers actually want" subtitle="Observed = said by customers. Inferred = what complaints imply (never presented as an explicit request)." />
      {inferred.length > 0 && (
        <div className="mb-4">
          <div className="mb-1 text-sm font-semibold">Summary of expectations (inferred from complaints)</div>
          <ul className="space-y-1 text-sm text-slate-700">{inferred.map((e, i) => <li key={i}><Badge color="#64748B">INFERRED</Badge>{e.summary.replace("INFERRED: ", "")}</li>)}</ul>
        </div>
      )}
      <div className="mb-3 flex flex-wrap gap-1.5">
        {Object.entries(KIND_NAMES).map(([k, name]) => (
          <button key={k} onClick={() => setKinds(kinds.includes(k) ? kinds.filter((x) => x !== k) : [...kinds, k])} className={`rounded-full border px-3 py-1 text-xs font-semibold ${kinds.includes(k) ? "border-transparent text-white" : "border-slate-300 bg-white text-slate-500"}`} style={kinds.includes(k) ? { background: KIND_COLORS[k] } : undefined}>{name}</button>
        ))}
      </div>
      {[...byTopic.entries()].map(([tid, g]) => (
        <Expander key={tid} title={`${labels[tid] ?? tid} — ${g.length} insight(s)`}>
          {g.map((r, i) => (
            <div key={i} className="mb-3">
              <div className="text-sm"><Badge color={KIND_COLORS[r.kind]}>{KIND_NAMES[r.kind]}</Badge><Badge soft>{r.is_inferred ? "inferred" : "observed"}</Badge> {r.summary}</div>
              <div className="text-xs text-slate-500">{r.support_count} supporting statement(s) · {r.share_pct.toFixed(0)}% of topic</div>
              {(r.evidence ?? []).slice(0, 3).map((e, j) => <Quote key={j} text={e.text} meta={e.date ?? ""} />)}
            </div>
          ))}
        </Expander>
      ))}
    </>
  );
}

function NegativeTab({ view, labels }: { view: View; labels: Record<number, string> }) {
  const neg = view.customer.filter((c) => c.label === "negative").sort((a, b) => a.compound - b.compound);
  const worst = [...view.topics].sort((a, b) => b.negative_pct - a.negative_pct)[0];
  return (
    <>
      <KpiRow items={[
        { label: "Negative conversations", value: neg.length.toLocaleString(), sub: `${pct(neg.length, view.customer.length).toFixed(0)}% of filtered`, accent: COLORS.neg },
        { label: "Most negative topic", value: <span className="text-lg">{worst?.label.slice(0, 26) ?? "—"}</span>, sub: worst ? `${worst.negative_pct.toFixed(0)}% negative` : "", accent: "#B91C1C" },
      ]} />
      <div className="grid gap-6 lg:grid-cols-2">
        <Section title="Negative share by topic"><TopicStack topics={view.topics} /></Section>
        <Section title="Negative share by data source"><SourceNegBar rows={view.customer} /></Section>
      </div>
      <Section title="Most negative conversations">
        <Table head={["Date", "Source", "Score", "Topic", "Conversation"]}>
          {neg.slice(0, 50).map((r) => (
            <tr key={r.record_id}><Td className="whitespace-nowrap">{r.date?.slice(0, 10) ?? "—"}</Td><Td>{r.source}</Td><Td className="tabular-nums">{r.compound.toFixed(2)}</Td><Td>{r.topic_id !== null ? labels[r.topic_id] : "—"}</Td><Td>{r.text_original}</Td></tr>
          ))}
        </Table>
      </Section>
    </>
  );
}

function ExplorerTab({ view, labels }: { view: View; labels: Record<number, string> }) {
  const [q, setQ] = useState("");
  const [open, setOpen] = useState<number | null>(null);
  const rows = useMemo(() => view.customer.filter((r) => !q || r.text_original.toLowerCase().includes(q.toLowerCase())).sort((a, b) => (b.date ?? "").localeCompare(a.date ?? "")), [view, q]);
  const csv = () => downloadCsv("conversations.csv", rows.map((r) => ({ date: r.date?.slice(0, 10), source: r.source, customer: r.customer_id, sentiment: r.label, score: r.compound, topic: r.topic_id !== null ? labels[r.topic_id] : "", text: r.text_original })));
  const detail = open === null ? [] : view.allMentions.filter((m) => m.record_id === open);
  return (
    <>
      <Section title="Review explorer" subtitle="Search and inspect individual conversations (respects the sidebar filters)" />
      <div className="mb-3 flex gap-3">
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search text, e.g. refund, chatbot, late …" className="w-full max-w-md rounded-xl border border-slate-300 bg-white px-3.5 py-2 text-sm outline-none focus:border-indigo-500" />
        <Btn onClick={csv}>⬇ Download CSV</Btn>
      </div>
      <div className="mb-2 text-xs text-slate-500">{rows.length.toLocaleString()} conversations — click a row for aspect-level detail</div>
      <div className="max-h-[420px] overflow-auto rounded-xl border border-slate-200">
        <Table head={["Date", "Source", "Customer", "Sentiment", "Score", "Topic", "Text"]} className="border-0">
          {rows.slice(0, 300).map((r) => (
            <tr key={r.record_id} onClick={() => setOpen(open === r.record_id ? null : r.record_id)} className={`cursor-pointer hover:bg-indigo-50/50 ${open === r.record_id ? "bg-indigo-50" : ""}`}>
              <Td className="whitespace-nowrap">{r.date?.slice(0, 10) ?? "—"}</Td><Td>{r.source}</Td><Td>{r.customer_id}</Td><Td>{dot(r.label)}{r.label}</Td>
              <Td className="tabular-nums">{r.compound.toFixed(2)}</Td><Td>{r.topic_id !== null ? labels[r.topic_id] : "—"}</Td><Td className="min-w-72">{r.text_original}</Td>
            </tr>
          ))}
        </Table>
      </div>
      {rows.length > 300 && <div className="mt-1 text-xs text-slate-500">Showing the first 300 — refine the search or download the CSV for all.</div>}
      {open !== null && (
        <Section title="Aspect-level breakdown">
          <Table head={["Statement", "Aspect", "Topic", "Sentiment", "Score", "Signals"]}>
            {detail.map((m, i) => <tr key={i}><Td>{m.clause}</Td><Td>{m.aspect}</Td><Td>{labels[m.topic_id]}</Td><Td>{dot(m.label)}{m.label}</Td><Td className="tabular-nums">{m.compound.toFixed(2)}</Td><Td>{(m.signals ?? []).join(", ")}</Td></tr>)}
          </Table>
        </Section>
      )}
    </>
  );
}
