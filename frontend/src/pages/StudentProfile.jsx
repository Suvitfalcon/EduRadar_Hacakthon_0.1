import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api.js";
import { ErrorBox, Loading, Notice, PriorityBadge, SourceTag, Tag, WeeklyChart, fmtDate, fmtPct, useAsync } from "../ui.jsx";

const TREND_TAG = {
  sustained_decline: ["red", "Sustained decline"],
  improving: ["green", "Improving"],
  isolated_dip: ["amber", "Single dip - not a trend"],
  stable: ["slate", "Stable"],
  insufficient: ["slate", "Not enough data"],
};

export default function StudentProfile({ reviewer }) {
  const { id } = useParams();
  const { data: d, error, loading, reload } = useAsync(() => api.student(id), [id]);
  if (loading && !d) return <Loading />;
  if (error) return <div className="space-y-3"><Link to="/students" className="text-sm text-brand-700 hover:underline">Back to students</Link><ErrorBox error={error} onRetry={reload} /></div>;
  const { student: st, prediction: p } = d;

  return (
    <div className="space-y-6">
      <Link to="/students" className="text-sm text-brand-700 hover:underline">← All students</Link>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1>{st.name}</h1>
          <div className="mt-1 flex flex-wrap items-center gap-2 text-sm text-slate-600">
            <span>{st.student_id}</span><span>·</span><span>{st.department}</span>
            {st.year_of_study && <><span>·</span><span>Year {st.year_of_study}</span></>}
            <SourceTag source={st.data_source} />
          </div>
        </div>
        <div className="text-right">
          <div className="text-xs text-slate-500">Current priority</div>
          <PriorityBadge value={st.priority} big />
          {st.overridden && <div className="mt-1 text-xs text-slate-500">Teacher override · model said {st.model_priority}</div>}
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-5">
        <div className="space-y-6 lg:col-span-3"><RiskCard d={d} /><Indicators d={d} /></div>
        <div className="space-y-6 lg:col-span-2"><ReviewCard d={d} reviewer={reviewer} reload={reload} /><AttendanceCard d={d} /><QualityCard d={d} /></div>
      </div>
      <SupportCard d={d} reviewer={reviewer} reload={reload} />
      <History d={d} />
    </div>
  );
}

/* ------------------------------------------------------------------ risk + explanation */
function RiskCard({ d }) {
  const p = d.prediction;
  if (!p) return <Notice>No model result yet.</Notice>;
  return (
    <section className="card">
      <h2>Why this priority? <span className="font-normal text-slate-500">· original model result</span></h2>
      {p.insufficient_data ? (
        <div className="mt-3"><Notice tone="amber" title="Insufficient data - no result shown">
          There is not enough recorded evidence to support a risk result for this student. Complete the missing weekly records (see Data checks) or use your own judgement and record it as an override.
        </Notice></div>
      ) : (
        <>
          <p className="mt-2 text-sm text-slate-700">
            Past students with a similar pattern withdrew by week 16 about <b>{fmtPct(p.score * 100)}</b> of the time
            (average across all students: {fmtPct(p.base_rate * 100)}). This is a pattern from simulated data, not a prediction about this student as a person.
          </p>
          <ul className="mt-4 space-y-3">
            {p.factors.map((f) => {
              const up = f.contribution > 0;
              const w = Math.min(100, Math.abs(f.contribution) * 400);
              return (
                <li key={f.feature} className="grid grid-cols-[1fr_auto] gap-x-4 gap-y-1">
                  <div>
                    <div className="text-sm font-medium text-slate-900">{f.label}</div>
                    <div className="text-xs text-slate-500">
                      {f.imputed ? "Value missing - typical value assumed" : `This student: ${f.value}${f.unit.trim() === "%" ? "%" : f.unit}`} · model rule: {f.rule}
                    </div>
                  </div>
                  <div className="text-right"><Tag tone={up ? "red" : "green"}>{up ? "Raises" : "Lowers"} risk {up ? "+" : "−"}{Math.abs(f.contribution * 100).toFixed(1)} pts</Tag></div>
                  <div className="col-span-2 h-1.5 rounded-full bg-slate-100" aria-hidden="true"><div className={`h-1.5 rounded-full ${up ? "bg-red-400" : "bg-emerald-400"}`} style={{ width: `${w}%` }} /></div>
                </li>
              );
            })}
          </ul>
          <p className="mt-4 text-xs text-slate-500">Factors come from the decision-tree path this student followed. Model {p.model_version} · scored {fmtDate(p.created_at)}.</p>
        </>
      )}
    </section>
  );
}

