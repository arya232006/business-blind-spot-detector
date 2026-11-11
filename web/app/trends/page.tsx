"use client";

import { useMemo, useState } from "react";
import { Gate } from "@/components/Gate";
import { NegativeHeatmap, NegativeShareTrend, SentimentTrend, TopicLines, type TrendMetric } from "@/components/charts";
import { Card, Empty, KpiRow, Note, PageHeader, Section, Table, Td } from "@/components/ui";
import { COLORS } from "@/lib/constants";
import type { Bundle } from "@/lib/types";
import type { View } from "@/lib/derive";

export default function Trends() {
  return (
    <>
      <PageHeader title="Trend Analysis" subtitle="Which issues are growing, which are fading — corrected for changes in sample volume" />
      <Gate>{({ bundle, view }) => <Content bundle={bundle} view={view} />}</Gate>
    </>
  );
}

const FREQ = { D: "day", W: "week", M: "month" } as const;

function Content({ bundle, view }: { bundle: Bundle; view: View }) {
  const meta = bundle.meta;
  const visible = useMemo(() => new Set(view.topics.map((t) => t.topic_id)), [view.topics]);
  const labels = useMemo(() => Object.fromEntries(bundle.topics.map((t) => [t.topic_id, t.label])), [bundle]);
  const series = bundle.trend_series.filter((s) => visible.has(s.topic_id));
  const summ = bundle.trend_summary.filter((s) => visible.has(s.topic_id));
  const defaultIds = [...summ].sort((a, b) => b.recent_n - a.recent_n).slice(0, 4).map((s) => s.topic_id);
  const [metric, setMetric] = useState<TrendMetric>("volume");
  const [chosen, setChosen] = useState<number[] | null>(null);
  const ids = (chosen ?? defaultIds).filter((i) => visible.has(i));
  if (!meta.trend_available) {
    return (
      <>
        <Note warn>{meta.trend_reason || "Trend analysis is unavailable for this dataset (no usable dates)."}</Note>
        <p className="text-sm text-slate-600">Upload a customer dataset with a <b>date</b> column (at least 20 dated records spanning 1+ week) to enable trends.</p>
      </>
    );
  }
  const emerging = bundle.trend_emerging.filter((e) => visible.has(e.topic_id));
  const spikes = bundle.trend_spikes.filter((s) => visible.has(s.topic_id));
  const freq = FREQ[meta.trend_freq as keyof typeof FREQ] ?? "week";
  return (
    <>
      <KpiRow items={[
        { label: "Time bucket", value: freq[0].toUpperCase() + freq.slice(1), sub: `recent window starts ${(meta.recent_start ?? "").slice(0, 10)}`, accent: COLORS.primary },
        { label: "Emerging issues", value: emerging.length, sub: "growing + mostly negative", accent: COLORS.warn },
        { label: "Growing topics", value: summ.filter((s) => ["increasing", "emerging"].includes(s.status)).length, sub: "significant increase in share", accent: COLORS.neg },
        { label: "Declining topics", value: summ.filter((s) => s.status === "declining").length, sub: "significant decrease in share", accent: COLORS.pos },
        { label: "Negative spikes", value: spikes.length, sub: "anomalous buckets", accent: "#7C3AED" },
      ]} />

      <Section title="Topic volume over time" subtitle={`Per ${freq}. 'Share' divides by all statements in the period so growth in raw volume alone is not mistaken for a trend.`}>
        <div className="grid gap-4 lg:grid-cols-[3fr_1fr]">
          <div>{ids.length ? <TopicLines series={series} labels={labels} ids={ids} metric={metric} /> : <Empty>Select at least one topic.</Empty>}</div>
          <Card>
            <div className="mb-1 text-sm font-semibold">Metric</div>
            {([["volume", "Statements"], ["share", "Share of period (%)"], ["neg_count", "Negative statements"]] as [TrendMetric, string][]).map(([k, l]) => (
              <label key={k} className="mb-1 flex items-center gap-2 text-sm"><input type="radio" checked={metric === k} onChange={() => setMetric(k)} className="accent-indigo-600" />{l}</label>
            ))}
            <div className="mb-1 mt-3 text-sm font-semibold">Topics</div>
            {[...visible].map((id) => (
              <label key={id} className="mb-1 flex items-start gap-2 text-sm"><input type="checkbox" className="mt-0.5 accent-indigo-600" checked={ids.includes(id)} onChange={() => setChosen(ids.includes(id) ? ids.filter((x) => x !== id) : [...ids, id])} />{labels[id]}</label>
            ))}
          </Card>
        </div>
      </Section>

      <div className="grid gap-6 lg:grid-cols-2">
        <Section title="Overall sentiment trend"><SentimentTrend overall={bundle.trend_overall} /></Section>
        <Section title="Negative conversations over time"><NegativeShareTrend overall={bundle.trend_overall} /></Section>
      </div>

      <Section title="Negative feedback heatmap" subtitle="Darker = more negative statements in that period"><NegativeHeatmap series={series} labels={labels} /></Section>

      <Section title="Emerging issues & increasing complaints">
        {emerging.length === 0 ? <Note>No topic shows a statistically significant increase in negative conversation.</Note> : emerging.map((e) => (
          <Card key={e.topic_id} className="mb-3"><h4 className="font-semibold">📈 {e.topic_label} · {e.status}</h4><p className="mt-1 text-sm text-slate-700">{e.reason}</p></Card>
        ))}
      </Section>

      <Section title="Trend table" subtitle="p-values come from a two-proportion z-test of recent vs historical share; low-confidence changes are shrunk toward neutral (50)">
        <Table head={["Topic", "Status", "Trend score", "Recent n", "History n", "Recent share %", "History share %", "Volume Δ%", "p-value", "Neg. Δ pts", "Sentiment slope/wk"]}>
          {[...summ].sort((a, b) => (b.trend_score ?? -1) - (a.trend_score ?? -1)).map((s) => (
            <tr key={s.topic_id}>
              <Td className="font-medium">{s.topic_label}</Td><Td>{s.status}</Td><Td className="tabular-nums">{s.trend_score === null ? "—" : s.trend_score.toFixed(0)}</Td>
              <Td>{s.recent_n}</Td><Td>{s.history_n}</Td><Td className="tabular-nums">{s.recent_share_pct.toFixed(1)}</Td><Td className="tabular-nums">{s.history_share_pct.toFixed(1)}</Td>
              <Td className="tabular-nums">{s.volume_change_pct === null ? "—" : s.volume_change_pct.toFixed(0)}</Td><Td className="tabular-nums">{s.volume_p_value.toFixed(3)}</Td>
              <Td className="tabular-nums">{s.negative_delta_pct.toFixed(1)}</Td><Td className="tabular-nums">{s.sentiment_slope_per_week === null ? "—" : s.sentiment_slope_per_week.toFixed(3)}</Td>
            </tr>
          ))}
        </Table>
      </Section>

      <Section title="Sudden spikes in negative feedback" subtitle="Buckets whose negative count is an outlier vs the topic's own history (robust z-score ≥ 2.5, ≥ 3 statements)">
        {spikes.length === 0 ? <Note>No anomalous spikes detected.</Note> : (
          <Table head={["Topic", "Period starting", "Negative statements", "Robust z"]}>
            {[...spikes].sort((a, b) => a.period.localeCompare(b.period)).map((s, i) => <tr key={i}><Td>{s.topic_label}</Td><Td>{s.period.slice(0, 10)}</Td><Td>{s.negative_count}</Td><Td className="tabular-nums">{s.z_score.toFixed(1)}</Td></tr>)}
          </Table>
        )}
      </Section>
    </>
  );
}
