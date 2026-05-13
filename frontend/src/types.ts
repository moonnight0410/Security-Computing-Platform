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

export type RuleLeafNode = {
  type: "rule";
  field: string;
  operator: "eq" | "neq" | "exists" | "not_empty" | "gte" | "lte" | "in";
  value: unknown;
};

export type RuleGroupNode = {
  type: "group";
  logic: "and" | "or";
  children: RuleNode[];
};

export type RuleNode = RuleLeafNode | RuleGroupNode;

export type RuleTemplate = {
  id: string;
  name: string;
  description?: string | null;
  rules: Array<Record<string, unknown>>;
  rules_count: number;
  created_by: string;
  created_at: string;
  updated_at: string;
};

export type RuleSnippet = {
  id: string;
  name: string;
  description?: string | null;
  rule: Record<string, unknown>;
  created_by: string;
  created_at: string;
  updated_at: string;
};

export type Task = {
  id: string;
  name: string;
  dataset_ids: string[];
  rule_package_id?: string | null;
  rule_package_revision_id?: string | null;
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
  assertion?: AssertionReviewState | null;
  aggregate_summary: Array<Record<string, unknown>>;
  suppressed_groups: number;
  local_security_notes: string[];
};

export type AssertionReviewState = {
  status: "pending_review" | "approved" | "rejected";
  statement: string;
  created_at: string;
  reviewer_name?: string | null;
  reviewed_at?: string | null;
  review_comment?: string | null;
  rejection_reason?: string | null;
};

export type RulePackage = {
  id: string;
  name: string;
  version: string;
  purpose: string;
  signer_name: string;
  signature_ref: string;
  signature: string;
  rules: Array<Record<string, unknown>>;
  rules_count: number;
  status: "draft" | "pending_review" | "approved" | "invalid" | "deprecated" | "deleted";
  verification_status: "not_signed" | "verified" | "failed" | "legacy_unverified";
  verification_message?: string | null;
  verified_at?: string | null;
  approved_by?: string | null;
  approved_at?: string | null;
  created_at: string;
  updated_at?: string | null;
  current_revision_id?: string | null;
  current_revision_no: number;
  latest_editor_name?: string | null;
  latest_edited_at?: string | null;
  signature_outdated: boolean;
  deprecated_at?: string | null;
  deprecated_by?: string | null;
  deprecation_reason?: string | null;
  notes?: string | null;
};

export type RulePackageRevision = {
  id: string;
  rule_package_id: string;
  revision_no: number;
  name: string;
  version: string;
  purpose: string;
  signer_name: string;
  signature_ref: string;
  signature: string;
  rules: Array<Record<string, unknown>>;
  rules_count: number;
  status: "draft" | "pending_review" | "approved" | "invalid" | "deprecated" | "deleted";
  verification_status: "not_signed" | "verified" | "failed" | "legacy_unverified";
  verification_message?: string | null;
  verified_at?: string | null;
  approved_by?: string | null;
  approved_at?: string | null;
  notes?: string | null;
  change_summary?: string | null;
  editor_name?: string | null;
  saved_by_auto: boolean;
  signature_outdated: boolean;
  based_on_revision_id?: string | null;
  content_hash: string;
  created_at: string;
};

export type RulePackageDiffFieldChange = {
  field: string;
  before?: unknown | null;
  after?: unknown | null;
};

export type RulePackageDiffRuleChange = {
  change_type: "added" | "removed" | "modified";
  rule_key: string;
  field: string;
  operator: string;
  before_value?: unknown | null;
  after_value?: unknown | null;
};

export type RulePackageRevisionDiff = {
  package_id: string;
  package_name: string;
  from_revision_id: string;
  from_revision_no: number;
  to_revision_id: string;
  to_revision_no: number;
  based_on_match: boolean;
  field_changes: RulePackageDiffFieldChange[];
  rule_changes: RulePackageDiffRuleChange[];
  summary: Record<string, unknown>;
};

export type RulePackageTaskReference = {
  task_id: string;
  task_name: string;
  task_status: string;
  created_at: string;
  output_policy: string;
  referenced_revision_id?: string | null;
  referenced_revision_no?: number | null;
  referenced_revision_status?: RulePackage["status"] | null;
  is_current_revision: boolean;
};

export type RulePackageRevisionReferenceSummary = {
  revision_id: string;
  revision_no: number;
  revision_status: RulePackage["status"];
  is_current_revision: boolean;
  task_count: number;
};

export type RulePackageUsageReport = {
  package_id: string;
  package_name: string;
  current_revision_id?: string | null;
  current_revision_no?: number | null;
  total_task_count: number;
  current_revision_task_count: number;
  historical_revision_task_count: number;
  revision_summaries: RulePackageRevisionReferenceSummary[];
  tasks: RulePackageTaskReference[];
};

export type RulePackageBatchResult = {
  package_id: string;
  name: string;
  success: boolean;
  status: string;
  message: string;
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

export type ExportArchiveVerification = {
  valid: boolean;
  manifest_hash: string;
  signature_verified: boolean;
  audit_chain_valid: boolean;
  errors: string[];
};

export type ExportArchive = {
  id: string;
  export_file_ids: string[];
  archived_by: string;
  purpose: string;
  archived_at: string;
  archive_dir: string;
  manifest_path: string;
  report_path: string;
  signature_path: string;
  signer_name: string;
  signer_key_ref: string;
  manifest_hash: string;
  file_count: number;
  verification: ExportArchiveVerification;
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

export type TrustedSignerInfo = {
  signer_name: string;
  key_type: "rsa-public-key";
  signature_ref: string;
  status: "active" | "disabled";
  public_key_path: string;
  description?: string | null;
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

export type GovernanceDashboard = {
  task_counts: Record<string, number>;
  output_counts: Record<string, number>;
  rule_package_counts: Record<string, number>;
  pending_assertion_count: number;
  audit_total_entries: number;
  recent_tasks: Task[];
  recent_export_requests: ExportRequest[];
  recent_export_files: ExportFile[];
  recent_archives: ExportArchive[];
};