function Indicators({ d }) {
  const w = d.weeks;
  const series = (k) => w.map((x) => x[k]);
  const T = d.trends?.indicators || {};
  const items = [
    ["attendance", "Attendance", series("attendance_pct"), "#4338ca", "%"],
    ["assessment", "Assessment score", series("assessment_score"), "#0f766e", ""],
    ["assignment", "Assignment completion", series("assignment_completion_pct"), "#b45309", "%"],
    ["engagement", "Engagement", series("engagement_score"), "#7c3aed", ""],
  ];
  return (
    <section className="card">
      <h2>Weekly indicators and trends</h2>
      <p className="mt-1 text-sm text-slate-600">A trend needs three consecutive weeks. One poor result is shown as a single dip, not as the student's trend.</p>
      <div className="mt-4 grid gap-5 sm:grid-cols-2">
        {items.map(([key, title, vals, color, unit]) => {
          const t = T[key] || { status: "insufficient", message: "" };
          const [tone, label] = TREND_TAG[t.status];
          const na = key === "assignment" && w.every((x) => x.assignment_not_applicable);
          return (
            <div key={key} className="rounded-lg border border-slate-200 p-3">
              <div className="flex items-center justify-between gap-2"><div className="text-sm font-medium">{title}</div><Tag tone={tone}>{label}</Tag></div>
              {na ? <div className="py-8 text-center text-sm text-slate-500">No assignments were due - not applicable (not counted as 0%).</div>
                : <WeeklyChart values={vals} color={color} label={title} unit={unit} />}
              <div className="text-xs text-slate-600">{t.message}</div>
            </div>
          );
        })}
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------ attendance (rule-based) */
function AttendanceCard({ d }) {
  const a = d.attendance;
  const tone = a.alert === "No alert" ? "green" : a.alert === "Attendance data missing" ? "slate" : "amber";
  return (
    <section className="card">
      <div className="flex items-center justify-between"><h2>Attendance alert</h2><Tag tone={tone}>{a.alert}</Tag></div>
      <p className="mt-1 text-xs text-slate-500">Rule-based, separate from the model. {a.rule}</p>
      <div className="mt-3 text-sm">Overall: <b>{a.weighted_pct == null ? "-" : fmtPct(a.weighted_pct, 1)}</b>{a.slope != null && <> · change {a.slope > 0 ? "+" : ""}{a.slope.toFixed(1)} pts / week</>}</div>
      <table className="mt-3 w-full text-sm">
        <thead><tr><th className="th px-0">Week</th><th className="th">Attended</th><th className="th">Conducted</th><th className="th">%</th></tr></thead>
        <tbody>{d.weeks.map((w) => (
          <tr key={w.week} className="border-t border-slate-100"><td className="py-1.5">W{w.week}</td><td>{w.classes_attended ?? "missing"}</td><td>{w.classes_scheduled ?? "missing"}</td><td>{w.attendance_pct == null ? "-" : fmtPct(w.attendance_pct)}</td></tr>
        ))}</tbody>
      </table>
    </section>
  );
}

function QualityCard({ d }) {
  const q = d.quality;
  if (!q) return null;
  return (
    <section className="card">
      <div className="flex items-center justify-between"><h2>Data checks</h2><Tag tone={q.incomplete ? "amber" : "green"}>{q.incomplete ? "Incomplete" : "Complete"}</Tag></div>
      <div className="mt-2 text-sm">Completeness: <b>{fmtPct(q.completeness_pct, 0)}</b></div>
      {q.missing.length > 0 && <div className="mt-2"><div className="text-xs font-medium text-slate-600">Missing ({q.missing.length})</div><ul className="mt-1 list-disc pl-5 text-xs text-slate-600">{q.missing.slice(0, 8).map((m) => <li key={m}>{m}</li>)}{q.missing.length > 8 && <li>and {q.missing.length - 8} more</li>}</ul></div>}
      {q.invalid.length > 0 && <div className="mt-2"><div className="text-xs font-medium text-red-700">Invalid values ignored ({q.invalid.length})</div><ul className="mt-1 list-disc pl-5 text-xs text-slate-600">{q.invalid.map((m) => <li key={m}>{m}</li>)}</ul></div>}
      {!q.incomplete && <p className="mt-1 text-xs text-slate-500">All weekly inputs are present and valid.</p>}
    </section>
  );
}

/* ------------------------------------------------------------------ teacher review */
function ReviewCard({ d, reviewer, reload }) {
  const p = d.prediction;
  const [mode, setMode] = useState("accept");
  const [final, setFinal] = useState("Medium");
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);
  const cur = d.current_review;
  if (!p) return null;
  const options = ["High", "Medium", "Low"].filter((x) => x !== p.priority);
  const canAccept = !p.insufficient_data;

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true); setErr(null);
    try {
      await api.review(d.student.student_id, { decision: mode, final_priority: mode === "override" ? (options.includes(final) ? final : options[0]) : null, reason, reviewer: reviewer.trim() });
      setReason(""); reload();
    } catch (x) { setErr(x); } finally { setBusy(false); }
  };

  return (
    <section className="card">
      <h2>Teacher review</h2>
      <div className="mt-2 rounded-lg bg-slate-50 p-3 text-sm">
        <div className="text-xs text-slate-500">Original model result (kept unchanged)</div>
        <div className="mt-1 flex items-center gap-2"><PriorityBadge value={p.priority} />{p.score != null && <span className="text-slate-600">score {fmtPct(p.score * 100)}</span>}</div>
      </div>
      {cur && (
        <div className="mt-3 rounded-lg border border-brand-100 bg-brand-50 p-3 text-sm">
          <div className="font-medium">{cur.decision === "accept" ? "Accepted" : "Overridden"} by {cur.reviewer} · {fmtDate(cur.created_at)}</div>
          {cur.decision === "override" && <div className="mt-1">Model: {cur.original_priority} → Final: <b>{cur.final_priority}</b></div>}
          {cur.reason && <div className="mt-1 text-slate-700">Reason: {cur.reason}</div>}
        </div>
      )}
      <form onSubmit={submit} className="mt-4 space-y-3">
        <fieldset>
          <legend className="label">{cur ? "Change your decision" : "Your decision"}</legend>
          <div className="flex gap-2">
            <label className={`btn-ghost flex-1 cursor-pointer ${mode === "accept" ? "!border-brand-500 !bg-brand-50" : ""} ${canAccept ? "" : "opacity-50"}`}>
              <input type="radio" className="sr-only" name="mode" checked={mode === "accept"} disabled={!canAccept} onChange={() => setMode("accept")} />Accept
            </label>
            <label className={`btn-ghost flex-1 cursor-pointer ${mode === "override" || !canAccept ? "!border-brand-500 !bg-brand-50" : ""}`}>
              <input type="radio" className="sr-only" name="mode" checked={mode === "override" || !canAccept} onChange={() => setMode("override")} />Override
            </label>
          </div>
        </fieldset>
        {(mode === "override" || !canAccept) && (
          <>
            <div>
              <label className="label" htmlFor="final">Priority you set</label>
              <select id="final" className="input" value={options.includes(final) ? final : options[0]} onChange={(e) => setFinal(e.target.value)}>
                {options.map((o) => <option key={o}>{o}</option>)}
              </select>
            </div>
            <div>
              <label className="label" htmlFor="reason">Reason (required)</label>
              <textarea id="reason" className="input" rows={3} value={reason} onChange={(e) => setReason(e.target.value)} placeholder="What do you know that the data does not show?" />
            </div>
          </>
        )}
        {!reviewer.trim() && <Notice tone="amber">Enter your name in the sidebar first.</Notice>}
        <ErrorBox error={err} />
        <button className="btn-primary w-full" disabled={busy || !reviewer.trim() || ((mode === "override" || !canAccept) && reason.trim().length < 5)}>
          {busy ? "Saving..." : mode === "accept" && canAccept ? "Accept model priority" : "Save override"}
        </button>
      </form>
      {d.reviews.length > 1 && (
        <details className="mt-3 text-sm"><summary className="cursor-pointer text-slate-600">Review history ({d.reviews.length})</summary>
          <ul className="mt-2 space-y-2">{d.reviews.map((r) => <li key={r.id} className="text-xs text-slate-600">{fmtDate(r.created_at)} · {r.reviewer} · {r.decision} · {r.original_priority} → {r.final_priority}{r.reason ? ` · "${r.reason}"` : ""}</li>)}</ul>
        </details>
      )}
    </section>
  );
}

