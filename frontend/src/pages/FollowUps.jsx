import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "../api.js";
import { ErrorBox, Loading, Pager, PriorityBadge, Tag, fmtDate, useAsync } from "../ui.jsx";

export default function FollowUps() {
  const [sp, setSp] = useSearchParams();
  const [page, setPage] = useState(1);
  const status = sp.get("status") || "";
  const overdue = sp.get("overdue") || "";
  const { data, error, loading, reload } = useAsync(() => api.interventions({ status, overdue, page, page_size: 25 }), [status, overdue, page]);
  const choose = (v) => { setPage(1); setSp(v === "overdue" ? { overdue: "true" } : v ? { status: v } : {}); };
  const current = overdue ? "overdue" : status;
  return (
    <div className="space-y-4">
      <div><h1>Support tracking</h1><p className="mt-1 text-sm text-slate-600">Every planned action, its owner and its follow-up date. Open a student to add a plan or record an outcome.</p></div>
      <div className="flex flex-wrap gap-2" role="tablist" aria-label="Status filter">
        {[["", "All"], ["Planned", "Planned"], ["In progress", "In progress"], ["overdue", "Overdue"], ["Completed", "Completed"], ["Cancelled", "Cancelled"]].map(([v, l]) => (
          <button key={l} role="tab" aria-selected={current === v} className={current === v ? "btn-primary" : "btn-ghost"} onClick={() => choose(v)}>{l}</button>
        ))}
      </div>
      <ErrorBox error={error} onRetry={reload} />
      <div className="card overflow-hidden p-0">
        {loading && !data ? <Loading /> : (
          <>
            <div className="overflow-x-auto"><table className="w-full">
              <thead><tr><th className="th">Student</th><th className="th">Action</th><th className="th">Owner</th><th className="th">Follow-up</th><th className="th">Status</th></tr></thead>
              <tbody className="divide-y divide-slate-100">
                {data?.items.map((i) => (
                  <tr key={i.id} className="align-top hover:bg-slate-50">
                    <td className="td"><Link className="font-medium text-brand-700 hover:underline" to={`/students/${i.student_id}`}>{i.student_name}</Link><div className="mt-0.5"><PriorityBadge value={i.student_priority} /></div></td>
                    <td className="td"><div className="font-medium">{i.type}</div><div className="max-w-md text-xs text-slate-600">{i.action}</div></td>
                    <td className="td">{i.owner}</td>
                    <td className="td whitespace-nowrap">{fmtDate(i.followup_date)}{i.overdue && <div><Tag tone="red">Overdue</Tag></div>}</td>
                    <td className="td"><Tag tone={i.status === "Completed" ? "green" : i.status === "In progress" ? "indigo" : "slate"}>{i.status}</Tag>{i.source === "simulated" && <div className="mt-1"><Tag tone="indigo">Simulated</Tag></div>}</td>
                  </tr>
                ))}
                {data && !data.items.length && <tr><td className="td text-slate-500" colSpan={5}>Nothing here.</td></tr>}
              </tbody></table></div>
            {data && <Pager page={page} pageSize={25} total={data.total} onPage={setPage} />}
          </>
        )}
      </div>
    </div>
  );
}
