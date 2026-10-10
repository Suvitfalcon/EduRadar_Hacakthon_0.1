function message(detail, status) {
  if (!detail) return `Request failed (${status})`;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return detail.map((d) => `${(d.loc || []).slice(1).join(".")}: ${d.msg}`).join("; ");
  if (detail.message) return [detail.message, ...(detail.errors || []).slice(0, 5)].join(" - ");
  return JSON.stringify(detail);
}

function getCsrf() {
  return document.cookie.split("; ").find(v => v.startsWith("eduradar_csrf="))?.split("=").slice(1).join("=") || "";
}

async function request(path, opts = {}) {
  const method = (opts.method || "GET").toUpperCase();
  if (!["GET", "HEAD", "OPTIONS"].includes(method)) {
    opts = { ...opts, headers: { ...opts.headers, "X-EduRadar-CSRF": getCsrf() } };
  }

  let res;
  try {
    res = await fetch(`/api${path}`, opts);
  } catch {
    throw new Error("Cannot reach the EduRadar server. Is the backend running on port 8000?");
  }
  const body = res.headers.get("content-type")?.includes("json") ? await res.json() : null;
  if (!res.ok) throw new Error(message(body?.detail, res.status));
  return body;
}

const json = (method, data) => ({ method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(data) });
export const qs = (o) => {
  const p = new URLSearchParams();
  Object.entries(o).forEach(([k, v]) => v !== "" && v != null && p.set(k, v));
  return p.toString();
};

export const api = {
  login: (username, password) => request("/auth/login", json("POST", { username, password })),
  me: () => request("/auth/me"),
  logout: () => request("/auth/logout", json("POST", {})),
  config: () => request("/config"),
  copilotAsk: (question) => request("/copilot/ask", json("POST", { question })),
  summary: () => request("/summary"),
  departments: () => request("/departments"),
  students: (params) => request(`/students?${qs(params)}`),
  student: (id) => request(`/students/${encodeURIComponent(id)}`),
  review: (id, data) => request(`/students/${encodeURIComponent(id)}/review`, json("POST", data)),
  addIntervention: (id, data) => request(`/students/${encodeURIComponent(id)}/interventions`, json("POST", data)),
  updateIntervention: (id, data) => request(`/interventions/${id}`, json("PATCH", data)),
  interventions: (params) => request(`/interventions?${qs(params)}`),
  dataQuality: (params) => request(`/data-quality?${qs(params)}`),
  metrics: () => request("/metrics"),
  upload: (kind, file) => {
    const fd = new FormData();
    fd.append("file", file);
    return request(`/upload/${kind}`, { method: "POST", body: fd });
  },
};
