// Thin fetch wrapper. Same-origin (Vite proxies /api in dev, FastAPI serves
// the built bundle from / in prod). 401 redirects to / so the login page renders.

import type {
  BatchItem,
  Health,
  InspectResult,
  Job,
  JobSummary,
  Preset,
  PrinterStatus,
  Stock,
  TraysResponse,
} from "./types";

class ApiError extends Error {
  constructor(public status: number, message: string, public body?: unknown) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    credentials: "same-origin",
    headers: { Accept: "application/json", ...(init?.headers || {}) },
    ...init,
  });
  if (res.status === 401) {
    window.location.href = "/";
    throw new ApiError(401, "not authenticated");
  }
  const text = await res.text();
  let data: unknown = undefined;
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = text;
    }
  }
  if (!res.ok) {
    const detail =
      data && typeof data === "object" && "detail" in data
        ? String((data as { detail: unknown }).detail)
        : res.statusText;
    throw new ApiError(res.status, detail, data);
  }
  return data as T;
}

export const api = {
  health: () => request<Health>("/api/health"),
  me: () => request<{ user: string }>("/api/me"),
  presets: () => request<Preset[]>("/api/presets"),
  stocks: () => request<Stock[]>("/api/stocks"),
  rates: () => request<{ color: number; bw: number }>("/api/rates"),
  printer: () => request<PrinterStatus>("/api/printer"),

  trays: () => request<TraysResponse>("/api/trays"),
  setTray: (
    tray: string,
    body: { stock_code: string | null; paper_size: string | null; level: string | null }
  ) =>
    request<TraysResponse>(`/api/trays/${tray}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),

  inspect: (file: File, quantityGuess = 100) => {
    const fd = new FormData();
    fd.append("file", file);
    fd.append("quantity_guess", String(quantityGuess));
    return request<InspectResult>("/api/inspect", { method: "POST", body: fd });
  },

  submitJob: (params: {
    file: File;
    workflow: string;
    preset_key: string;
    stock_code: string;
    quantity: number;
    sides: number;
  }) => {
    const fd = new FormData();
    fd.append("file", params.file);
    fd.append("workflow", params.workflow);
    fd.append("preset_key", params.preset_key);
    fd.append("stock_code", params.stock_code);
    fd.append("quantity", String(params.quantity));
    fd.append("sides", String(params.sides));
    return request<Job>("/api/job", { method: "POST", body: fd });
  },

  submitBatch: (params: {
    files: File[];
    workflow: string;
    preset_key: string;
    stock_code: string;
    quantity: number;
    sides: number;
  }) => {
    const fd = new FormData();
    for (const f of params.files) fd.append("files", f);
    fd.append("workflow", params.workflow);
    fd.append("preset_key", params.preset_key);
    fd.append("stock_code", params.stock_code);
    fd.append("quantity", String(params.quantity));
    fd.append("sides", String(params.sides));
    return request<BatchItem[]>("/api/batch", { method: "POST", body: fd });
  },

  jobs: (limit = 50) => request<JobSummary[]>(`/api/jobs?limit=${limit}`),
  job: (id: string) => request<Job>(`/api/job/${id}`),
  reprint: (id: string) => request<Job>(`/api/job/${id}/reprint`, { method: "POST" }),

  imposedPdfUrl: (id: string) => `/api/job/${id}/imposed.pdf`,
  thumbUrl: (id: string) => `/api/job/${id}/thumb.png`,
};

export { ApiError };
