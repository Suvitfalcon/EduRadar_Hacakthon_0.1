import { Link, useSearchParams } from "react-router-dom";
import { useEffect, useState } from "react";
import { api } from "../api.js";
import { ErrorBox, Loading, Pager, PriorityBadge, SourceTag, Tag, fmtPct, useAsync } from "../ui.jsx";

const PRIORITIES = ["High", "Medium", "Low", "Insufficient Data"];

export default function Students() {
  const [sp, setSp] = useSearchParams();
  const f = Object.fromEntries(sp.entries());
  const page = Number(f.page || 1);
  const [search, setSearch] = useState(f.search || "");
  const set = (patch) => {
    const next = { ...f, ...patch };
    Object.keys(next).forEach((k) => (next[k] === "" || next[k] == null) && delete next[k]);
    if (!("page" in patch)) delete next.page;
    setSp(next);
  };
  useEffect(() => {
    const t = setTimeout(() => search !== (f.search || "") && set({ search }), 350);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search]);

  const { data: depts } = useAsync(() => api.departments(), []);
  const { data, error, loading, reload } = useAsync(() => api.students({ ...f, page, page_size: 25 }), [sp.toString()]);
  const pri = f.priority ? f.priority.split(",") : [];

  return (
    <div className="space-y-4">
      <div>
        <h1>Students</h1>
        <p className="mt-1 text-sm text-slate-600">Sorted by support priority, highest first.</p>
      </div>

      <div className="card grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        <div className="lg:col-span-2">
          <label className="label" htmlFor="q">Search name or ID</label>
          <input id="q" className="input" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="e.g. Sana or S00047" />
        </div>
        <div>
          <label className="label" htmlFor="pri">Priority</label>
          <select id="pri" className="input" value={f.priority || ""} onChange={(e) => set({ priority: e.target.value })}>
            <option value="">All</option>
            {PRIORITIES.map((p) => <option key={p}>{p}</option>)}
            <option value="High,Medium">High + Medium</option>
          </select>
        </div>
        <div>
          <label className="label" htmlFor="dep">Department</label>
          <select id="dep" className="input" value={f.department || ""} onChange={(e) => set({ department: e.target.value })}>
            <option value="">All</option>
            {(depts || []).map((d) => <option key={d}>{d}</option>)}
          </select>
        </div>
        <div>
          <label className="label" htmlFor="flag">Signal</label>
          <select id="flag" className="input" value={f.alert === "any" ? "alert" : f.trend ? "trend" : f.needs_action ? "plan" : f.incomplete ? "inc" : f.reviewed ? "rev-" + f.reviewed : f.source ? "edge" : ""}
            onChange={(e) => {
              const v = e.target.value;
              set({ alert: v === "alert" ? "any" : "", trend: v === "trend" ? "true" : "", needs_action: v === "plan" ? "true" : "",
                incomplete: v === "inc" ? "true" : "", reviewed: v === "rev-false" ? "false" : v === "rev-true" ? "true" : "",
                source: v === "edge" ? "simulated-edge-case" : "" });
            }}>
            <option value="">Any</option>
            <option value="alert">Attendance alert</option>
            <option value="trend">Sustained decline</option>
            <option value="plan">Needs a support plan</option>
            <option value="inc">Incomplete data</option>
            <option value="rev-false">Not yet reviewed</option>
            <option value="rev-true">Reviewed</option>
            <option value="edge">Simulated edge cases</option>
          </select>
        </div>
      </div>
      {pri.length > 0 && <div className="text-sm text-slate-600">Filtered by: {pri.map((p) => <PriorityBadge key={p} value={p} />)}</div>}

      <ErrorBox error={error} onRetry={reload} />
      <div className="card overflow-hidden p-0">
        {loading && !data ? <Loading /> : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr><th className="th">Student</th><th className="th">Department</th><th className="th">Priority</th><th className="th">Model score</th><th className="th">Signals</th></tr>
                </thead>
                <tbody className={`divide-y divide-slate-100 ${loading ? "opacity-60" : ""}`}>
                  {data?.items.map((r) => (
                    <tr key={r.student_id} className="hover:bg-slate-50">
                      <td className="td">
                        <Link className="font-medium text-brand-700 hover:underline" to={`/students/${r.student_id}`}>{r.name}</Link>
                        <div className="text-xs text-slate-500">{r.student_id}{r.year_of_study ? ` · Year ${r.year_of_study}` : ""}</div>
                      </td>
                      <td className="td">{r.department}</td>
                      <td className="td">
                        <PriorityBadge value={r.priority} />
                        {r.overridden && <div className="mt-1 text-xs text-slate-500">model said {r.model_priority}</div>}
                      </td>
                      <td className="td tabular-nums">{r.score == null ? "-" : fmtPct(r.score * 100)}</td>
                      <td className="td"><div className="flex flex-wrap gap-1">
                        {r.attendance_alert !== "No alert" && <Tag tone="amber">{r.attendance_alert}</Tag>}
                        {r.trend_warning && <Tag tone="red">Sustained decline</Tag>}
                        {r.incomplete && <Tag>Incomplete data</Tag>}
                        {r.reviewed && <Tag tone="green">Reviewed</Tag>}
                        {r.open_interventions > 0 && <Tag tone="indigo">Follow-up open</Tag>}
                        <SourceTag source={r.data_source} />
                      </div></td>
                    </tr>
                  ))}
                  {data && !data.items.length && <tr><td className="td text-slate-500" colSpan={5}>No students match these filters.</td></tr>}
                </tbody>
              </table>
            </div>
            {data && <Pager page={page} pageSize={25} total={data.total} onPage={(p) => set({ page: String(p) })} />}
          </>
        )}
      </div>
    </div>
  );
}
