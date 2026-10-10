import { useContext, useEffect, useState } from "react";
import { NavLink, Route, Routes, useLocation } from "react-router-dom";
import Dashboard from "./pages/Dashboard.jsx";
import Students from "./pages/Students.jsx";
import StudentProfile from "./pages/StudentProfile.jsx";
import Upload from "./pages/Upload.jsx";
import DataQuality from "./pages/DataQuality.jsx";
import FollowUps from "./pages/FollowUps.jsx";
import Evaluation from "./pages/Evaluation.jsx";
import Copilot from "./pages/Copilot.jsx";
import LogoMark from "./Logo.jsx";
import ThemeToggle from "./ThemeToggle.jsx";
import BackgroundAnimation from "./BackgroundAnimation.jsx";
import { TeacherContext } from "./session.js";

const NAV = [
  ["/", "Dashboard", "▦"],
  ["/students", "Students", "♧"],
  ["/follow-ups", "Support tracking", "◷"],
  ["/upload", "Upload CSV", "⇧"],
  ["/data-quality", "Data checks", "◈"],
  ["/evaluation", "Evaluation", "◫"],
  ["/copilot", "AI Copilot", "✦"],
];
const TITLES = {"/":"Overview", "/students":"Student directory", "/follow-ups":"Support tracking", "/upload":"Data import", "/data-quality":"Data quality", "/evaluation":"Model evaluation", "/copilot":"AI Copilot"};

const initialsOf = (name) => {
  const parts = (name || "").trim().split(/\s+/).filter(Boolean);
  if (!parts.length) return "ER";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
};

export default function App() {
  const teacher = useContext(TeacherContext);
  const fullName = teacher?.display_name || "";
  const [reviewer, setReviewer] = useState(() => {
    try { return localStorage.getItem("reviewer") || ""; } catch { return ""; }
  });
  const [menuOpen, setMenuOpen] = useState(false);
  const location = useLocation();
  useEffect(() => { setMenuOpen(false); }, [location.pathname]);
  useEffect(() => {
    try { localStorage.setItem("reviewer", reviewer); } catch { /* storage unavailable */ }
  }, [reviewer]);

  return (
    <div className="app-shell">
      <BackgroundAnimation />
      {menuOpen && <button className="sidebar-scrim" aria-label="Close navigation" onClick={() => setMenuOpen(false)} />}
      <aside className={`app-sidebar ${menuOpen ? "sidebar-open" : ""}`} aria-label="Main navigation">
        <div className="sidebar-brand">
          <div className="brand-symbol" aria-hidden="true"><LogoMark /></div>
          <div><div className="brand-title">EduRadar<span className="brand-dot">.</span></div></div>
          <button className="sidebar-close" aria-label="Close menu" onClick={() => setMenuOpen(false)}>×</button>
        </div>
        <div className="sidebar-section-label">WORKSPACE</div>
        <nav className="sidebar-nav" aria-label="Main">
          {NAV.map(([to, label, symbol]) => (
            <NavLink key={to} to={to} end={to === "/"}
              className={({isActive})=>`sidebar-link ${isActive?"sidebar-link-active":""}`}>
              <span className="sidebar-link-icon" aria-hidden="true">{symbol}</span><span>{label}</span>
              {to === "/copilot" && <span className="sidebar-new">AI</span>}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <label className="label" htmlFor="reviewer">Reviewer display name</label>
          <input id="reviewer" className="input reviewer-input" value={reviewer} onChange={e=>setReviewer(e.target.value)} placeholder="e.g. Dr. Rao" />
        </div>
      </aside>
      <div className="app-workspace">
        <header className="app-topbar">
          <div className="topbar-left">
            <button className="mobile-menu-button" onClick={()=>setMenuOpen(true)} aria-label="Open navigation"><span>☰</span></button>
            <div><div className="topbar-eyebrow">EDURADAR / WORKSPACE</div><div className="topbar-title">{TITLES[location.pathname] || (location.pathname.startsWith('/students/') ? 'Student profile' : 'Student success')}</div></div>
          </div>
          <div className="topbar-right"><span className="live-indicator"><span className="live-dot"/> Live insights</span><span className="topbar-avatar" tabIndex={0} role="img" aria-label={fullName || "Account"} data-fullname={fullName}>{initialsOf(fullName)}</span><ThemeToggle /></div>
        </header>
        <main className="app-main" id="main-content">
          <div className="page-container page-enter">
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/students" element={<Students />} />
              <Route path="/students/:id" element={<StudentProfile reviewer={reviewer} />} />
              <Route path="/follow-ups" element={<FollowUps />} />
              <Route path="/upload" element={<Upload />} />
              <Route path="/data-quality" element={<DataQuality />} />
              <Route path="/evaluation" element={<Evaluation />} />
              <Route path="/copilot" element={<Copilot />} />
              <Route path="*" element={<div className="card">Page not found.</div>} />
            </Routes>
          </div>
        </main>
      </div>
    </div>
  );
}
