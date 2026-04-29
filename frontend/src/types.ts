export type FieldProfile = {
  name: string;
  inferred_type: string;
  empty_count: number;
  non_empty_count: number;
  duplicate_count: number;
  samples: string[];
};

export type Dataset = {
  id: string;
  name: string;
  source_filename: string;
  stored_path: string;
  status: "imported" | "failed";
  row_count: number;
  field_count: number;
  fields: FieldProfile[];
  created_at: string;
  note?: string | null;
};

export type FieldMapping = {
  dataset_id: string;
  primary_key_fields: string[];
  sub_key_fields: string[];
  sensitive_fields: string[];
  group_fields: Record<string, string>;
  updated_at: string;
};

export type Task = {
  id: string;
  name: string;
  dataset_ids: string[];
  rule_package_id?: string | null;
  output_policy: "local_only" | "execution_receipt" | "manual_assertion" | "aggregate_summary";
  aggregate_threshold?: number | null;
  aggregate_group_by?: "department" | "matter_type" | "month" | null;
  status: "draft" | "ready" | "running" | "completed" | "failed";
  description?: string | null;
  created_at: string;
};

export type TaskResult = {
  id: string;
  task_id: string;
  status: "completed" | "failed";
  created_at: string;
  summary: Record<string, unknown>;
  receipt: Record<string, unknown>;
  assertion?: Record<string, unknown> | null;
  aggregate_summary: Array<Record<string, unknown>>;
  suppressed_groups: number;
  local_security_notes: string[];
};

export type RulePackage = {
  id: string;
  name: string;
  version: string;
  purpose: string;
  signature_ref: string;
  rules: Array<Record<string, unknown>>;
  rules_count: number;
  status: "pending_review" | "approved" | "rejected" | "invalid";
  approved_by?: string | null;
  approved_at?: string | null;
  created_at: string;
  notes?: string | null;
};

export type OperatorInfo = {
  code: string;
  name: string;
  category: string;
  description: string;
  output_boundary: "local_only" | "safe_summary";
};

export type ExportRequest = {
  id: string;
  result_id: string;
  export_type: "receipt" | "assertion" | "aggregate_summary";
  requester_name: string;
  purpose: string;
  status: "pending" | "approved" | "rejected";
  approver_name?: string | null;
  requested_at: string;
  approved_at?: string | null;
  rejection_reason?: string | null;
};

export type ExportPackage = {
  request_id: string;
  result_id: string;
  export_type: "receipt" | "assertion" | "aggregate_summary";
  generated_at: string;
  payload: Record<string, unknown>;
  safety_notes: string[];
};

export type ExportFile = {
  id: string;
  request_id: string;
  result_id: string;
  export_type: "receipt" | "assertion" | "aggregate_summary";
  stored_path: string;
  file_name: string;
  sha256: string;
  byte_size: number;
  generated_at: string;
  safety_notes: string[];
};

export type AuditEntry = {
  id: string;
  action: string;
  object_type: string;
  object_id?: string | null;
  summary: string;
  created_at: string;
};

export type AuditChainVerification = {
  valid: boolean;
  total_entries: number;
  checked_entries: number;
  first_invalid_index?: number | null;
  head_hash?: string | null;
  errors: string[];
};

export type HealthResponse = {
  status: "ok";
  mode: "offline-single-node";
  workspace: string;
};

export type DomainPolicy = {
  mode: "domain-local-only";
  summary: string;
  prohibited_exports: string[];
  allowed_exchange: string[];
  allowed_outputs: string[];
  aggregate_min_threshold: number;
  aggregate_grouping_policy: string;
  aggregate_allowed_dimensions: string[];
  assertion_approval_policy: string;
  rule_package_import_policy: string;
  signature_required: boolean;
  default_output_policy: "local_only";
};
