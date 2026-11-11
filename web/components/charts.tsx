"use client";

import { Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart, Pie, PieChart, ReferenceLine, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis, ZAxis } from "recharts";
import { COLORS, SENT_COLORS, SEVERITY_COLORS } from "@/lib/constants";
import { sentimentHistogram } from "@/lib/derive";
import type { BlindSpot, CustomerRow, OverallRow, SeriesRow, Topic } from "@/lib/types";

const short = (s: string, n = 26) => (s.length <= n ? s : s.slice(0, n - 1) + "…");
const AX = { tick: { fill: "#64748B", fontSize: 12 }, stroke: "#CBD5E1" };
const PALETTE = ["#4F46E5", "#F97316", "#10B981", "#EC4899", "#0EA5E9", "#EAB308", "#8B5CF6", "#14B8A6"];

/** red -> amber -> green for average sentiment (-0.6 .. +0.6) */
export function sentColor(v: number): string {
  const t = Math.max(0, Math.min(1, (v + 0.6) / 1.2));
  const lerp = (a: number[], b: number[], k: number) => a.map((x, i) => Math.round(x + (b[i] - x) * k));
  const red = [239, 68, 68], mid = [253, 230, 138], grn = [16, 185, 129];
  const c = t < 0.5 ? lerp(red, mid, t / 0.5) : lerp(mid, grn, (t - 0.5) / 0.5);
  return `rgb(${c[0]},${c[1]},${c[2]})`;
}

function Box({ h = 320, children }: { h?: number; children: React.ReactElement }) {
  return <div style={{ width: "100%", height: h }}><ResponsiveContainer width="100%" height="100%">{children}</ResponsiveContainer></div>;
}
const tipStyle = { borderRadius: 10, border: "1px solid #E2E8F0", fontSize: 12 };

export function SentimentDonut({ rows }: { rows: CustomerRow[] }) {
  const data = ["positive", "neutral", "negative"].map((l) => ({ name: l[0].toUpperCase() + l.slice(1), key: l, value: rows.filter((r) => r.label === l).length }));
  return (
    <div className="relative">
      <Box h={290}>
        <PieChart>
          <Pie data={data} dataKey="value" innerRadius="58%" outerRadius="88%" paddingAngle={1} stroke="none"
            label={({ percent }) => `${((percent ?? 0) * 100).toFixed(0)}%`} labelLine={false}>
            {data.map((d) => <Cell key={d.key} fill={SENT_COLORS[d.key]} />)}
          </Pie>
          <Tooltip contentStyle={tipStyle} />
          <Legend verticalAlign="top" height={30} />
        </PieChart>
      </Box>
      <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center pt-6">
        <div className="text-2xl font-bold text-slate-800">{rows.length}</div>
        <div className="text-xs text-slate-500">conversations</div>
      </div>
    </div>
  );
}

export function SentimentHistogram({ rows }: { rows: CustomerRow[] }) {
  const data = sentimentHistogram(rows);
  return (
    <Box h={290}>
      <BarChart data={data} barCategoryGap={1}>
        <CartesianGrid stroke="#EEF2F6" vertical={false} />
        <XAxis dataKey="x" {...AX} />
        <YAxis {...AX} allowDecimals={false} />
        <Tooltip contentStyle={tipStyle} />
        <Legend verticalAlign="top" height={30} />
        <Bar dataKey="negative" stackId="a" fill={SENT_COLORS.negative} />
        <Bar dataKey="neutral" stackId="a" fill={SENT_COLORS.neutral} />
        <Bar dataKey="positive" stackId="a" fill={SENT_COLORS.positive} />
      </BarChart>
    </Box>
  );
}

export function TopicBar({ topics }: { topics: Topic[] }) {
  const d = [...topics].filter((t) => t.mentions > 0).sort((a, b) => b.mentions - a.mentions).map((t) => ({ ...t, name: short(t.label) }));
  return (
    <Box h={Math.max(240, d.length * 50 + 50)}>
      <BarChart data={d} layout="vertical" margin={{ left: 10, right: 20 }}>
        <CartesianGrid stroke="#EEF2F6" horizontal={false} />
        <XAxis type="number" {...AX} allowDecimals={false} />
        <YAxis type="category" dataKey="name" width={170} {...AX} />
        <Tooltip contentStyle={tipStyle} formatter={(v) => [`${v} statements`, ""]} labelFormatter={(l, p) => {
          const t = p?.[0]?.payload as Topic | undefined;
          return t ? `${t.label} · avg sentiment ${t.avg_sentiment.toFixed(2)} · ${t.negative_pct.toFixed(0)}% negative` : String(l);
        }} />
        <Bar dataKey="mentions" radius={[0, 6, 6, 0]}>{d.map((t) => <Cell key={t.topic_id} fill={sentColor(t.avg_sentiment)} />)}</Bar>
      </BarChart>
    </Box>
  );
}

