import { api } from "../api.js";
import { ErrorBox, Loading, Notice, PriorityBadge, Stat, fmtPct, useAsync } from "../ui.jsx";

export default function Evaluation() {
  const { data: m, error, loading, reload } = useAsync(() => api.metrics(), []);
  if (loading) return <Loading />;
  if (error) return <ErrorBox error={error} onRetry={reload} />;
  const h = m.high_priority, mh = m.medium_or_high, f = m.completed_followups;
  const pct = (v) => (v == null ? "-" : fmtPct(v * 100, 1));
  const tree = m.model.training.decision_tree, base = m.model.training.logistic_baseline;
  return (
    <div className="space-y-6">
      <div><h1>Evaluation</h1><p className="mt-1 text-sm text-slate-600">What we measure: alert precision, withdrawal recall and completed follow-ups.</p></div>
      <Notice tone="amber" title="No impact claim">{m.evaluation_set.note} Measured on {m.evaluation_set.students.toLocaleString()} test students ({m.evaluation_set.withdrawals} withdrew by week 16).</Notice>

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Stat label="Alert precision (High)" value={pct(h.alert_precision)} hint={`${h.true_withdrawals_flagged} of ${h.flagged} High alerts withdrew`} />
        <Stat label="Withdrawal recall (High)" value={pct(h.withdrawal_recall)} hint="Share of withdrawals marked High" />
        <Stat label="Recall (High + Medium)" value={pct(mh.withdrawal_recall)} hint={`Precision ${pct(mh.alert_precision)}`} />
        <Stat label="Completed follow-ups" value={`${f.completed.toLocaleString()} / ${f.total.toLocaleString()}`} hint={`${pct(f.completion_rate)} complete · ${f.teacher_completed} of ${f.teacher_created} teacher-created`} />
      </div>

      <section className="card"><h2>Withdrawal rate by priority</h2>
        <p className="text-sm text-slate-500">If the priorities are useful, High should withdraw more often than Medium, and Medium more than Low.</p>
        <div className="mt-3 space-y-3">{["High", "Medium", "Low"].map((p) => {
          const b = m.by_priority[p];
          return <div key={p} className="grid grid-cols-[8rem_1fr_6rem] items-center gap-3 text-sm"><PriorityBadge value={p} /><div className="h-3 rounded-full bg-slate-100"><div className="h-3 rounded-full bg-brand-500" style={{ width: `${(b.withdrawal_rate || 0) * 100}%` }} /></div><span className="tabular-nums">{pct(b.withdrawal_rate)} <span className="text-slate-400">({b.students})</span></span></div>;
        })}</div>
      </section>

      <div className="grid gap-6 lg:grid-cols-2">
        <section className="card"><h2>Model</h2>
          <table className="mt-2 w-full text-sm"><thead><tr><th className="th px-0">Test set</th><th className="th">Decision tree (used)</th><th className="th">Logistic baseline</th></tr></thead>
            <tbody>{[["Precision", "precision"], ["Recall", "recall"], ["F1", "f1"], ["ROC-AUC", "roc_auc"], ["Average precision", "average_precision"]].map(([l, k]) => (
              <tr key={k} className="border-t border-slate-100"><td className="py-1.5">{l}</td><td className="tabular-nums">{tree[k].toFixed(3)}</td><td className="tabular-nums text-slate-500">{base[k].toFixed(3)}</td></tr>))}</tbody></table>
          <p className="mt-3 text-xs text-slate-500">Decision tree (depth {m.model.training.tree_params.max_depth}) chosen for explainability. Medium from {m.model.thresholds.low_below.toFixed(2)}, High from {m.model.thresholds.high_from.toFixed(2)} (chosen on validation data only).</p>
        </section>
        <section className="card"><h2>Teacher review and support</h2>
          <ul className="mt-2 space-y-1 text-sm"><li>Accepted: <b>{m.teacher_review.accepted}</b> · Overridden: <b>{m.teacher_review.overridden}</b></li>
            {Object.entries(f.by_status).map(([k, v]) => <li key={k}>{k}: <b>{v.toLocaleString()}</b></li>)}</ul>
        </section>
      </div>

      <section className="card"><h2>Risks and how they are handled</h2><ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-slate-700">{m.risks.map((r) => <li key={r}>{r}</li>)}</ul></section>
    </div>
  );
}
