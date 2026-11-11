"use client";

import { Gate } from "@/components/Gate";
import { ClassBadge, Card, KpiRow, Meter, Note, PageHeader, Section, SeverityBadge, Expander } from "@/components/ui";
import { SentimentDonut, TopicBar } from "@/components/charts";
import { COLORS, SEVERITY_COLORS } from "@/lib/constants";
import { flaggedSpots, mean, pct } from "@/lib/derive";
import { useApp } from "@/lib/store";

export default function Overview() {
  const app = useApp();
  return (
    <>
      <PageHeader title="Overview" subtitle={app.company ? `${app.company.name} · what customers say vs what the company communicates` : "Business Blind Spot Detector"} />
      <Gate>
        {({ bundle, view }) => {
          const minScore = bundle.meta.scoring_config?.min_score ?? 5;
          const flagged = flaggedSpots(view.blindSpots, minScore);
          const visible = new Set(view.topics.map((t) => t.topic_id));
          const emerging = bundle.trend_emerging.filter((e) => visible.has(e.topic_id));
          const m = mean(view.customer.map((c) => c.compound));
          const posPct = pct(view.customer.filter((c) => c.label === "positive").length, view.customer.length);
          const negPct = pct(view.customer.filter((c) => c.label === "negative").length, view.customer.length);
          const top = [...view.blindSpots].sort((a, b) => b.score - a.score).slice(0, 5);
          return (
            <>
              <KpiRow items={[
                { label: "Conversations analysed", value: view.customer.length.toLocaleString(), sub: `of ${bundle.overview.total_conversations.toLocaleString()} total`, accent: COLORS.primary },
                { label: "Topics detected", value: view.topics.length, sub: `${bundle.meta.topic_backend.toUpperCase()} discovery`, accent: "#0EA5E9" },
                { label: "Potential blind spots", value: flagged.length, sub: `${flagged.filter((f) => f.classification === "genuine_blind_spot").length} genuine`, accent: COLORS.neg },
                { label: "Emerging issues", value: emerging.length, sub: "statistically significant growth", accent: COLORS.warn },
                { label: "Overall sentiment", value: `${m >= 0 ? "+" : ""}${m.toFixed(2)}`, sub: `${posPct.toFixed(0)}% pos · ${negPct.toFixed(0)}% neg`, accent: m > 0.05 ? COLORS.pos : m < -0.05 ? COLORS.neg : COLORS.neu },
                { label: "Avg blind spot score", value: flagged.length ? mean(flagged.map((f) => f.score)).toFixed(1) : "—", sub: "flagged blind spots, 0-100", accent: "#7C3AED" },
              ]} />

              <div className="mt-6 grid gap-6 lg:grid-cols-[1fr_1.5fr]">
                <div>
                  <Section title="Customer sentiment" subtitle="VADER compound score per conversation"><SentimentDonut rows={view.customer} /></Section>
                </div>
                <div>
                  <Section title="Top customer concerns" subtitle="Statements per topic · colour = average sentiment"><TopicBar topics={view.topics} /></Section>
                </div>
              </div>

              <Section title="Highest-scoring blind spots" subtitle="Ranked by Blind Spot Score = Importance × Expectation Gap × Trend ÷ 10,000">
                {top.length === 0 && <Note>No blind spots match the current filters.</Note>}
                {top.map((r) => {
                  const color = SEVERITY_COLORS[r.severity];
                  return (
                    <Card key={r.topic_id} className="mb-3">
                      <div className="flex flex-wrap items-center justify-between gap-3">
                        <h4 className="text-base font-semibold">#{r.rank} · {r.topic_label}</h4>
                        <div className="flex items-center"><ClassBadge c={r.classification} /><SeverityBadge s={r.severity} /><b className="text-xl" style={{ color }}>{r.score.toFixed(1)}</b><span className="text-slate-400">/100</span></div>
                      </div>
                      <Meter value={r.score} color={color} />
                      <p className="mt-2 text-sm text-slate-700">
                        <b>Customer importance</b> {r.importance.toFixed(0)} · <b>Company coverage</b> {r.coverage_norm.toFixed(0)} · <b>Gap</b> {r.gap.toFixed(0)} · <b>Negative</b> {r.negative_pct.toFixed(0)}% of {r.mentions} statements · <b>Trend</b> {r.trend_status ?? "n/a"}
                      </p>
                    </Card>
                  );
                })}
              </Section>

              <Section title="Emerging issues" subtitle="Topics whose share of conversation is growing significantly AND is mostly negative">
                {emerging.length === 0 ? <Note>{bundle.meta.trend_reason || "No topic shows a statistically significant increase in negative conversation."}</Note> : emerging.map((e) => (
                  <Card key={e.topic_id} className="mb-3"><h4 className="font-semibold">📈 {e.topic_label} <span className="font-normal text-slate-500">· {e.status}</span></h4><p className="mt-1 text-sm text-slate-700">{e.reason}</p></Card>
                ))}
              </Section>

              {bundle.meta.notes.length > 0 && (
                <div className="mt-6"><Expander title={`Data-quality notes (${bundle.meta.notes.length})`}><ul className="list-disc space-y-1 pl-5 text-sm text-slate-700">{bundle.meta.notes.map((n, i) => <li key={i}>{n}</li>)}</ul></Expander></div>
              )}
            </>
          );
        }}
      </Gate>
    </>
  );
}