export function TopicStack({ topics }: { topics: Topic[] }) {
  const d = [...topics].filter((t) => t.mentions > 0).sort((a, b) => b.negative_pct - a.negative_pct).map((t) => ({ name: short(t.label), Negative: Number(t.negative_pct.toFixed(1)), Neutral: Number(t.neutral_pct.toFixed(1)), Positive: Number(t.positive_pct.toFixed(1)) }));
  return (
    <Box h={Math.max(240, d.length * 46 + 70)}>
      <BarChart data={d} layout="vertical" margin={{ left: 10, right: 20 }}>
        <CartesianGrid stroke="#EEF2F6" horizontal={false} />
        <XAxis type="number" domain={[0, 100]} unit="%" {...AX} />
        <YAxis type="category" dataKey="name" width={170} {...AX} />
        <Tooltip contentStyle={tipStyle} formatter={(v) => `${v}%`} />
        <Legend verticalAlign="top" height={30} />
        <Bar dataKey="Negative" stackId="s" fill={SENT_COLORS.negative} />
        <Bar dataKey="Neutral" stackId="s" fill={SENT_COLORS.neutral} />
        <Bar dataKey="Positive" stackId="s" fill={SENT_COLORS.positive} />
      </BarChart>
    </Box>
  );
}

export function SourceNegBar({ rows }: { rows: CustomerRow[] }) {
  const m = new Map<string, { n: number; neg: number }>();
  rows.forEach((r) => { if (!r.source) return; const x = m.get(r.source) ?? { n: 0, neg: 0 }; x.n++; if (r.label === "negative") x.neg++; m.set(r.source, x); });
  const d = [...m.entries()].map(([name, x]) => ({ name: short(name, 28), pct: Number(((x.neg / x.n) * 100).toFixed(1)) })).sort((a, b) => b.pct - a.pct);
  return (
    <Box h={Math.max(220, d.length * 40 + 50)}>
      <BarChart data={d} layout="vertical" margin={{ left: 10, right: 24 }}>
        <CartesianGrid stroke="#EEF2F6" horizontal={false} />
        <XAxis type="number" domain={[0, 100]} unit="%" {...AX} />
        <YAxis type="category" dataKey="name" width={170} {...AX} />
        <Tooltip contentStyle={tipStyle} formatter={(v) => `${v}% negative`} />
        <Bar dataKey="pct" fill={COLORS.neg} radius={[0, 6, 6, 0]} />
      </BarChart>
    </Box>
  );
}

export function ImportanceCoverage({ spots }: { spots: BlindSpot[] }) {
  const d = [...spots].sort((a, b) => a.rank - b.rank).map((s) => ({ name: short(s.topic_label), "Customer importance": Math.round(s.importance), "Company coverage": Math.round(s.coverage_norm) }));
  return (
    <Box h={Math.max(280, d.length * 72 + 60)}>
      <BarChart data={d} layout="vertical" margin={{ left: 10, right: 24 }} barGap={2}>
        <CartesianGrid stroke="#EEF2F6" horizontal={false} />
        <XAxis type="number" domain={[0, 100]} {...AX} />
        <YAxis type="category" dataKey="name" width={170} {...AX} />
        <Tooltip contentStyle={tipStyle} />
        <Legend verticalAlign="top" height={30} />
        <Bar dataKey="Customer importance" fill={COLORS.primary} radius={[0, 5, 5, 0]} />
        <Bar dataKey="Company coverage" fill="#F59E0B" radius={[0, 5, 5, 0]} />
      </BarChart>
    </Box>
  );
}

