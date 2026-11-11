"use client";

import { useState, type ButtonHTMLAttributes, type ReactNode } from "react";
import { CLASS_COLORS, CLASS_LABELS, COLORS, PRIORITY_COLORS, SEVERITY_COLORS } from "@/lib/constants";

export function PageHeader({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <div className="mb-5">
      <h1 className="text-[1.75rem] font-bold text-slate-900">{title}</h1>
      {subtitle && <p className="mt-0.5 text-[0.95rem] text-slate-500">{subtitle}</p>}
    </div>
  );
}

export function Section({ title, subtitle, children, right }: { title: string; subtitle?: string; children?: ReactNode; right?: ReactNode }) {
  return (
    <section className="mt-7">
      <div className="mb-3 flex items-end justify-between gap-3">
        <div>
          <h2 className="text-lg font-bold text-slate-900">{title}</h2>
          {subtitle && <p className="text-sm text-slate-500">{subtitle}</p>}
        </div>
        {right}
      </div>
      {children}
    </section>
  );
}

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={`rounded-2xl border border-slate-200 bg-white p-4 shadow-[0_1px_2px_rgba(15,23,42,.04)] ${className}`}>{children}</div>;
}

export function KpiRow({ items }: { items: { label: string; value: ReactNode; sub?: string; accent?: string }[] }) {
  return (
    <div className="mb-2 grid gap-3.5" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))" }}>
      {items.map((k) => (
        <div key={k.label} className="relative overflow-hidden rounded-2xl border border-slate-200 bg-white px-4 py-3.5 shadow-[0_1px_2px_rgba(15,23,42,.04)]">
          <span className="absolute inset-y-0 left-0 w-1" style={{ background: k.accent ?? COLORS.primary }} />
          <div className="text-[0.7rem] font-semibold uppercase tracking-wider text-slate-500">{k.label}</div>
          <div className="mt-1 text-[1.85rem] font-bold leading-tight text-slate-900">{k.value}</div>
          {k.sub && <div className="mt-0.5 text-xs text-slate-500">{k.sub}</div>}
        </div>
      ))}
    </div>
  );
}

export function Badge({ children, color = COLORS.primary, soft = false }: { children: ReactNode; color?: string; soft?: boolean }) {
  if (soft) return <span className="mr-1.5 inline-block rounded-full border border-indigo-200 bg-indigo-50 px-2.5 py-0.5 text-[0.7rem] font-semibold text-indigo-800">{children}</span>;
  return <span className="mr-1.5 inline-block rounded-full px-2.5 py-0.5 text-[0.7rem] font-semibold text-white" style={{ background: color }}>{children}</span>;
}
export const SeverityBadge = ({ s }: { s: string }) => <Badge color={SEVERITY_COLORS[s] ?? "#64748B"}>{s}</Badge>;
export const ClassBadge = ({ c }: { c: string }) => <Badge color={CLASS_COLORS[c] ?? "#64748B"}>{CLASS_LABELS[c] ?? c}</Badge>;
export const PriorityBadge = ({ p }: { p: string }) => <Badge color={PRIORITY_COLORS[p.slice(0, 2)] ?? "#64748B"}>{p}</Badge>;

export function Meter({ value, color = COLORS.primary }: { value: number; color?: string }) {
  return (
    <div className="mt-1.5 h-2 overflow-hidden rounded-full bg-slate-200">
      <div className="h-full rounded-full" style={{ width: `${Math.max(0, Math.min(100, value || 0))}%`, background: color }} />
    </div>
  );
}

export function Note({ children, warn = false }: { children: ReactNode; warn?: boolean }) {
  return <div className={`my-2 rounded-xl border px-3.5 py-2.5 text-sm ${warn ? "border-amber-200 bg-amber-50 text-amber-900" : "border-blue-200 bg-blue-50 text-blue-900"}`}>{children}</div>;
}

export function ErrorBox({ children }: { children: ReactNode }) {
  return <div className="my-2 rounded-xl border border-red-200 bg-red-50 px-3.5 py-2.5 text-sm text-red-800">{children}</div>;
}

export function SuccessBox({ children }: { children: ReactNode }) {
  return <div className="my-2 rounded-xl border border-emerald-200 bg-emerald-50 px-3.5 py-2.5 text-sm text-emerald-800">{children}</div>;
}

export function Quote({ text, meta }: { text: string; meta?: string }) {
  return (
    <div className="my-1.5 border-l-[3px] border-slate-300 py-0.5 pl-2.5 text-sm italic text-slate-700">
      “{text}” {meta && <span className="not-italic text-slate-400">{meta}</span>}
    </div>
  );
}

export function Btn({ variant = "secondary", className = "", ...p }: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "secondary" | "danger" }) {
  const base = "inline-flex items-center justify-center gap-1.5 rounded-xl px-4 py-2 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-50";
  const v = variant === "primary" ? "bg-indigo-600 text-white hover:bg-indigo-700" : variant === "danger" ? "border border-red-200 bg-white text-red-700 hover:bg-red-50" : "border border-slate-300 bg-white text-slate-800 hover:bg-slate-50";
  return <button {...p} className={`${base} ${v} ${className}`} />;
}

