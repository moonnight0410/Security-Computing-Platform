import type {
  AuditEntry,
  AuditChainVerification,
  Dataset,
  DomainPolicy,
  ExportArchive,
  ExportFile,
  FieldMapping,
  HealthResponse,
  ExportPackage,
  ExportRequest,
  OperatorInfo,
  RulePackageBatchResult,
  RulePackage,
  RulePackageRevision,
  Task,
  TaskResult,
  TrustedSignerInfo,
} from "./types";

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://127.0.0.1:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, init);
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Request failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export function getHealth(): Promise<HealthResponse> {
  return request<HealthResponse>("/api/health");
}

export function getDomainPolicy(): Promise<DomainPolicy> {
  return request<DomainPolicy>("/api/domain-policy");
}

export function getDatasets(): Promise<Dataset[]> {
  return request<Dataset[]>("/api/datasets");
}

export function getFieldMapping(datasetId: string): Promise<FieldMapping> {
  return request<FieldMapping>(`/api/datasets/${datasetId}/field-mapping`);
}

export function saveFieldMapping(
  datasetId: string,
  payload: Omit<FieldMapping, "dataset_id" | "updated_at">,
): Promise<FieldMapping> {
  return request<FieldMapping>(`/api/datasets/${datasetId}/field-mapping`, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
}

export function uploadDataset(file: File): Promise<Dataset> {
  const form = new FormData();
  form.append("file", file);
  return request<Dataset>("/api/datasets/import", {
    method: "POST",
    body: form,
  });
}

export function getTasks(): Promise<Task[]> {
  return request<Task[]>("/api/tasks");
}

export function executeTask(taskId: string): Promise<TaskResult> {
  return request<TaskResult>(`/api/tasks/${taskId}/execute`, {
    method: "POST",
  });
}

export function getResults(): Promise<TaskResult[]> {
  return request<TaskResult[]>("/api/results");
}

export function getOperators(): Promise<OperatorInfo[]> {
  return request<OperatorInfo[]>("/api/operators");
}

export function getExportRequests(): Promise<ExportRequest[]> {
  return request<ExportRequest[]>("/api/export-requests");
}

export function getExportFiles(): Promise<ExportFile[]> {
  return request<ExportFile[]>("/api/export-files");
}

export function createExportRequest(
  resultId: string,
  exportType: "receipt" | "assertion" | "aggregate_summary",
  requesterName: string,
  purpose: string,
): Promise<ExportRequest> {
  return request<ExportRequest>("/api/export-requests", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      result_id: resultId,
      export_type: exportType,
      requester_name: requesterName,
      purpose,
    }),
  });
}

export function approveExportRequest(requestId: string, approverName: string): Promise<ExportRequest> {
  return request<ExportRequest>(`/api/export-requests/${requestId}/approve`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      approver_name: approverName,
    }),
  });
}

export function getExportPackage(requestId: string): Promise<ExportPackage> {
  return request<ExportPackage>(`/api/export-requests/${requestId}/package`);
}

export function persistExportFile(requestId: string): Promise<ExportFile> {
  return request<ExportFile>(`/api/export-requests/${requestId}/file`, {
    method: "POST",
  });
}

export function getExportArchives(): Promise<ExportArchive[]> {
  return request<ExportArchive[]>("/api/export-archives");
}

export function createExportArchive(
  exportFileIds: string[],
  archivedBy: string,
  purpose: string,
): Promise<ExportArchive> {
  return request<ExportArchive>("/api/export-archives", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      export_file_ids: exportFileIds,
      archived_by: archivedBy,
      purpose,
    }),
  });
}

export function verifyExportArchive(archiveId: string): Promise<ExportArchive> {
  return request<ExportArchive>(`/api/export-archives/${archiveId}/verify`);
}

export function getRulePackages(): Promise<RulePackage[]> {
  return request<RulePackage[]>("/api/rule-packages");
}

export function getRuleSigners(): Promise<TrustedSignerInfo[]> {
  return request<TrustedSignerInfo[]>("/api/rule-signers");
}

export function createRulePackage(
  name: string,
  purpose: string,
  signerName: string,
  signatureRef: string,
  signature: string,
  rules: Array<Record<string, unknown>>,
): Promise<RulePackage> {
  return request<RulePackage>("/api/rule-packages", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      name,
      purpose,
      version: "0.1.0",
      signer_name: signerName,
      signature_ref: signatureRef,
      signature,
      rules,
      notes: "Stage 8 规则包登记：包含签名人、RSA 签名引用和签名值，用于本域公私钥验签。",
    }),
  });
}

export function verifyRulePackage(rulePackageId: string): Promise<RulePackage> {
  return request<RulePackage>(`/api/rule-packages/${rulePackageId}/verify`, {
    method: "POST",
  });
}

