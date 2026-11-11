"use client";

import { Gate } from "@/components/Gate";
import { HBar } from "@/components/charts";
import { Expander, KpiRow, Note, PageHeader, Section, Table, Td } from "@/components/ui";
import { COLORS } from "@/lib/constants";

export default function CompanyCommunication() {
  return (
    <>
      <PageHeader title="Company Communication" subtitle="What the company is actually telling its customers (analysed separately from customer data)" />
      <Gate>
        {({ bundle, view }) => {
          const themes = bundle.company_themes;
          const promises = bundle.meta.promises ?? [];
          const types = new Map<string, number>();
          promises.forEach((p) => p.promise_types.forEach((t) => types.set(t, (types.get(t) ?? 0) + 1)));
          const spots = [...view.blindSpots];
          return (
            <>
              <KpiRow items={[
                { label: "Company messages analysed", value: bundle.overview.total_company_messages, sub: "after cleaning", accent: COLORS.warn },
                { label: "Messaging themes", value: themes.length, sub: "discovered by clustering", accent: COLORS.primary },
                { label: "Messages with promises/claims", value: promises.length, sub: "speed · price · trust · rewards …", accent: "#0EA5E9" },
                { label: "Off-topic share", value: `${bundle.overview.offtopic_company_share_pct.toFixed(0)}%`, sub: "unrelated to any customer topic", accent: COLORS.neu },
              ]} />
              <div className="grid gap-6 lg:grid-cols-2">
                <Section title="Main messaging themes" subtitle="Share = messages in the theme ÷ all company messages × 100">
                  <HBar data={themes.map((t) => ({ name: t.label, value: t.share_pct }))} unit="%" />
                </Section>
                <Section title="Communication coverage by customer topic" subtitle="Share of company messaging that semantically addresses each topic customers discuss">
                  <HBar data={spots.map((s) => ({ name: s.topic_label, value: s.coverage_share * 100 }))} unit="%" />
                </Section>
              </div>

              <Section title="Theme details" subtitle="Keywords come from class-based TF-IDF; examples are real messages from the dataset">
                {themes.map((t) => (
                  <Expander key={t.theme_id} title={`${t.label} — ${t.share_pct.toFixed(0)}% of messages (${t.n_messages})`}>
                    <div className="mb-2 text-sm"><b>Keywords:</b> {(t.keywords ?? []).join(", ")}</div>
                    <ul className="list-disc space-y-1 pl-5 text-sm text-slate-700">{(t.examples ?? []).map((e, i) => <li key={i}>“{e}”</li>)}</ul>
                  </Expander>
                ))}
              </Section>

              <div className="grid gap-6 lg:grid-cols-2">
                <Section title="Most promoted features, services & words" subtitle="Number of messages containing each word">
                  <HBar color={COLORS.primary} data={(bundle.meta.company_keywords ?? []).slice(0, 15).map(([w, n]) => ({ name: w, value: n }))} />
                </Section>
                <Section title="Company promises & benefits detected">
                  {promises.length === 0 ? <Note>No explicit promises detected.</Note> : (
                    <>
                      <Table head={["Promise type", "Messages"]}>{[...types.entries()].sort((a, b) => b[1] - a[1]).map(([t, n]) => <tr key={t}><Td>{t}</Td><Td>{n}</Td></tr>)}</Table>
                      <div className="mt-3"><Expander title="All promise messages">
                        <ul className="space-y-1.5 text-sm text-slate-700">{promises.map((p, i) => <li key={i}>“{p.text}” <span className="text-xs text-slate-400">— {p.promise_types.join(", ")}</span></li>)}</ul>
                      </Expander></div>
                    </>
                  )}
                </Section>
              </div>

              <Section title="Closest company messages for each customer topic" subtitle="Semantic (SBERT cosine) similarity between a customer topic and the company's messages — shows what the company says nearest to each concern">
                {[...spots].sort((a, b) => a.coverage_norm - b.coverage_norm).map((s) => {
                  const best = s.closest_company_messages?.[0]?.similarity ?? 0;
                  return (
                    <Expander key={s.topic_id} title={`${s.topic_label} — coverage index ${s.coverage_norm.toFixed(0)}/100 · best match similarity ${best.toFixed(2)}`}>
                      <ul className="list-disc space-y-1 pl-5 text-sm text-slate-700">{(s.closest_company_messages ?? []).map((m, i) => <li key={i}>“{m.text}” — similarity <b>{m.similarity.toFixed(2)}</b></li>)}</ul>
                    </Expander>
                  );
                })}
              </Section>
              {!bundle.meta.semantic_embeddings && <Note warn>Offline TF-IDF embeddings were used, so semantic matching is weaker than with SBERT.</Note>}
            </>
          );
        }}
      </Gate>
    </>
  );
}
