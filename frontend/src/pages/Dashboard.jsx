import { Link } from "react-router-dom";
import { api } from "../api.js";
import LogoMark from "../Logo.jsx";
import { ErrorBox, Loading, Notice, PriorityBadge, SourceTag, Stat, StackedBar, Tag, useAsync } from "../ui.jsx";

const ORDER = ["High", "Medium", "Low", "Insufficient Data"];

export default function Dashboard() {
  const { data: s, error, loading, reload } = useAsync(() => api.summary(), []);
  if (loading) return <Loading />;
  if (error) return <ErrorBox error={error} onRetry={reload} />;
  const q = (p) => `/students?${new URLSearchParams(p)}`;

  return (
    <div className="space-y-6">
      <section className="dashboard-hero">
        <div className="dashboard-hero-content">
          <div className="hero-actions"><Link className="hero-primary-link" to="/students">Explore students <span>↗</span></Link><Link className="hero-secondary-link" to="/copilot">✦ Ask AI Copilot</Link></div>
        </div>
        <div className="hero-art" aria-hidden="true"><div className="hero-art-ring ring-one"/><div className="hero-art-ring ring-two"/><div className="hero-art-center"><LogoMark /></div><div className="hero-art-chip chip-one">↗ Insights</div><div className="hero-art-chip chip-two">✓ Support</div></div>
      </section>
      <div>
        <h1>Dashboard</h1>
        <p className="mt-1 text-sm text-slate-600">Who may need support first, and why. Priorities guide teacher review - they do not decide anything.</p>
      </div>

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Link to={q({ priority: "High" })}><Stat label="High priority" value={s.by_priority.High.toLocaleString()} tone="red" hint="View list" /></Link>
        <Link to={q({ priority: "Medium" })}><Stat label="Medium priority" value={s.by_priority.Medium.toLocaleString()} tone="amber" hint="View list" /></Link>
        <Link to={q({ needs_action: "true" })}><Stat label="Need a support plan" value={s.needs_support_plan.toLocaleString()} hint="High / Medium with no open follow-up" /></Link>
        <Link to="/follow-ups?overdue=true"><Stat label="Overdue follow-ups" value={s.overdue_followups} tone={s.overdue_followups ? "red" : undefined} hint="Past their follow-up date" /></Link>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <section className="card lg:col-span-2">
          <h2>Priority by department</h2>
          <div className="mt-4 space-y-4">
            {Object.entries(s.by_department).sort().map(([dept, c]) => (
              <div key={dept}>
                <div className="mb-1 flex justify-between text-sm">
                  <Link className="font-medium text-slate-800 hover:underline" to={q({ department: dept })}>{dept}</Link>
                  <span className="text-slate-500 tabular-nums">{ORDER.map((p) => `${c[p] || 0}`).join(" / ")}</span>
                </div>
                <StackedBar parts={ORDER.map((p) => ({ label: p, value: c[p] || 0 }))} />
              </div>
            ))}
          </div>
          <div className="mt-4 flex flex-wrap gap-4 text-xs text-slate-600">
            {ORDER.map((p) => <span key={p}><PriorityBadge value={p} /></span>)}
            <span className="self-center">numbers: High / Medium / Low / Insufficient</span>
          </div>
        </section>

        <section className="card space-y-3">
          <h2>Signals to check</h2>
          {[
            ["Attendance alerts (rule-based)", s.attendance_alerts, q({ alert: "any" })],
            ["Sustained decline in an indicator", s.trend_warnings, q({ trend: "true" })],
            ["Awaiting teacher review", s.awaiting_review, q({ reviewed: "false", priority: "High,Medium" })],
            ["Teacher overrides", s.overridden, q({ reviewed: "true" })],
            ["Incomplete records", s.incomplete_records, "/data-quality"],
            ["Insufficient data - no result", s.insufficient_data, q({ priority: "Insufficient Data" })],
          ].map(([label, n, to]) => (
            <Link key={label} to={to} className="flex items-center justify-between rounded-lg px-2 py-1.5 text-sm hover:bg-slate-50">
              <span>{label}</span><span className="font-semibold tabular-nums">{n.toLocaleString()}</span>
            </Link>
          ))}
        </section>
      </div>

      <section className="card p-0">
        <div className="flex items-center justify-between p-5 pb-3">
          <div>
            <h2>Highest priority with no support plan yet</h2>
            <p className="text-sm text-slate-500">Sorted by model score. Open a student to see the reasons and record a plan.</p>
          </div>
          <Link className="btn-ghost" to={q({ priority: "High", needs_action: "true" })}>See all</Link>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead><tr><th className="th">Student</th><th className="th">Department</th><th className="th">Priority</th><th className="th">Signals</th></tr></thead>
            <tbody className="divide-y divide-slate-100">
              {s.top_needs_action.map((r) => (
                <tr key={r.student_id} className="hover:bg-slate-50">
                  <td className="td"><Link className="font-medium text-brand-700 hover:underline" to={`/students/${r.student_id}`}>{r.name}</Link><div className="text-xs text-slate-500">{r.student_id}</div></td>
                  <td className="td">{r.department}</td>
                  <td className="td"><PriorityBadge value={r.priority} /></td>
                  <td className="td space-x-1">
                    {r.attendance_alert !== "No alert" && <Tag tone="amber">{r.attendance_alert}</Tag>}
                    {r.trend_warning && <Tag tone="red">Sustained decline</Tag>}
                    {r.incomplete && <Tag>Incomplete data</Tag>}
                    <SourceTag source={r.data_source} />
                  </td>
                </tr>
              ))}
              {!s.top_needs_action.length && <tr><td className="td text-slate-500" colSpan={4}>Everyone with High priority has a support plan.</td></tr>}
            </tbody>
          </table>
        </div>
      </section>

      <Notice tone="indigo" title="Read this first">{s.disclaimer}</Notice>
    </div>
  );
}
