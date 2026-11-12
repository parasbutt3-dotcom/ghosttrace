export interface User { id: string; email: string; full_name?: string | null; is_admin: boolean; mfa_enabled?: boolean; }

export interface TokenResponse { access_token: string; refresh_token: string; token_type?: string; }

export type LoginResponse = { mfa_required?: boolean; mfa_token?: string; } & Partial<TokenResponse>;

export interface RecentEvent { id: string; timestamp: string; source: string; application: string | null; event_type: string; description: string | null; }

export interface OverviewData {
  accounts: number; integrations: number; devices: number; events: number; active_integrations: number;
  recent_events: RecentEvent[];
}

export interface EventItem {
  id: string; timestamp: string; source: string; application: string | null; event_type: string;
  category: string | null; description: string | null; collection_method: string;
  permission_status: string; confidence: number; metadata?: Record<string, unknown> | null;
}

export interface EventListResponse { total: number; items: EventItem[]; offset: number; limit: number; next_offset: number | null; }

export interface StatsRow { source?: string; category?: string; count: number; }

export interface EventsStats { total: number; by_source: StatsRow[]; by_category: StatsRow[]; }

export interface Capability { name: string; available: boolean; reason: string; requires: string[]; }

export interface Integration {
  id: string; kind: string; name: string; enabled: boolean; status: string;
  last_sync_at: string | null; last_error: string | null; last_sync_summary?: Record<string, unknown> | null;
  created_at: string;
}

export interface IntegrationDetails {
  id: string; kind: string; name: string; status: string; last_sync_at: string | null;
  last_error: string | null; last_sync_summary?: Record<string, unknown> | null;
  config: Record<string, unknown>; capabilities: Capability[];
}

export interface ConnectedAccount {
  id: string; provider: string; display_name: string | null; email: string | null;
  status: string; scopes: string[]; token_expires_at: string | null; created_at: string;
  metadata: Record<string, unknown> | null;
}

export interface Device {
  id: string; name: string; device_type: string; platform: string | null;
  os_version: string | null; app_version: string | null; battery_level: number | null;
  network_type: string | null; last_seen_at: string | null; last_location: Record<string, unknown> | null;
  status: string; created_at: string;
}

export interface DeviceRegisterResponse { id: string; name: string; device_key: string; note?: string; }

export interface Alert { severity: string; type: string; title: string; detail: string; resource_id?: string; }

export interface AuditEntry { id: string; action: string; resource: string | null; resource_id: string | null; details: Record<string, unknown> | null; status: string; ip_address: string | null; created_at: string; }

export interface ReportSummary {
  days: number; total: number;
  by_source: { source: string; count: number }[];
  by_category: { category: string | null; count: number }[];
  top_applications: { application: string; count: number }[];
}

export interface MfaSetupResponse { secret: string; otpauth_uri: string; recovery_codes: string[]; note?: string; }

export interface Session { id: string; ip_address: string | null; user_agent: string | null; created_at: string | null; last_seen_at: string | null; current: boolean; revoked: boolean; }

export interface ApiKeyRow { id: string; name: string; prefix: string; created_at: string | null; last_used_at: string | null; }

export interface ApiKeyCreated extends ApiKeyRow { key: string; note?: string; }

export interface DetectionRule { id: string; name: string; description: string | null; event_type: string | null; source: string | null; category: string | null; application: string | null; window_hours: number; min_count: number; severity: string; enabled: boolean; created_at: string | null; }

export interface TakeoutSummary { ok: boolean; locations: number; place_visits: number; activities: number; youtube: number; total_ingested: number; }

export interface Insights {
  days: number; total_events: number;
  hourly: { hour: number; count: number }[];
  weekdays: { weekday: number; count: number }[];
  top_applications: { application: string; count: number }[];
  by_category: { category: string | null; count: number }[];
  by_source: { source: string; count: number }[];
  active_days: number; current_streak: number;
  correlations: { meetings: number; file_edits: number; git_pushes: number; security_alerts: number;
                  location_points: number; place_visits: number };
  coverage: { integrations_enabled: number; integrations_error: number; devices_seen_24h: number; mfa_enabled: boolean };
}