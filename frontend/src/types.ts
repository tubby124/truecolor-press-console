// Types mirror the backend dataclasses / pydantic models in main.py.
// Keep in sync if backend shapes change.

export type Severity = "block" | "warn" | "info";

export interface Finding {
  severity: Severity;
  code: string;
  message: string;
  page: number | null;
}

export interface CostBreakdown {
  paper: number;
  click: number;
  total: number;
}

export interface WorkflowRule {
  workflow: string;
  label: string;
  preset_key: string;
  stock_code: string;
  expect_bleed_in: number;
  notes: string;
}

export interface InspectResult {
  filename: string;
  page_count: number;
  width_in: number;
  height_in: number;
  detected: WorkflowRule | null;
  findings: Finding[];
  cost_preview: CostBreakdown;
  sheets_estimate: number;
  can_send: boolean;
  suggested_quantity: number;
  upload_path: string;
}

export interface Preset {
  key: string;
  sheet: string;
  sheet_in: [number, number];
  piece: string;
  piece_in: [number, number];
  cols: number;
  rows: number;
  total: number;
  bleed_in: number;
  fits: boolean;
  friendly_label?: string;
}

export interface Stock {
  code: string;
  name: string;
  friendly_name?: string;
  finish: string;
  weight: string;
  cost_per_unit: number;
  parent_sheet: string;
  default_tray: string;
  tags: string[];
}

export interface Job {
  job_id: string;
  workflow: string;
  quantity: number;
  sides: number;
  stock_code: string;
  preset_key: string;
  artwork_path: string;
  imposed_path: string | null;
  spool_path: string | null;
  sheets: number;
  paper_cost: number;
  click_cost: number;
  total_cost: number;
  created_at: string;
  status: string;
  findings: Finding[];
}

export interface JobSummary {
  job_id: string;
  workflow: string;
  quantity: number;
  stock_code: string;
  preset_key: string;
  sheets: number;
  total_cost: number;
  status: string;
  created_at: string;
  has_thumb: boolean;
  has_imposed: boolean;
}

export interface TrayInfo {
  stock_code: string | null;
  paper_size: string | null;
  level: "full" | "low" | "empty" | "unknown" | null;
  updated_at: string | null;
  sheets_used: number;
}

export type TrayKey = "T1" | "T2" | "T3" | "T4" | "T5";
export type TrayState = Record<TrayKey, TrayInfo>;

export interface TraysResponse {
  configured: boolean;
  trays: TrayState;
}

export interface PrinterStatus {
  reachable: boolean;
  raw?: string;
  error?: string;
  online?: string;
  code?: string;
  display?: string;
  [key: string]: unknown;
}

export interface Health {
  ok: boolean;
  safe_print_mode: "dry" | "live" | string;
  version: string;
}

export interface BatchItem {
  file: string;
  job?: Job;
  error?: string;
}

export interface PreviewResult {
  preview_id: string;
  preview_url: string;
  thumb_url: string;
  sheets: number;
  paper_cost: number;
  click_cost: number;
  total_cost: number;
}

// ───────────────────────── Test patterns ─────────────────────────
// Mirrors backend/test_patterns_router.py PATTERNS metadata.

export interface TestPattern {
  id: string;
  label: string;
  friendly_label: string;
  file_size_kb: number | null;
  description: string;
  recommended_stock: string;
  recommended_preset: string;
  sheet: string;
  available: boolean;
}

// Returned by POST /api/job/{id}/cancel-spool when successful.
export interface CancelSpoolResult {
  job_id: string;
  cancelled: boolean;
  previous_status: string;
}

// 422 body shape from /api/bleed-fix when the design has no background to
// extend. Caught in InspectCard's bleed handler.
export interface BleedNoContentError {
  error: "design-ends-at-cut-line";
  message: string;
}

// ───────────────────────── Live press state ─────────────────────────
// Mirrors backend/press_state.py composite_state(). Read-only, cached 15s.

export type PressTrayLevelLabel = "empty" | "low" | "ok" | "full" | "unknown" | "other";

export interface PressTrayState {
  description: string;
  paper_type: string | null;
  paper_size: string | null;
  feed_in: number | null;
  xfeed_in: number | null;
  level_raw: number | null;
  level_pct: number | null;
  level_label: PressTrayLevelLabel;
  capacity: number | null;
}

export type PressAlertSeverity = "critical" | "warning" | "other" | "unknown";

export interface PressAlert {
  id: string;
  severity: PressAlertSeverity;
  severity_code: number | null;
  group: string;
  group_code: number | null;
  code: number | null;
  description: string;
  uptime_ticks: number | null;
}

export interface PressDeviceStatus {
  printer_status: string | null;
  printer_status_code: number | null;
  detected_error_bits: string | null;
}

export interface PressLiveState {
  ts: string;
  host: string;
  reachable: boolean;
  snmp_available: boolean;
  snmp_used?: boolean;
  trays: Record<string, PressTrayState>;
  alerts: PressAlert[];
  lifetime_pagecount: number | null;
  device_status: PressDeviceStatus | null;
  error: string | null;
  cached: boolean;
}

// ───────────────────────── Scanner inbox ─────────────────────────
// Files dropped by the C3070 via Scan-to-SMB into the operator's watch folder.
// Mirrors backend/scanner.py list_inbox() output.

export interface ScanItem {
  filename: string;
  size_kb: number;
  modified_at: string; // ISO
  suggested_workflow: "inspect" | "print" | "trash";
  import_url: string;
}

export interface ScanInboxResponse {
  inbox_dir: string;
  items: ScanItem[];
}

// /api/scan/import returns the same shape as /api/inspect plus a couple of
// scanner-specific fields so the frontend can re-use InspectCard.
export interface ScanImportResult extends InspectResult {
  source?: "scanner";
}

export interface ScanSetupResponse {
  markdown: string;
  inbox_dir: string;
}
