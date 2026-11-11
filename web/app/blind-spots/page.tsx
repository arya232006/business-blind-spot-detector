"use client";

import { useState } from "react";
import { Gate } from "@/components/Gate";
import { ComponentBars, GapScatter, ImportanceCoverage, ScoreBar } from "@/components/charts";
import { Bar, Badge, Btn, ClassBadge, ErrorBox, Expander, KpiRow, Note, PageHeader, Quote, Section, SeverityBadge, Slider, SuccessBox, Table, Td } from "@/components/ui";
import { CAVEAT, CLASS_EXPLANATIONS, CLASS_LABELS, SEVERITY_BANDS, SEVERITY_COLORS } from "@/lib/constants";
import { downloadCsv } from "@/lib/derive";
import { api } from "@/lib/api";
import { useApp } from "@/lib/store";
import type { BlindSpot, Bundle, RescoreResult, ScoringConfig } from "@/lib/types";

export default function BlindSpots() {
  return (
    <>
      <PageHeader title="Blind Spot Analysis" subtitle="Where customer priorities and company communication diverge — ranked and scored" />
      <Gate>{({ bundle, view }) => (view.blindSpots.length === 0 ? <Note>No blind spots match the current filters.</Note> : <Content bundle={bundle} spots={[...view.blindSpots].sort((a, b) => b.score - a.score)} />)}</Gate>
    </>
  );
}

