import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api.js";
import { ErrorBox, Notice, PriorityBadge } from "../ui.jsx";

function Uploader({ kind, title, help, columns }) {
  const [file, setFile] = useState(null);
  const [busy, setBusy] = useState(false);
  const [res, setRes] = useState(null);
  const [err, setErr] = useState(null);
  const send = async (e) => {
    e.preventDefault(); setBusy(true); setErr(null); setRes(null);
    try { setRes(await api.upload(kind, file)); } catch (x) { setErr(x); } finally { setBusy(false); }
  };
  return (
    <section className="card space-y-4">
      <div><h2>{title}</h2><p className="mt-1 text-sm text-slate-600">{help}</p></div>
      <div className="rounded-lg bg-slate-50 p-3 text-xs text-slate-600"><span className="font-medium">Columns:</span> {columns}</div>
      <a className="text-sm text-brand-700 hover:underline" href={`/api/templates/${kind}`}>Download CSV template</a>
      <form onSubmit={send} className="space-y-3">
        <div>
          <label className="label" htmlFor={`f-${kind}`}>CSV file (max 15 MB)</label>
          <input id={`f-${kind}`} type="file" accept=".csv,text/csv" className="input" onChange={(e) => { setFile(e.target.files?.[0] || null); setRes(null); setErr(null); }} />
        </div>
        <button className="btn-primary" disabled={!file || busy}>{busy ? "Checking and scoring..." : "Upload and score"}</button>
      </form>
      <ErrorBox error={err} />
      {res && <Result res={res} kind={kind} />}
    </section>
  );
}

function Result({ res, kind }) {
  const pc = res.priority_counts || {};
  return (
    <div className="space-y-3" role="status">
      <Notice tone="green" title={kind === "students" ? `${res.students} students processed (${res.created} new, ${res.updated} updated)` : `${res.rows_applied} attendance rows applied; ${res.students} students re-scored`}>
        {res.rows_rejected > 0 && `${res.rows_rejected} row(s) were rejected. `}Previous model results are kept in each student's history.
      </Notice>
      <div className="flex flex-wrap gap-2">{["High", "Medium", "Low", "Insufficient Data"].map((p) => <span key={p} className="flex items-center gap-1 text-sm"><PriorityBadge value={p} /> {pc[p] || 0}</span>)}</div>
      <ul className="list-disc space-y-1 pl-5 text-sm text-slate-700">
        <li>{res.incomplete_records} record(s) with missing or invalid values - <Link className="text-brand-700 underline" to="/data-quality">see Data checks</Link></li>
        <li>{res.insufficient_data} with insufficient data (no result shown)</li>
        <li>{res.attendance_alerts} attendance alert(s), {res.trend_warnings} sustained-decline warning(s)</li>
        {res.weekly_columns_found != null && <li>{res.weekly_columns_found} of {res.weekly_columns_expected} weekly columns found; absent ones are treated as missing</li>}
      </ul>
      {res.warnings?.map((w) => <Notice key={w} tone="amber">{w}</Notice>)}
      {res.note && <Notice tone="indigo">{res.note} Ignored: {res.ignored_columns.join(", ")}.</Notice>}
      {res.errors?.length > 0 && (
        <details open className="text-sm"><summary className="cursor-pointer font-medium text-red-800">Rejected rows ({res.rows_rejected})</summary>
          <ul className="mt-1 list-disc pl-5 text-xs text-slate-700">{res.errors.map((e) => <li key={e}>{e}</li>)}</ul></details>
      )}
    </div>
  );
}

export default function Upload() {
  return (
    <div className="space-y-6">
      <div><h1>Upload CSV</h1><p className="mt-1 text-sm text-slate-600">Files are checked first: impossible values and missing data are flagged, never silently counted as zero.</p></div>
      <div className="grid gap-6 lg:grid-cols-2">
        <Uploader kind="attendance" title="Attendance - classes attended and conducted"
          help="One row per student per week (1-4). Updates attendance and re-scores only the students in the file."
          columns="student_id, week, classes_attended, classes_conducted" />
        <Uploader kind="students" title="Full student records (batch)"
          help="Weekly attendance, assessment, assignment and engagement data for many students across classes. New students are added; existing ones are updated."
          columns="student_id (required); optional student_name, department, year_of_study; weekly columns such as classes_attended_week1, classes_scheduled_week1, assessment_score_week1, assignments_due_week1, assignments_submitted_week1, engagement_score_week1, active_learning_days_week1 ... week4" />
      </div>
    </div>
  );
}