export function GapScatter({ spots }: { spots: BlindSpot[] }) {
  const d = spots.map((s) => ({ x: s.coverage_norm, y: s.importance, z: Math.max(40, s.mentions * 6), s }));
  return (
    <Box h={400}>
      <ScatterChart margin={{ top: 20, right: 20, bottom: 30, left: 10 }}>
        <CartesianGrid stroke="#EEF2F6" />
        <XAxis type="number" dataKey="x" name="Coverage" domain={[-5, 108]} label={{ value: "Company coverage index (0-100) →", position: "bottom", fill: "#64748B", fontSize: 12 }} {...AX} />
        <YAxis type="number" dataKey="y" name="Importance" domain={[0, 108]} label={{ value: "Customer importance →", angle: -90, position: "insideLeft", fill: "#64748B", fontSize: 12 }} {...AX} />
        <ZAxis type="number" dataKey="z" range={[500, 2600]} />
        <ReferenceLine x={30} stroke="#FCA5A5" strokeDasharray="4 4" />
        <ReferenceLine y={50} stroke="#FCA5A5" strokeDasharray="4 4" />
        <Tooltip cursor={false} contentStyle={tipStyle} content={({ payload }) => {
          const s = (payload?.[0]?.payload as { s: BlindSpot } | undefined)?.s;
          if (!s) return null;
          return (
            <div className="rounded-lg border border-slate-200 bg-white p-2.5 text-xs shadow">
              <div className="font-semibold">#{s.rank} {s.topic_label}</div>
              <div>Coverage {s.coverage_norm.toFixed(0)} · Importance {s.importance.toFixed(0)}</div>
              <div>Gap {s.gap.toFixed(0)} · Score {s.score.toFixed(1)} ({s.severity})</div>
            </div>
          );
        }} />
        <Scatter data={d} shape={(props: unknown) => {
          const p = props as { cx: number; cy: number; node?: { z: number }; payload: { s: BlindSpot; z: number } };
          const r = Math.max(15, Math.min(32, Math.sqrt(p.payload.z) * 1.7));
          return (
            <g>
              <circle cx={p.cx} cy={p.cy} r={r} fill={SEVERITY_COLORS[p.payload.s.severity]} fillOpacity={0.85} stroke="#fff" strokeWidth={1.5} />
              <text x={p.cx} y={p.cy} textAnchor="middle" dominantBaseline="central" fill="#fff" fontSize={12} fontWeight={700}>#{p.payload.s.rank}</text>
            </g>
          );
        }} />
      </ScatterChart>
    </Box>
  );
}

export function ScoreBar({ spots }: { spots: BlindSpot[] }) {
  const d = [...spots].sort((a, b) => a.rank - b.rank).map((s) => ({ name: short(s.topic_label), score: s.score, severity: s.severity }));
  return (
    <Box h={Math.max(240, d.length * 48 + 60)}>
      <BarChart data={d} layout="vertical" margin={{ left: 10, right: 40 }}>
        <CartesianGrid stroke="#EEF2F6" horizontal={false} />
        <XAxis type="number" domain={[0, 100]} {...AX} />
        <YAxis type="category" dataKey="name" width={170} {...AX} />
        {[20, 40, 60, 80].map((x) => <ReferenceLine key={x} x={x} stroke="#CBD5E1" strokeDasharray="3 3" />)}
        <Tooltip contentStyle={tipStyle} formatter={(v) => [Number(v).toFixed(1), "Blind Spot Score"]} />
        <Bar dataKey="score" radius={[0, 6, 6, 0]} label={{ position: "right", fill: "#334155", fontSize: 12, formatter: (v: unknown) => Number(v).toFixed(1) }}>
          {d.map((x) => <Cell key={x.name} fill={SEVERITY_COLORS[x.severity]} />)}
        </Bar>
      </BarChart>
    </Box>
  );
}

export function ComponentBars({ spot }: { spot: BlindSpot }) {
  const d = [
    { name: "Customer importance", v: spot.importance, c: COLORS.primary },
    { name: "Expectation gap", v: spot.gap, c: "#F97316" },
    { name: spot.trend_available ? "Issue trend" : "Issue trend (neutral)", v: spot.trend_used, c: "#0EA5E9" },
    { name: "Blind Spot Score", v: spot.score, c: SEVERITY_COLORS[spot.severity] },
  ];
  return (
    <Box h={230}>
      <BarChart data={d} layout="vertical" margin={{ left: 10, right: 40 }}>
        <XAxis type="number" domain={[0, 110]} hide />
        <YAxis type="category" dataKey="name" width={150} {...AX} />
        <Tooltip contentStyle={tipStyle} formatter={(v) => Number(v).toFixed(1)} />
        <Bar dataKey="v" radius={[0, 6, 6, 0]} label={{ position: "right", fill: "#334155", fontSize: 12, formatter: (v: unknown) => Number(v).toFixed(1) }}>
          {d.map((x) => <Cell key={x.name} fill={x.c} />)}
        </Bar>
      </BarChart>
    </Box>
  );
}

export function HBar({ data, color = "#F59E0B", unit = "", max }: { data: { name: string; value: number }[]; color?: string; unit?: string; max?: number }) {
  const d = [...data].sort((a, b) => b.value - a.value).map((x) => ({ ...x, name: short(x.name, 28) }));
  return (
    <Box h={Math.max(220, d.length * 38 + 50)}>
      <BarChart data={d} layout="vertical" margin={{ left: 10, right: 40 }}>
        <CartesianGrid stroke="#EEF2F6" horizontal={false} />
        <XAxis type="number" domain={max ? [0, max] : undefined} unit={unit} {...AX} />
        <YAxis type="category" dataKey="name" width={170} {...AX} />
        <Tooltip contentStyle={tipStyle} formatter={(v) => `${Number(v).toFixed(1)}${unit}`} />
        <Bar dataKey="value" fill={color} radius={[0, 6, 6, 0]} label={{ position: "right", fill: "#334155", fontSize: 12, formatter: (v: unknown) => `${Number(v).toFixed(0)}${unit}` }} />
      </BarChart>
    </Box>
  );
}