/* ------------------------------------------------------------------ support tracking */
const IND = [["attendance_pct", "Attendance %"], ["assignment_completion_pct", "Assignment completion %"], ["engagement_score", "Engagement score"]];

function SupportCard({ d, reviewer, reload }) {
  const [adding, setAdding] = useState(false);
  return (
    <section className="card">
      <div className="flex items-center justify-between">
        <div><h2>Support tracking</h2><p className="text-sm text-slate-500">Record the action, who owns it and when to check back. Compare indicators at follow-up.</p></div>
        {!adding && <button className="btn-primary" onClick={() => setAdding(true)}>Add support plan</button>}
      </div>
      {adding && <AddPlan id={d.student.student_id} reviewer={reviewer} done={() => { setAdding(false); reload(); }} cancel={() => setAdding(false)} />}
      <div className="mt-4 space-y-4">
        {d.interventions.map((iv) => <Plan key={iv.id} iv={iv} reload={reload} />)}
        {!d.interventions.length && !adding && <p className="text-sm text-slate-500">No support plans recorded yet.</p>}
      </div>
    </section>
  );
}

function AddPlan({ id, reviewer, done, cancel }) {
  const today = new Date(Date.now() + 14 * 864e5).toISOString().slice(0, 10);
  const [f, setF] = useState({ type: "Mentoring", action: "", owner: reviewer || "", followup_date: today });
  const [err, setErr] = useState(null);
  const [busy, setBusy] = useState(false);
  const types = ["Academic tutoring", "Assignment support", "Attendance counselling", "Mentoring", "Other"];
  const submit = async (e) => {
    e.preventDefault(); setBusy(true); setErr(null);
    try { await api.addIntervention(id, f); done(); } catch (x) { setErr(x); } finally { setBusy(false); }
  };
  return (
    <form onSubmit={submit} className="mt-4 grid gap-3 rounded-lg border border-slate-200 bg-slate-50 p-4 sm:grid-cols-2">
      <div><label className="label" htmlFor="t">Type</label><select id="t" className="input" value={f.type} onChange={(e) => setF({ ...f, type: e.target.value })}>{types.map((t) => <option key={t}>{t}</option>)}</select></div>
      <div><label className="label" htmlFor="o">Owner</label><input id="o" className="input" value={f.owner} onChange={(e) => setF({ ...f, owner: e.target.value })} placeholder="Who is responsible?" /></div>
      <div className="sm:col-span-2"><label className="label" htmlFor="a">Action</label><textarea id="a" className="input" rows={2} value={f.action} onChange={(e) => setF({ ...f, action: e.target.value })} placeholder="e.g. Weekly 20-minute mentoring check-in" /></div>
      <div><label className="label" htmlFor="fd">Follow-up date</label><input id="fd" type="date" className="input" min={new Date().toISOString().slice(0, 10)} value={f.followup_date} onChange={(e) => setF({ ...f, followup_date: e.target.value })} /></div>
      <div className="sm:col-span-2"><ErrorBox error={err} /></div>
      <div className="flex gap-2 sm:col-span-2"><button className="btn-primary" disabled={busy || f.action.trim().length < 3 || !f.owner.trim()}>{busy ? "Saving..." : "Save plan"}</button><button type="button" className="btn-ghost" onClick={cancel}>Cancel</button></div>
    </form>
  );
}

