import { useEffect, useState } from "react";
import { applyTheme, getInitialTheme, saveTheme } from "./theme.js";

export default function ThemeToggle({ floating = false }) {
  const [theme, setTheme] = useState(() => document.documentElement.getAttribute("data-theme") || getInitialTheme());
  useEffect(() => { applyTheme(theme); }, [theme]);
  const dark = theme === "dark";
  const toggle = () => {
    const next = dark ? "light" : "dark";
    setTheme(next);
    saveTheme(next);
  };
  const label = dark ? "Switch to light theme" : "Switch to dark theme";
  return (
    <button type="button" className={`theme-toggle ${floating ? "theme-toggle-floating" : ""}`} onClick={toggle} aria-label={label} title={label} aria-pressed={dark}>
      {dark ? (
        <svg key="sun" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <circle cx="12" cy="12" r="4" />
          <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41" />
        </svg>
      ) : (
        <svg key="moon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z" />
        </svg>
      )}
    </button>
  );
}