export function batchVerifyRulePackages(packageIds: string[]): Promise<RulePackageBatchResult[]> {
  return request<RulePackageBatchResult[]>("/api/rule-packages/batch-verify", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      package_ids: packageIds,
    }),
  });
}

export function approveRulePackage(rulePackageId: string, approverName: string): Promise<RulePackage> {
  return request<RulePackage>(`/api/rule-packages/${rulePackageId}/approve`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      approver_name: approverName,
    }),
  });
}

export function batchApproveRulePackages(
  packageIds: string[],
  approverName: string,
  comment?: string,
): Promise<RulePackageBatchResult[]> {
  return request<RulePackageBatchResult[]>("/api/rule-packages/batch-approve", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      package_ids: packageIds,
      approver_name: approverName,
      comment,
    }),
  });
}

export function createTask(
  name: string,
  datasetIds: string[],
  rulePackageId: string | null,
  rulePackageRevisionId: string | null,
  outputPolicy: "local_only" | "execution_receipt" | "manual_assertion" | "aggregate_summary",
  aggregateThreshold?: number,
  aggregateGroupBy?: "department" | "matter_type" | "month",
): Promise<Task> {
  return request<Task>("/api/tasks", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      name,
      dataset_ids: datasetIds,
      rule_package_id: rulePackageId,
      rule_package_revision_id: rulePackageRevisionId,
      output_policy: outputPolicy,
      aggregate_threshold: aggregateThreshold,
      aggregate_group_by: aggregateGroupBy,
    }),
  });
}

export function getAudit(): Promise<AuditEntry[]> {
  return request<AuditEntry[]>("/api/audit");
}

export function verifyAuditChain(): Promise<AuditChainVerification> {
  return request<AuditChainVerification>("/api/audit/verify");
}

export function getRulePackageCenterPackages(): Promise<RulePackage[]> {
  return request<RulePackage[]>("/api/rule-package-center/packages");
}

export function createRulePackageDraft(payload: {
  name: string;
  version: string;
  purpose: string;
  signer_name: string;
  signature_ref: string;
  signature: string;
  rules: Array<Record<string, unknown>>;
  notes?: string;
  editor_name: string;
  change_summary?: string;
}): Promise<RulePackage> {
  return request<RulePackage>("/api/rule-package-center/packages", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
}

export function getRulePackageRevisions(rulePackageId: string): Promise<RulePackageRevision[]> {
  return request<RulePackageRevision[]>(`/api/rule-package-center/packages/${rulePackageId}/revisions`);
}

export function beginRulePackageEdit(rulePackageId: string, editorName: string): Promise<RulePackageRevision> {
  const search = new URLSearchParams({ editor_name: editorName }).toString();
  return request<RulePackageRevision>(`/api/rule-package-center/packages/${rulePackageId}/edit?${search}`, {
    method: "POST",
  });
}

export function saveRulePackageDraft(rulePackageId: string, payload: {
  name: string;
  version: string;
  purpose: string;
  signer_name: string;
  signature_ref: string;
  signature: string;
  rules: Array<Record<string, unknown>>;
  notes?: string;
  editor_name: string;
  change_summary?: string;
  auto_saved?: boolean;
}): Promise<RulePackageRevision> {
  return request<RulePackageRevision>(`/api/rule-package-center/packages/${rulePackageId}/draft-save`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
}

export function submitRulePackageVerification(rulePackageId: string): Promise<RulePackage> {
  return request<RulePackage>(`/api/rule-package-center/packages/${rulePackageId}/submit-verification`, {
    method: "POST",
  });
}

export function approveRulePackageCenter(rulePackageId: string, approverName: string, comment?: string): Promise<RulePackage> {
  return request<RulePackage>(`/api/rule-package-center/packages/${rulePackageId}/approve`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      approver_name: approverName,
      comment,
    }),
  });
}

export function deprecateRulePackage(rulePackageId: string, operatorName: string, reason: string): Promise<RulePackage> {
  return request<RulePackage>(`/api/rule-package-center/packages/${rulePackageId}/deprecate`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      operator_name: operatorName,
      reason,
    }),
  });
}

export async function deleteRulePackage(rulePackageId: string): Promise<void> {
  await request<{ status: string }>(`/api/rule-package-center/packages/${rulePackageId}`, {
    method: "DELETE",
  });
}

export function reviewAssertion(
  resultId: string,
  reviewerName: string,
  decision: "approved" | "rejected",
  finalStatement?: string,
  comment?: string,
): Promise<TaskResult> {
  return request<TaskResult>(`/api/results/${resultId}/assertion/review`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      reviewer_name: reviewerName,
      decision,
      final_statement: finalStatement,
      comment,
    }),
  });
}