function Plan({ iv, reload }) {
  const [open, setOpen] = useState(false);
  const [notes, setNotes] = useState("");
  const [fu, setFu] = useState({});
  const [err, setErr] = useState(null);
  const [busy, setBusy] = useState(false);
  const closed = iv.status === "Completed" || iv.status === "Cancelled";
  const tone = { Planned: "slate", "In progress": "indigo", Completed: "green", Cancelled: "slate" }[iv.status];

  const patch = async (body) => {
    setBusy(true); setErr(null);
    try { await api.updateIntervention(iv.id, body); setOpen(false); reload(); } catch (x) { setErr(x); } finally { setBusy(false); }
  };
  const complete = () => {
    const followup = Object.fromEntries(IND.map(([k]) => [k, fu[k] === "" || fu[k] == null ? null : Number(fu[k])]));
    patch({ status: "Completed", outcome_notes: notes, followup });
  };

  return (
    <article className="rounded-lg border border-slate-200 p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-2"><span className="font-medium">{iv.type}</span><Tag tone={tone}>{iv.status}</Tag>{iv.overdue && <Tag tone="red">Overdue</Tag>}{iv.source === "simulated" && <Tag tone="indigo">Simulated</Tag>}</div>
        <div className="text-xs text-slate-500">Owner: {iv.owner} · follow-up {fmtDate(iv.followup_date)}</div>
      </div>
      <p className="mt-1 text-sm text-slate-700">{iv.action}</p>
      {iv.baseline && (
        <div className="overflow-x-auto"><table className="mt-3 w-full text-sm">
          <thead><tr><th className="th px-0">Indicator</th><th className="th">At plan</th><th className="th">Follow-up</th><th className="th">Change</th></tr></thead>
          <tbody>{IND.map(([k, label]) => {
            const b = iv.baseline[k], f = iv.followup?.[k], dl = iv.deltas?.[k];
            return <tr key={k} className="border-t border-slate-100"><td className="py-1.5">{label}</td><td>{b ?? "-"}</td><td>{f ?? "-"}</td>
              <td className={dl == null ? "" : dl > 0 ? "font-medium text-emerald-700" : dl < 0 ? "font-medium text-red-700" : ""}>{dl == null ? "-" : `${dl > 0 ? "▲ +" : dl < 0 ? "▼ " : ""}${dl}`}</td></tr>;
          })}</tbody>
        </table></div>
      )}
      {iv.outcome_notes && <p className="mt-2 rounded bg-slate-50 p-2 text-sm"><span className="font-medium">Outcome:</span> {iv.outcome_notes}</p>}
      {!closed && !open && (
        <div className="mt-3 flex flex-wrap gap-2">
          {iv.status === "Planned" && <button className="btn-ghost" disabled={busy} onClick={() => patch({ status: "In progress" })}>Mark in progress</button>}
          <button className="btn-primary" onClick={() => setOpen(true)}>Record follow-up and complete</button>
          <button className="btn-danger" disabled={busy} onClick={() => patch({ status: "Cancelled" })}>Cancel plan</button>
        </div>
      )}
      {open && (
        <div className="mt-3 space-y-3 rounded-lg bg-slate-50 p-3">
          <div className="grid gap-3 sm:grid-cols-3">{IND.map(([k, label]) => (
            <div key={k}><label className="label" htmlFor={`${iv.id}-${k}`}>{label} now</label><input id={`${iv.id}-${k}`} type="number" min="0" max="100" className="input" value={fu[k] ?? ""} onChange={(e) => setFu({ ...fu, [k]: e.target.value })} /></div>
          ))}</div>
          <div><label className="label" htmlFor={`n${iv.id}`}>Outcome notes (required)</label><textarea id={`n${iv.id}`} rows={2} className="input" value={notes} onChange={(e) => setNotes(e.target.value)} /></div>
          <ErrorBox error={err} />
          <div className="flex gap-2"><button className="btn-primary" disabled={busy || notes.trim().length < 3} onClick={complete}>{busy ? "Saving..." : "Complete follow-up"}</button><button className="btn-ghost" onClick={() => setOpen(false)}>Close</button></div>
        </div>
      )}
      {!open && <ErrorBox error={err} />}
    </article>
  );
}

function History({ d }) {
  if (d.history.length < 2) return null;
  return (
    <section className="card">
      <h2>Model result history</h2>
      <p className="text-sm text-slate-500">Every score is kept. A new one is added whenever the student's data is re-uploaded.</p>
      <ul className="mt-3 divide-y divide-slate-100 text-sm">
        {d.history.map((h) => <li key={h.id} className="flex items-center justify-between py-2"><span>{fmtDate(h.created_at)} · {h.source}</span><span className="flex items-center gap-3">{h.score != null && <span className="tabular-nums text-slate-500">{fmtPct(h.score * 100)}</span>}<PriorityBadge value={h.priority} /></span></li>)}
      </ul>
    </section>
  );
}
