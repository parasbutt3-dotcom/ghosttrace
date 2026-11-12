import axios from "axios";
import type {
  Alert, ApiKeyCreated, ApiKeyRow, AuditEntry, ConnectedAccount, DetectionRule, Device,
  DeviceRegisterResponse, EventListResponse, EventsStats, Insights, Integration,
  IntegrationDetails, LoginResponse, MfaSetupResponse, OverviewData, ReportSummary,
  Session, TakeoutSummary, TokenResponse, User,
} from "./types";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export const api = axios.create({ baseURL: API });

api.interceptors.request.use((config) => {
  if (typeof window !== "undefined") {
    const t = localStorage.getItem("access_token");
    if (t) config.headers.Authorization = `Bearer ${t}`;
  }
  return config;
});

let refreshing: Promise<string | null> | null = null;
async function refreshAccessToken(): Promise<string | null> {
  const rt = typeof window !== "undefined" ? localStorage.getItem("refresh_token") : null;
  if (!rt) return null;
  try {
    const r = await axios.post<TokenResponse>(`${API}/api/v1/auth/refresh`, { refresh_token: rt });
    const newAccess = r.data?.access_token;
    const newRefresh = r.data?.refresh_token;
    if (newAccess) localStorage.setItem("access_token", newAccess);
    if (newRefresh) localStorage.setItem("refresh_token", newRefresh);
    return newAccess || null;
  } catch {
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    return null;
  }
}

api.interceptors.response.use(
  (res) => res,
  async (error) => {
    const original = error.config;
    if (error.response?.status === 401 && original && !original._retry) {
      original._retry = true;
      if (!refreshing) refreshing = refreshAccessToken().finally(() => { refreshing = null; });
      const newToken = await refreshing;
      if (newToken) {
        original.headers = original.headers || {};
        original.headers.Authorization = `Bearer ${newToken}`;
        return api(original);
      }
    }
    return Promise.reject(error);
  }
);

export function errDetail(x: unknown, fallback: string): string {
  if (x && typeof x === "object" && "response" in x) {
    const data = (x as { response?: { data?: { detail?: string } } }).response?.data;
    if (data?.detail) return data.detail;
  }
  return fallback;
}

export const authApi = {
  register: (email: string, password: string, full_name?: string) =>
    api.post<TokenResponse>("/api/v1/auth/register", { email, password, full_name }),
  login: (email: string, password: string) =>
    api.post<LoginResponse>("/api/v1/auth/login", { email, password }),
  me: () => api.get<User>("/api/v1/auth/me"),
  logoutAll: () => api.post("/api/v1/auth/logout-all"),
  changePassword: (current_password: string, new_password: string) =>
    api.post("/api/v1/auth/change-password", { current_password, new_password }),
  deleteAccount: (password: string) =>
    api.delete("/api/v1/auth/account", { data: { password } }),
  mfaSetup: () => api.post<MfaSetupResponse>("/api/v1/auth/mfa/setup"),
  mfaVerify: (code: string) => api.post("/api/v1/auth/mfa/verify", null, { params: { code } }),
  mfaDisable: (code: string) => api.post("/api/v1/auth/mfa/disable", null, { params: { code } }),
  mfaRecoveryCodes: () => api.post<{ recovery_codes: string[] }>("/api/v1/auth/mfa/recovery-codes"),
  mfaLogin: (mfa_token: string, code: string) =>
    api.post<TokenResponse>("/api/v1/auth/mfa/login", null, { params: { mfa_token, code } }),
};