function Content({ bundle, spots }: { bundle: Bundle; spots: BlindSpot[] }) {
  const app = useApp();
  const [pick, setPick] = useState<number>(spots[0].topic_id);
  const r = spots.find((s) => s.topic_id === pick) ?? spots[0]; // falls back to the top item if filters removed the selection
  const sev = (s: string) => spots.filter((x) => x.severity === s).length;
  const ex = bundle.expectations.filter((e) => e.topic_id === r.topic_id);
  return (
    <>
      <KpiRow items={SEVERITY_BANDS.map(([s, range]) => ({ label: s, value: sev(s), sub: `score ${range}`, accent: SEVERITY_COLORS[s] }))} />

      <Section title="Ranked blind spots" right={<Btn onClick={() => downloadCsv("blind_spots.csv", spots.map((s) => ({ rank: s.rank, topic: s.topic_label, type: CLASS_LABELS[s.classification], importance: s.importance.toFixed(1), coverage: s.coverage_norm.toFixed(1), gap: s.gap.toFixed(1), trend: s.trend_used.toFixed(1), trend_available: s.trend_available, score: s.score, severity: s.severity })))}>⬇ CSV</Btn>}>
        <Table head={["Rank", "Topic", "Type", "Importance", "Coverage", "Gap", "Trend", "Score", "Severity"]}>
          {spots.map((s) => (
            <tr key={s.topic_id} onClick={() => setPick(s.topic_id)} className={`cursor-pointer hover:bg-indigo-50/50 ${r.topic_id === s.topic_id ? "bg-indigo-50" : ""}`}>
              <Td>{s.rank}</Td><Td className="font-medium">{s.topic_label}</Td><Td><ClassBadge c={s.classification} /></Td>
              <Td><Bar value={s.importance} /></Td><Td><Bar value={s.coverage_norm} color="#F59E0B" /></Td><Td><Bar value={s.gap} color="#F97316" /></Td>
              <Td className="whitespace-nowrap tabular-nums">{s.trend_used.toFixed(0)}{s.trend_available ? "" : " (neutral)"}</Td>
              <Td><Bar value={s.score} color={SEVERITY_COLORS[s.severity]} label={s.score.toFixed(1)} /></Td><Td><SeverityBadge s={s.severity} /></Td>
            </tr>
          ))}
        </Table>
      </Section>

      <div className="grid gap-6 lg:grid-cols-2">
        <Section title="Customer importance vs company coverage" subtitle="The gap between the bars is the mismatch"><ImportanceCoverage spots={spots} /></Section>
        <Section title="Importance × coverage map" subtitle="Labels = rank · bubble size = statements · dashed lines mark the high-importance / low-coverage zone"><GapScatter spots={spots} /></Section>
      </div>
      <Section title="Blind Spot Score" subtitle="Dotted lines mark severity bands (20 / 40 / 60 / 80)"><ScoreBar spots={spots} /></Section>

      <Section title="Inspect a blind spot" subtitle="Evidence behind the score">
        <select value={r.topic_id} onChange={(e) => setPick(Number(e.target.value))} className="mb-3 w-full max-w-xl rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm">
          {spots.map((s) => <option key={s.topic_id} value={s.topic_id}>#{s.rank} · {s.topic_label}</option>)}
        </select>
        <div className="mb-1 flex flex-wrap items-center"><ClassBadge c={r.classification} /><SeverityBadge s={r.severity} /><b className="ml-1">{r.topic_label}</b><span className="ml-2 text-slate-600">— score <b>{r.score.toFixed(1)}</b></span></div>
        <p className="mb-2 text-sm italic text-slate-600">{CLASS_EXPLANATIONS[r.classification]}</p>
        {["genuine_blind_spot", "communication_gap", "unmet_operational_need"].includes(r.classification) && <Note>{CAVEAT}</Note>}
        <div className="mt-3 grid gap-6 lg:grid-cols-2">
          <div>
            <ComponentBars spot={r} />
            <p className="text-sm"><b>Calculation:</b> {r.importance.toFixed(1)} × {r.gap.toFixed(1)} × {r.trend_used.toFixed(1)} ÷ 10,000 = <b>{r.score.toFixed(1)}</b></p>
            {!r.trend_available && <Note warn>Not enough dated history for this topic: a neutral trend value was used instead of guessing a direction.</Note>}
            <p className="mt-2 text-sm text-slate-700">Trend status: <b>{r.trend_status ?? "unavailable"}</b> · customers: <b>{r.unique_customers}</b> · statements: <b>{r.mentions}</b> · negative: <b>{r.negative_pct.toFixed(0)}%</b>{r.recurring && <> · <Badge color="#7C3AED">recurring frustration</Badge></>}</p>
          </div>
          <div>
            <div className="mb-1 text-sm font-semibold">Customer evidence (most negative statements)</div>
            {(r.evidence_quotes ?? []).map((e, i) => <Quote key={i} text={e.text} meta={`${e.date ?? ""} · ${e.compound >= 0 ? "+" : ""}${e.compound.toFixed(2)}`} />)}
            <div className="mb-1 mt-3 text-sm font-semibold">Closest company messages</div>
            <ul className="list-disc space-y-1 pl-5 text-sm text-slate-700">{(r.closest_company_messages ?? []).map((m, i) => <li key={i}>“{m.text}” — similarity {m.similarity.toFixed(2)}</li>)}</ul>
          </div>
        </div>
        {ex.length > 0 && (
          <div className="mt-3"><Expander title="What customers expect on this topic">
            <ul className="space-y-1.5 text-sm">{ex.map((e, i) => <li key={i}><Badge soft>{e.is_inferred ? "inferred" : "observed"}</Badge>{e.summary}</li>)}</ul>
          </Expander></div>
        )}
      </Section>

      <ScoringPanel key={`${app.sessionId}-${JSON.stringify(bundle.meta.scoring_config)}`} sessionId={app.sessionId!} current={bundle.meta.scoring_config} spots={spots} onApplied={app.reloadBundle} />
    </>
  );
}

const GROUPS: { title: string; fields: { key: keyof ScoringConfig; label: string; min: number; max: number; step: number }[] }[] = [
  { title: "Customer importance weights", fields: [
    { key: "w_frequency", label: "Topic frequency", min: 0, max: 1, step: 0.05 }, { key: "w_unique_customers", label: "Unique customers", min: 0, max: 1, step: 0.05 },
    { key: "w_sentiment", label: "Negative sentiment", min: 0, max: 1, step: 0.05 }, { key: "w_explicit_requests", label: "Explicit requests", min: 0, max: 1, step: 0.05 }] },
  { title: "Expectation gap & trend weights", fields: [
    { key: "w_coverage", label: "Gap: coverage weight", min: 0, max: 1, step: 0.05 }, { key: "w_similarity", label: "Gap: similarity weight", min: 0, max: 1, step: 0.05 },
    { key: "w_volume_trend", label: "Trend: volume weight", min: 0, max: 1, step: 0.05 }, { key: "w_negative_trend", label: "Trend: negativity weight", min: 0, max: 1, step: 0.05 }] },
  { title: "Thresholds", fields: [
    { key: "min_importance", label: "Min importance to flag", min: 0, max: 100, step: 1 }, { key: "min_gap", label: "Min gap to flag", min: 0, max: 100, step: 1 },
    { key: "low_coverage", label: "'Low coverage' below", min: 0, max: 100, step: 1 }, { key: "trend_floor", label: "Trend floor", min: 0, max: 50, step: 1 }] },
];

function ScoringPanel({ sessionId, current, spots, onApplied }: { sessionId: number; current: ScoringConfig; spots: BlindSpot[]; onApplied: () => Promise<void> }) {
  const [cfg, setCfg] = useState<ScoringConfig>(current);
  const [preview, setPreview] = useState<RescoreResult | null>(null);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [busy, setBusy] = useState(false);

  async function run(kind: "preview" | "apply" | "default") {
    setBusy(true); setMsg(null);
    try {
      if (kind === "default") { await api.saveScoringConfig(cfg); setMsg({ ok: true, text: "Saved as the default for future analyses." }); }
      else {
        const res = await api.rescore(sessionId, cfg, kind === "apply");
        if (kind === "preview") setPreview(res);
        else { setPreview(null); await onApplied(); setMsg({ ok: true, text: "Scores updated for this analysis." }); }
      }
    } catch (e) { setMsg({ ok: false, text: e instanceof Error ? e.message : String(e) }); }
    finally { setBusy(false); }
  }
  const old = new Map(spots.map((s) => [s.topic_id, s]));
  return (
    <Section title="Scoring weights & thresholds" subtitle="All parameters are configurable. Re-scoring re-uses stored components, so no NLP re-run is needed.">
      <div className="rounded-2xl border border-slate-200 bg-white p-4">
        {GROUPS.map((g) => (
          <div key={g.title} className="mb-4">
            <div className="mb-2 text-sm font-semibold">{g.title}</div>
            <div className="grid gap-x-6 gap-y-3 sm:grid-cols-2 lg:grid-cols-4">{g.fields.map((f) => <Slider key={f.key} label={f.label} min={f.min} max={f.max} step={f.step} value={cfg[f.key] as number} onChange={(v) => setCfg({ ...cfg, [f.key]: v })} />)}</div>
          </div>
        ))}
        <div className="flex flex-wrap gap-2">
          <Btn disabled={busy} onClick={() => run("preview")}>👁 Preview new scores</Btn>
          <Btn variant="primary" disabled={busy} onClick={() => run("apply")}>✅ Apply to this analysis</Btn>
          <Btn disabled={busy} onClick={() => run("default")}>💾 Save as default</Btn>
        </div>
        {msg && (msg.ok ? <SuccessBox>{msg.text}</SuccessBox> : <ErrorBox>{msg.text}</ErrorBox>)}
        {preview && (
          <div className="mt-4">
            <Table head={["Topic", "Old score", "New score", "Old severity", "New severity", "New type"]}>
              {[...preview.blind_spots].sort((a, b) => b.score - a.score).map((n) => (
                <tr key={n.topic_id}><Td>{n.topic_label}</Td><Td className="tabular-nums">{old.get(n.topic_id)?.score.toFixed(1)}</Td><Td className="font-semibold tabular-nums">{n.score.toFixed(1)}</Td><Td>{old.get(n.topic_id)?.severity}</Td><Td><SeverityBadge s={n.severity} /></Td><Td>{CLASS_LABELS[n.classification]}</Td></tr>
              ))}
            </Table>
            <div className="mt-1 text-xs text-slate-500">Preview only — nothing was saved.</div>
          </div>
        )}
      </div>
    </Section>
  );
}
