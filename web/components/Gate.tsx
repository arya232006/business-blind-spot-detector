"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { useApp } from "@/lib/store";
import type { Bundle } from "@/lib/types";
import type { View } from "@/lib/derive";
import { ErrorBox, Note, Spinner } from "./ui";

/** Handles loading / empty / error states, the synthetic-data banner, and "filters excluded everything". */
export function Gate({ children, needsRecords = true }: { children: (ctx: { bundle: Bundle; view: View }) => ReactNode; needsRecords?: boolean }) {
  const app = useApp();
  if (!app.ready) return <Spinner label="Connecting to the backend…" />;
  if (app.apiStatus === "offline") return null; // the shell already shows the connection error
  if (!app.company) {
    return <Note>👈 Create a company in the sidebar to get started.</Note>;
  }
  if (app.bundleLoading) return <Spinner label="Loading analysis…" />;
  if (app.bundleError) return <ErrorBox>{app.bundleError}</ErrorBox>;
  if (!app.bundle || !app.view) {
    return (
      <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-8">
        <h3 className="text-lg font-semibold">No analysis for “{app.company.name}” yet</h3>
        <p className="mt-1 text-sm text-slate-600">Load the NovaCart demo data (or upload your own customer + company datasets) and press <b>Run analysis</b>.</p>
        <Link href="/data" className="mt-4 inline-block rounded-xl bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700">Open Data Management →</Link>
      </div>
    );
  }
  return (
    <>
      {app.bundle.session.is_synthetic && (
        <div className="mb-3 rounded-xl border border-amber-300 bg-amber-100 px-3.5 py-2 text-sm font-semibold text-amber-900">
          ⚠ SYNTHETIC DEMO DATA — every record in this analysis was generated for demonstration; it is not real customer feedback.
        </div>
      )}
      {needsRecords && app.view.customer.length === 0 ? (
        <Note warn>The current filters exclude every record. Clear some filters in the sidebar.</Note>
      ) : children({ bundle: app.bundle, view: app.view })}
    </>
  );
}