export const overviewApi = { get: () => api.get<OverviewData>("/api/v1/overview") };
export const eventsApi = {
  list: (params: Record<string, unknown>) => api.get<EventListResponse>("/api/v1/events", { params }),
  stats: () => api.get<EventsStats>("/api/v1/events/stats"),
};
export const integrationsApi = {
  list: () => api.get<Integration[]>("/api/v1/integrations"),
  accounts: () => api.get<ConnectedAccount[]>("/api/v1/integrations/accounts"),
  kinds: () => api.get<{ kinds: string[] }>("/api/v1/integrations/kinds"),
  create: (kind: string, name: string, config?: Record<string, unknown>) =>
    api.post("/api/v1/integrations", config ?? {}, { params: { kind, name } }),
  get: (id: string) => api.get<IntegrationDetails>(`/api/v1/integrations/${id}`),
  summary: (id: string) => api.get<Record<string, unknown>>(`/api/v1/integrations/${id}/summary`),
  sync: (id: string) => api.post<Record<string, unknown>>(`/api/v1/integrations/${id}/sync`),
  delete: (id: string) => api.delete(`/api/v1/integrations/${id}`),
  disconnectAccount: (id: string) => api.delete(`/api/v1/integrations/accounts/${id}`),
  googleLogin: (opts: { gmail?: boolean; calendar?: boolean; drive?: boolean } = {}) => {
    const params: Record<string, boolean> = {};
    if (opts.gmail) params.include_gmail = true;
    if (opts.calendar) params.include_calendar = true;
    if (opts.drive) params.include_drive = true;
    return api.get<{ authorization_url: string; state: string }>("/api/v1/auth/google/login", { params });
  },
};
export const devicesApi = {
  list: () => api.get<Device[]>("/api/v1/devices"),
  register: (name: string, device_type?: string, platform?: string) =>
    api.post<DeviceRegisterResponse>("/api/v1/devices/register", null, { params: { name, device_type, platform } }),
  delete: (id: string) => api.delete(`/api/v1/devices/${id}`),
};
export const reportsApi = {
  summary: (days?: number) => api.get<ReportSummary>("/api/v1/reports/summary", { params: { days } }),
  exportUrl: (format: string, days: number) => `${API}/api/v1/reports/export?format=${format}&days=${days}`,
};
export const securityApi = {
  alerts: () => api.get<{ alerts: Alert[]; count: number }>("/api/v1/security/alerts"),
  audit: () => api.get<AuditEntry[]>("/api/v1/security/audit"),
  retention: () => api.get<{ days: number; default_days: number }>("/api/v1/security/retention"),
};

export const sessionsApi = {
  list: () => api.get<{ sessions: Session[] }>("/api/v1/auth/sessions"),
  revoke: (id: string) => api.post(`/api/v1/auth/sessions/${id}/revoke`),
};

export const apiKeysApi = {
  list: () => api.get<ApiKeyRow[]>("/api/v1/apikeys"),
  create: (name: string) => api.post<ApiKeyCreated>("/api/v1/apikeys", { name }),
  revoke: (id: string) => api.delete(`/api/v1/apikeys/${id}`),
};

export interface RuleInput {
  name: string; description?: string; event_type?: string; source?: string;
  category?: string; application?: string; window_hours: number; min_count: number; severity: string;
}
export const rulesApi = {
  list: () => api.get<DetectionRule[]>("/api/v1/rules"),
  create: (rule: RuleInput) => api.post<{ id: string; name: string }>("/api/v1/rules", rule),
  update: (id: string, rule: Partial<RuleInput> & { enabled?: boolean }) =>
    api.patch<{ ok: boolean }>(`/api/v1/rules/${id}`, rule),
  patch: (id: string, rule: Partial<RuleInput> & { enabled?: boolean }) =>
    api.patch<{ ok: boolean }>(`/api/v1/rules/${id}`, rule),
  toggle: (id: string, enabled: boolean) => api.patch<{ ok: boolean }>(`/api/v1/rules/${id}`, { enabled }),
  toggleEnabled: (id: string, enabled: boolean) => api.patch<{ ok: boolean }>(`/api/v1/rules/${id}`, { enabled }),
  setEnabled: (id: string, enabled: boolean) => api.patch<{ ok: boolean }>(`/api/v1/rules/${id}`, { enabled }),
  updateEnabled: (id: string, enabled: boolean) => api.patch<{ ok: boolean }>(`/api/v1/rules/${id}`, { enabled }),
  enable: (id: string) => api.patch<{ ok: boolean }>(`/api/v1/rules/${id}`, { enabled: true }),
  disable: (id: string) => api.patch<{ ok: boolean }>(`/api/v1/rules/${id}`, { enabled: false }),
  enableRule: (id: string) => api.patch<{ ok: boolean }>(`/api/v1/rules/${id}`, { enabled: true }),
  disableRule: (id: string) => api.patch<{ ok: boolean }>(`/api/v1/rules/${id}`, { enabled: false }),
  setRuleEnabled: (id: string, enabled: boolean) => api.patch<{ ok: boolean }>(`/api/v1/rules/${id}`, { enabled }),
  toggleRule: (id: string, enabled: boolean) => api.patch<{ ok: boolean }>(`/api/v1/rules/${id}`, { enabled }),
  toggleRuleEnabled: (id: string, enabled: boolean) => api.patch<{ ok: boolean }>(`/api/v1/rules/${id}`, { enabled }),
  updateRule: (id: string, rule: Partial<RuleInput> & { enabled?: boolean }) =>
    api.patch<{ ok: boolean }>(`/api/v1/rules/${id}`, rule),
  delete: (id: string) => api.delete(`/api/v1/rules/${id}`),
};

export const insightsApi = { get: (days?: number) => api.get<Insights>("/api/v1/insights", { params: { days } }) };

export const takeoutApi = {
  import: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return api.post<TakeoutSummary>("/api/v1/takeout/import", form);
  },
};