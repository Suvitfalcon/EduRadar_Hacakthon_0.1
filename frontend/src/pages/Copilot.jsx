import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api.js";

const EXAMPLES = [
  "Which students have declining attendance?",
  "Which high priority students are unreviewed?",
  "What follow-ups are due tomorrow?",
  "How should teachers support students with missed assignments?",
  "Why should we avoid reacting to one poor test?",
];

export default function Copilot() {
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState([]);
  const [busy, setBusy] = useState(false);
  async function ask(text = question) {
    const q = text.trim();
    if (!q || busy) return;
    setQuestion("");
    setMessages(prev => [...prev, { who: "you", text: q }]);
    setBusy(true);
    try {
      const answer = await api.copilotAsk(q);
      setMessages(prev => [...prev, { who: "copilot", ...answer }]);
    } catch (e) {
      setMessages(prev => [...prev, { who: "error", text: e.message }]);
    } finally { setBusy(false); }
  }
  return <div className="space-y-5">
    <div><h1>EduRadar AI Copilot</h1><p className="text-sm text-slate-500 mt-1">Grounded answers from synthetic records and demonstration guidance. Teacher review required.</p></div>
    <div className="card space-y-4">
      <div className="flex flex-wrap gap-2">{EXAMPLES.map(x => <button key={x} className="btn-ghost text-sm" disabled={busy} onClick={() => ask(x)}>{x}</button>)}</div>
      <div aria-live="polite" className="space-y-4 max-h-[55vh] overflow-auto">
        {messages.length === 0 && <p className="text-sm text-slate-500">Ask about support guidelines, synthetic student trends, or follow-up actions.</p>}
        {messages.map((m, i) => <div key={i} className={`rounded-lg p-4 ${m.who === "you" ? "bg-brand-50 ml-8" : "bg-slate-50 mr-8"}`}>
          <div className="font-medium text-sm mb-1">{m.who === "you" ? "You" : m.who === "error" ? "Error" : "Copilot"}</div>
          <p className="text-sm whitespace-pre-wrap">{m.text || m.answer}</p>
          {m.records?.length > 0 && <div className="mt-3 space-y-1">{m.records.map((r, j) => <div key={j} className="text-sm rounded border bg-white p-2"><Link className="text-brand-700 underline" to={`/students/${encodeURIComponent(r.student_id)}`}>{r.student_id} — {r.name}</Link>{r.priority && <span> · {r.priority}</span>}{r.followup_date && <span> · Follow-up {r.followup_date}</span>}{r.action && <div>{r.action}</div>}</div>)}</div>}
          {m.sources?.length > 0 && <details className="mt-2 text-xs"><summary className="cursor-pointer text-slate-600">Sources ({m.sources.length})</summary>{m.sources.map(src => <p key={src.id} className="mt-2 text-slate-600"><b>{src.id}</b>: {src.excerpt}</p>)}</details>}
        </div>)}
        {busy && <p className="text-sm text-slate-500">Searching authorized demo records...</p>}
      </div>
      <form className="flex gap-2" onSubmit={e => { e.preventDefault(); ask(); }}>
        <input className="input flex-1" value={question} onChange={e => setQuestion(e.target.value)} maxLength={500} placeholder="Ask EduRadar..." aria-label="Ask EduRadar" />
        <button className="btn-primary" disabled={busy || question.trim().length < 3}>Send</button>
      </form>
      <p className="text-xs text-amber-700">Demo guidance is illustrative, not official school policy. This copilot does not change priorities or interventions.</p>
    </div>
  </div>;
}
