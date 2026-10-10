import { useEffect, useState } from "react";

export const PRIORITY_STYLE = {
  High: "bg-red-50 text-red-800 ring-red-200",
  Medium: "bg-amber-50 text-amber-800 ring-amber-200",
  Low: "bg-emerald-50 text-emerald-800 ring-emerald-200",
  "Insufficient Data": "bg-slate-100 text-slate-700 ring-slate-300",
};
const PRIORITY_ICON = { High: "▲", Medium: "●", Low: "▼", "Insufficient Data": "?" };

export function PriorityBadge({ value, big }) {
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full font-medium ring-1 ring-inset ${PRIORITY_STYLE[value] || PRIORITY_STYLE.Low} ${big ? "px-4 py-1.5 text-base" : "px-2.5 py-0.5 text-xs"}`}>
      <span aria-hidden="true" className="text-[0.7em]">{PRIORITY_ICON[value]}</span>
      {value}
    </span>
  );
}

export function Tag({ children, tone = "slate", title }) {
  const tones = {
    slate: "bg-slate-100 text-slate-700 ring-slate-200",
    amber: "bg-amber-50 text-amber-800 ring-amber-200",
    red: "bg-red-50 text-red-800 ring-red-200",
    green: "bg-emerald-50 text-emerald-800 ring-emerald-200",
    indigo: "bg-brand-50 text-brand-700 ring-brand-100",
  };
  return <span title={title} className={`inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${tones[tone]}`}>{children}</span>;
}

export function Stat({ label, value, hint, tone, to }) {
  const color = tone === "red" ? "text-red-700" : tone === "amber" ? "text-amber-700" : "text-slate-900";
  return (
    <div className="card">
      <div className="text-xs font-medium text-slate-500">{label}</div>
      <div className={`mt-1 text-3xl font-semibold tabular-nums ${color}`}>{value ?? "-"}</div>
      {hint && <div className="mt-1 text-xs text-slate-500">{hint}</div>}
    </div>
  );
}

export function Loading({ label = "Loading..." }) {
  return <div className="p-8 text-sm text-slate-500" role="status">{label}</div>;
}

export function ErrorBox({ error, onRetry }) {
  if (!error) return null;
  return (
    <div role="alert" className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800">
      {error.message || String(error)}
      {onRetry && <button className="ml-3 underline" onClick={onRetry}>Retry</button>}
    </div>
  );
}

export function Notice({ tone = "slate", title, children }) {
  const t = { slate: "border-slate-200 bg-slate-50 text-slate-700", amber: "border-amber-200 bg-amber-50 text-amber-900", green: "border-emerald-200 bg-emerald-50 text-emerald-900", red: "border-red-200 bg-red-50 text-red-800", indigo: "border-brand-100 bg-brand-50 text-brand-900" }[tone];
  return (
    <div className={`rounded-lg border p-3 text-sm ${t}`}>
      {title && <div className="font-medium">{title}</div>}
      <div>{children}</div>
    </div>
  );
}

export function Pager({ page, pageSize, total, onPage }) {
  const pages = Math.max(1, Math.ceil(total / pageSize));
  return (
    <div className="flex items-center justify-between border-t border-slate-200 px-3 py-3 text-sm text-slate-600">
      <span>{total.toLocaleString()} result{total === 1 ? "" : "s"}</span>
      <div className="flex items-center gap-2">
        <button className="btn-ghost" disabled={page <= 1} onClick={() => onPage(page - 1)}>Previous</button>
        <span className="tabular-nums">Page {page} of {pages}</span>
        <button className="btn-ghost" disabled={page >= pages} onClick={() => onPage(page + 1)}>Next</button>
      </div>
    </div>
  );
}

export function useAsync(fn, deps) {
  const [state, set] = useState({ data: null, error: null, loading: true });
  const [tick, setTick] = useState(0);
  useEffect(() => {
    let live = true;
    set((s) => ({ ...s, loading: true, error: null }));
    fn().then((data) => live && set({ data, error: null, loading: false }))
      .catch((error) => live && set({ data: null, error, loading: false }));
    return () => { live = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick]);
  return { ...state, reload: () => setTick((t) => t + 1) };
}

export const fmtPct = (v, d = 0) => (v == null ? "-" : `${Number(v).toFixed(d)}%`);
export const fmtDate = (s) => (s ? new Date(s).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" }) : "-");

export function SourceTag({ source }) {
  if (source === "synthetic") return <Tag tone="indigo" title="Simulated record from the synthetic dataset">Simulated</Tag>;
  if (source === "simulated-edge-case") return <Tag tone="indigo" title="Simulated record built to demonstrate an edge case">Simulated edge case</Tag>;
  return <Tag>Uploaded</Tag>;
}

/* ---------- weekly line chart (breaks the line where data is missing) ---------- */
export function WeeklyChart({ values, color = "#4338ca", label, unit = "%", max = 100 }) {
  const W = 260, H = 110, pad = { l: 30, r: 10, t: 10, b: 22 };
  const x = (i) => pad.l + (i * (W - pad.l - pad.r)) / 3;
  const y = (v) => pad.t + (1 - v / max) * (H - pad.t - pad.b);
  const segs = [];
  let cur = [];
  values.forEach((v, i) => {
    if (v == null) { if (cur.length) segs.push(cur); cur = []; } else cur.push([x(i), y(v)]);
  });
  if (cur.length) segs.push(cur);
  const desc = values.map((v, i) => `week ${i + 1}: ${v == null ? "missing" : v.toFixed(0) + unit}`).join(", ");
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label={`${label}. ${desc}`}>
      {[0, 50, 100].map((g) => (
        <g key={g}>
          <line x1={pad.l} x2={W - pad.r} y1={y((g / 100) * max)} y2={y((g / 100) * max)} stroke="#e2e8f0" />
          <text x={pad.l - 4} y={y((g / 100) * max) + 4} textAnchor="end" fontSize="10" fill="#64748b">{Math.round((g / 100) * max)}</text>
        </g>
      ))}
      {segs.map((s, i) => s.length > 1 && <polyline key={i} points={s.map((p) => p.join(",")).join(" ")} fill="none" stroke={color} strokeWidth="2.5" strokeLinejoin="round" />)}
      {values.map((v, i) => (
        <g key={i}>
          <text x={x(i)} y={H - 6} textAnchor="middle" fontSize="10" fill="#64748b">W{i + 1}</text>
          {v == null ? (
            <text x={x(i)} y={y(max * 0.5) + 4} textAnchor="middle" fontSize="10" fill="#94a3b8">n/a</text>
          ) : (
            <>
              <circle cx={x(i)} cy={y(v)} r="4" fill="white" stroke={color} strokeWidth="2.5" />
              <text x={x(i)} y={y(v) - 8} textAnchor="middle" fontSize="10" fontWeight="600" fill="#334155">{v.toFixed(0)}</text>
            </>
          )}
        </g>
      ))}
    </svg>
  );
}

export function StackedBar({ parts }) {
  const total = parts.reduce((a, p) => a + p.value, 0) || 1;
  const colors = { High: "bg-red-500", Medium: "bg-amber-400", Low: "bg-emerald-500", "Insufficient Data": "bg-slate-400" };
  return (
    <div className="flex h-3 w-full overflow-hidden rounded-full bg-slate-100" role="img" aria-label={parts.map((p) => `${p.label}: ${p.value}`).join(", ")}>
      {parts.map((p) => p.value > 0 && <div key={p.label} className={colors[p.label]} style={{ width: `${(p.value / total) * 100}%` }} title={`${p.label}: ${p.value}`} />)}
    </div>
  );
}
