const KEY = "eduradar-theme";

export function getInitialTheme() {
  try {
    const saved = localStorage.getItem(KEY);
    if (saved === "dark" || saved === "light") return saved;
  } catch { /* storage unavailable */ }
  return "light";
}

export function applyTheme(theme) {
  document.documentElement.setAttribute("data-theme", theme);
}

export function saveTheme(theme) {
  try { localStorage.setItem(KEY, theme); } catch { /* storage unavailable */ }
}
