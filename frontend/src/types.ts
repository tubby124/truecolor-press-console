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
}

export interface Stock {
  code: string;
  name: string;
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