export function Tabs({ tabs, children }: { tabs: string[]; children: (active: string) => ReactNode }) {
  const [active, setActive] = useState(tabs[0]);
  return (
    <div>
      <div className="mb-4 flex flex-wrap gap-1 border-b border-slate-200">
        {tabs.map((t) => (
          <button key={t} onClick={() => setActive(t)} className={`-mb-px border-b-2 px-3.5 py-2 text-sm font-semibold transition ${active === t ? "border-indigo-600 text-indigo-600" : "border-transparent text-slate-600 hover:text-slate-900"}`}>
            {t}
          </button>
        ))}
      </div>
      {children(active)}
    </div>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <div className="rounded-2xl border border-dashed border-slate-300 bg-white/60 px-6 py-10 text-center text-sm text-slate-500">{children}</div>;
}

export function Spinner({ label }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 py-6 text-sm text-slate-500">
      <span className="h-4 w-4 animate-spin rounded-full border-2 border-slate-300 border-t-indigo-600" /> {label ?? "Loading…"}
    </div>
  );
}

export function Expander({ title, children, defaultOpen = false }: { title: ReactNode; children: ReactNode; defaultOpen?: boolean }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="mb-2 rounded-xl border border-slate-200 bg-white">
      <button onClick={() => setOpen(!open)} className="flex w-full items-center gap-2 px-3.5 py-2.5 text-left text-sm font-medium text-slate-800">
        <span className={`text-xs transition ${open ? "rotate-90" : ""}`}>▶</span> {title}
      </button>
      {open && <div className="border-t border-slate-100 px-3.5 py-3">{children}</div>}
    </div>
  );
}

export function Table({ head, children, className = "" }: { head: string[]; children: ReactNode; className?: string }) {
  return (
    <div className={`overflow-x-auto rounded-xl border border-slate-200 bg-white ${className}`}>
      <table className="w-full text-sm">
        <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
          <tr>{head.map((h) => <th key={h} className="whitespace-nowrap px-3 py-2 font-semibold">{h}</th>)}</tr>
        </thead>
        <tbody className="divide-y divide-slate-100">{children}</tbody>
      </table>
    </div>
  );
}
export const Td = ({ children, className = "" }: { children?: ReactNode; className?: string }) => <td className={`px-3 py-2 align-top ${className}`}>{children}</td>;

export function Bar({ value, color = COLORS.primary, label }: { value: number; color?: string; label?: string }) {
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-20 overflow-hidden rounded-full bg-slate-200"><div className="h-full rounded-full" style={{ width: `${Math.max(0, Math.min(100, value))}%`, background: color }} /></div>
      <span className="tabular-nums text-slate-700">{label ?? value.toFixed(0)}</span>
    </div>
  );
}

export function Slider({ label, value, min, max, step, onChange }: { label: string; value: number; min: number; max: number; step: number; onChange: (v: number) => void }) {
  return (
    <label className="block text-sm text-slate-700">
      <div className="flex justify-between"><span>{label}</span><span className="tabular-nums font-semibold text-indigo-700">{value}</span></div>
      <input type="range" min={min} max={max} step={step} value={value} onChange={(e) => onChange(Number(e.target.value))} className="w-full accent-indigo-600" />
    </label>
  );
}

export function MultiSelect({ label, options, value, onChange, dark = false }: { label: string; options: { value: string; label: string }[]; value: string[]; onChange: (v: string[]) => void; dark?: boolean }) {
  const [open, setOpen] = useState(false);
  const labelCls = dark ? "text-slate-400" : "text-slate-500";
  return (
    <div className="relative mb-3">
      <div className={`mb-1 text-[0.7rem] font-semibold uppercase tracking-wider ${labelCls}`}>{label}</div>
      <button onClick={() => setOpen(!open)} className="flex min-h-9 w-full flex-wrap items-center gap-1 rounded-lg border border-slate-300 bg-white px-2 py-1 text-left text-sm text-slate-800">
        {value.length === 0 ? <span className="text-slate-500">All</span> : value.map((v) => (
          <span key={v} className="rounded bg-indigo-600 px-1.5 py-0.5 text-xs text-white">{options.find((o) => o.value === v)?.label ?? v}</span>
        ))}
        <span className="ml-auto text-xs text-slate-400">▾</span>
      </button>
      {open && (
        <>
          <div className="fixed inset-0 z-10" onClick={() => setOpen(false)} />
          <div className="absolute z-20 mt-1 max-h-60 w-full overflow-auto rounded-lg border border-slate-200 bg-white p-1 shadow-lg">
            {options.map((o) => {
              const on = value.includes(o.value);
              return (
                <button key={o.value} onClick={() => onChange(on ? value.filter((x) => x !== o.value) : [...value, o.value])} className={`flex w-full items-center gap-2 rounded px-2 py-1.5 text-left text-sm text-slate-800 hover:bg-slate-100 ${on ? "font-semibold" : ""}`}>
                  <span className={`flex h-4 w-4 items-center justify-center rounded border text-[10px] ${on ? "border-indigo-600 bg-indigo-600 text-white" : "border-slate-300"}`}>{on ? "✓" : ""}</span>
                  <span className="truncate">{o.label}</span>
                </button>
              );
            })}
            {value.length > 0 && <button onClick={() => onChange([])} className="mt-1 w-full rounded px-2 py-1 text-left text-xs text-indigo-600 hover:bg-slate-100">Clear</button>}
          </div>
        </>
      )}
    </div>
  );
}
