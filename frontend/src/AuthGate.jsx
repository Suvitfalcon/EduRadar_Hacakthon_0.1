import { useEffect, useState } from "react";
import { api } from "./api.js";
import LogoMark from "./Logo.jsx";
import ThemeToggle from "./ThemeToggle.jsx";
import BackgroundAnimation from "./BackgroundAnimation.jsx";
import { TeacherContext } from "./session.js";

export default function AuthGate({ children }) {
  const [teacher, setTeacher] = useState(null);
  const [loading, setLoading] = useState(true);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => { api.me().then(setTeacher).catch(() => {}).finally(() => setLoading(false)); }, []);

  async function submit(e) {
    e.preventDefault(); setError(""); setBusy(true);
    try { const result = await api.login(username, password); setTeacher(result); setPassword(""); }
    catch (err) { setError(err.message || "Could not log in"); }
    finally { setBusy(false); }
  }

  async function signOut() {
    try { await api.logout(); } catch { /* Clear local session state even if connection fails */ }
    setTeacher(null);
    window.location.href = "/";
  }

  if (loading) return <div className="auth-loading" role="status"><div className="auth-spinner"/><span>Preparing your workspace…</span></div>;
  if (!teacher) return <main className="auth-page">
    <BackgroundAnimation /><ThemeToggle floating />
    <div className="auth-orb auth-orb-one"/><div className="auth-orb auth-orb-two"/>
    <div className="auth-layout">
      <section className="auth-story">
        <div className="auth-brand"><span className="auth-logo"><LogoMark /></span><span>EduRadar<span className="brand-dot">.</span></span></div>
        <div className="auth-story-content">
          <div className="auth-visual" aria-hidden="true">
            <div className="auth-visual-header"><span>Learning indicators</span><span>↗ Weekly outlook</span></div>
            <svg viewBox="0 0 500 145" preserveAspectRatio="none" role="img" aria-label="Decorative upward trend chart"><defs><linearGradient id="lineFill" x1="0" x2="0" y1="0" y2="1"><stop stopColor="#92a4ff" stopOpacity=".34"/><stop offset="1" stopColor="#92a4ff" stopOpacity="0"/></linearGradient></defs><path d="M0 122 C55 115 70 101 115 106 S185 88 220 91 S290 55 326 65 S405 40 500 10 L500 145 L0 145Z" fill="url(#lineFill)"/><path className="auth-chart-line" d="M0 122 C55 115 70 101 115 106 S185 88 220 91 S290 55 326 65 S405 40 500 10" fill="none" stroke="#b5c3ff" strokeWidth="3.5" strokeLinecap="round"/></svg>
          </div>
        </div>
      </section>
      <section className="auth-form-side">
        <div className="auth-form-wrapper">
          <div className="auth-mobile-brand"><span className="auth-logo"><LogoMark /></span> EduRadar</div>
          <div className="auth-welcome-icon">✧</div>
          <span className="auth-form-kicker">TEACHER PORTAL</span>
          <h2>Welcome back<span className="brand-dot">.</span></h2>
          <p className="auth-form-description">Sign in to view student insights and manage support plans.</p>
          <form className="auth-form" onSubmit={submit}>
            <label htmlFor="teacher-user">Username</label>
            <input id="teacher-user" autoComplete="username" required value={username} onChange={e=>setUsername(e.target.value)} placeholder="Enter your username" />
            <label htmlFor="teacher-password">Password</label>
            <div className="auth-password-wrap"><input id="teacher-password" type={showPassword?"text":"password"} autoComplete="current-password" required value={password} onChange={e=>setPassword(e.target.value)} placeholder="Enter your password" /><button type="button" aria-label={showPassword?"Hide password":"Show password"} onClick={()=>setShowPassword(!showPassword)}>{showPassword?"Hide":"Show"}</button></div>
            {error && <p className="auth-error" role="alert">{error}</p>}
            <button className="auth-submit" disabled={busy} type="submit">{busy ? "Signing in…" : "Access dashboard"}<span aria-hidden="true">→</span></button>
          </form>
          <div className="auth-security"><span>♢</span> Restricted to authorized teachers · Secure session</div>
        </div>
      </section>
    </div>
  </main>;

  return <TeacherContext.Provider value={teacher}>
    <div className="session-widget"><div className="session-icon">✓</div><span className="session-name">{teacher.display_name}</span><button type="button" onClick={signOut}>Log out ↗</button></div>
    {children}
  </TeacherContext.Provider>;
}