export type TrendMetric = "volume" | "share" | "neg_count";
export function TopicLines({ series, labels, ids, metric }: { series: SeriesRow[]; labels: Record<number, string>; ids: number[]; metric: TrendMetric }) {
  const periods = Array.from(new Set(series.map((s) => s.period))).sort();
  const data = periods.map((p) => {
    const row: Record<string, number | string | null> = { period: p.slice(0, 10) };
    ids.forEach((id) => { const r = series.find((s) => s.topic_id === id && s.period === p); row[String(id)] = r ? (r[metric] === null ? null : Number(Number(r[metric]).toFixed(2))) : null; });
    return row;
  });
  return (
    <Box h={380}>
      <LineChart data={data}>
        <CartesianGrid stroke="#EEF2F6" />
        <XAxis dataKey="period" {...AX} />
        <YAxis {...AX} />
        <Tooltip contentStyle={tipStyle} />
        <Legend verticalAlign="top" height={32} />
        {ids.map((id, i) => <Line key={id} name={short(labels[id] ?? String(id), 28)} type="monotone" dataKey={String(id)} stroke={PALETTE[i % PALETTE.length]} strokeWidth={2.2} dot={{ r: 3 }} connectNulls />)}
      </LineChart>
    </Box>
  );
}

export function SentimentTrend({ overall }: { overall: OverallRow[] }) {
  const d = overall.map((o) => ({ period: o.period.slice(0, 10), avg: o.avg_sentiment, ma: o.sentiment_ma }));
  return (
    <Box h={300}>
      <LineChart data={d}>
        <CartesianGrid stroke="#EEF2F6" />
        <XAxis dataKey="period" {...AX} />
        <YAxis domain={[-1, 1]} {...AX} />
        <ReferenceLine y={0} stroke="#CBD5E1" />
        <Tooltip contentStyle={tipStyle} formatter={(v) => (v === null ? "—" : Number(v).toFixed(2))} />
        <Legend verticalAlign="top" height={30} />
        <Line name="Avg sentiment" dataKey="avg" stroke="#94A3B8" strokeWidth={0} dot={{ r: 3, fill: "#94A3B8" }} />
        <Line name="3-period moving avg" dataKey="ma" stroke={COLORS.primary} strokeWidth={3} dot={false} />
      </LineChart>
    </Box>
  );
}

export function NegativeShareTrend({ overall }: { overall: OverallRow[] }) {
  const d = overall.map((o) => ({ period: o.period.slice(0, 10), v: o.negative_share }));
  return (
    <Box h={300}>
      <AreaChart data={d}>
        <CartesianGrid stroke="#EEF2F6" />
        <XAxis dataKey="period" {...AX} />
        <YAxis domain={[0, 100]} unit="%" {...AX} />
        <Tooltip contentStyle={tipStyle} formatter={(v) => (v === null ? "—" : `${Number(v).toFixed(0)}%`)} />
        <Area name="% negative" dataKey="v" stroke={COLORS.neg} fill={COLORS.neg} fillOpacity={0.12} strokeWidth={2.5} />
      </AreaChart>
    </Box>
  );
}

export function NegativeHeatmap({ series, labels }: { series: SeriesRow[]; labels: Record<number, string> }) {
  const periods = Array.from(new Set(series.map((s) => s.period))).sort();
  const ids = Array.from(new Set(series.map((s) => s.topic_id)));
  const max = Math.max(1, ...series.map((s) => s.neg_count));
  return (
    <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white p-3">
      <table className="text-xs">
        <thead>
          <tr><th className="pr-3" />{periods.map((p) => <th key={p} className="px-0.5 pb-1 font-normal text-slate-500">{p.slice(5, 10)}</th>)}</tr>
        </thead>
        <tbody>
          {ids.map((id) => (
            <tr key={id}>
              <td className="whitespace-nowrap pr-3 text-right text-slate-600">{short(labels[id] ?? String(id), 30)}</td>
              {periods.map((p) => {
                const v = series.find((s) => s.topic_id === id && s.period === p)?.neg_count ?? 0;
                return <td key={p} className="p-0.5"><div title={`${v} negative`} className="flex h-7 w-9 items-center justify-center rounded text-[10px]" style={{ background: `rgba(220,38,38,${0.06 + (v / max) * 0.94})`, color: v / max > 0.55 ? "#fff" : "#475569" }}>{v || ""}</div></td>;
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
