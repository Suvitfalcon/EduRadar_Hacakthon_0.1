import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api.js";
import { ErrorBox, Loading, Notice, Pager, PriorityBadge, fmtPct, useAsync } from "../ui.jsx";

export default function DataQuality() {
  const [page, setPage] = useState(1);
  const [onlyInsufficient, setOnly] = useState(false);
  const { data, error, loading, reload } = useAsync(() => api.dataQuality({ page, page_size: 20, insufficient: onlyInsufficient ? "true" : "" }), [page, onlyInsufficient]);
  return (
    <div className="space-y-4">
      <div><h1>Data checks</h1><p className="mt-1 text-sm text-slate-600">Incomplete records are flagged. When evidence cannot support a result, EduRadar shows "Insufficient Data" instead of guessing.</p></div>
      <ErrorBox error={error} onRetry={reload} />
      {data && <Notice tone="indigo" title="Insufficient-data rule">{data.rule}</Notice>}
      {data?.common_gaps?.length > 0 && (
        <section className="card"><h2>Most common gaps</h2>
          <ul className="mt-2 grid gap-x-8 gap-y-1 text-sm sm:grid-cols-2">{data.common_gaps.map((g) => <li key={g.field} className="flex justify-between"><span>{g.field}</span><span className="tabular-nums text-slate-600">{g.records.toLocaleString()} records</span></li>)}</ul></section>
      )}
      <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={onlyInsufficient} onChange={(e) => { setOnly(e.target.checked); setPage(1); }} /> Only show "Insufficient Data"</label>
      <div className="card overflow-hidden p-0">
        {loading && !data ? <Loading /> : (
          <>
            <div className="overflow-x-auto"><table className="w-full">
              <thead><tr><th className="th">Student</th><th className="th">Priority</th><th className="th">Complete</th><th className="th">Issues</th></tr></thead>
              <tbody className="divide-y divide-slate-100">
                {data?.items.map((r) => (
                  <tr key={r.student_id} className="align-top hover:bg-slate-50">
                    <td className="td"><Link className="font-medium text-brand-700 hover:underline" to={`/students/${r.student_id}`}>{r.name}</Link><div className="text-xs text-slate-500">{r.student_id}</div></td>
                    <td className="td"><PriorityBadge value={r.priority} /></td>
                    <td className="td tabular-nums">{fmtPct(r.completeness_pct)}</td>
                    <td className="td text-xs text-slate-600">
                      {r.invalid.map((m) => <div key={m} className="text-red-700">{m}</div>)}
                      {r.missing.slice(0, 4).map((m) => <div key={m}>Missing - {m}</div>)}
                      {r.missing.length > 4 && <div>+ {r.missing.length - 4} more missing</div>}
                    </td>
                  </tr>
                ))}
                {data && !data.items.length && <tr><td className="td text-slate-500" colSpan={4}>No incomplete records.</td></tr>}
              </tbody></table></div>
            {data && <Pager page={page} pageSize={20} total={data.total} onPage={setPage} />}
          </>
        )}
      </div>
    </div>
  );
}
