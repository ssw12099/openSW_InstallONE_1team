const API_BASE_URL = "http://127.0.0.1:8000";

async function apiRequest(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));

    throw new Error(
      typeof error.detail === "string"
        ? error.detail
        : `서버 요청 실패 (${response.status})`
    );
  }

  return response.json();
}

export const api = {
  getHealth: () => apiRequest("/api/health"),

  getConfig: () => apiRequest("/api/config"),

  getPCs: () => apiRequest("/api/pcs"),

  getProfiles: () => apiRequest("/api/profiles"),

  analyze: (request) =>
    apiRequest("/api/analyze", {
      method: "POST",
      body: JSON.stringify({ request }),
    }),

  install: (plan) =>
    apiRequest("/api/install", {
      method: "POST",
      body: JSON.stringify({
        request: plan.request,
        pc_ids: plan.pc_ids,
        profiles: plan.profiles,
        approved: true,
      }),
    }),

  getJobs: () => apiRequest("/api/jobs"),

  getJobDetail: (jobId) =>
    apiRequest(`/api/jobs/${jobId}`),
};