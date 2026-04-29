import type {
  AuditEntry,
  AuditChainVerification,
  Dataset,
  DomainPolicy,
  ExportFile,
  FieldMapping,
  HealthResponse,
  ExportPackage,
  ExportRequest,
  OperatorInfo,
  RulePackage,
  Task,
  TaskResult,
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

export function getRulePackages(): Promise<RulePackage[]> {
  return request<RulePackage[]>("/api/rule-packages");
}

export function createRulePackage(
  name: string,
  purpose: string,
  signatureRef: string,
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
      signature_ref: signatureRef,
      rules,
      notes: "Stage 1 规则包骨架：仅保存规则包元数据，不包含任何数据。",
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

export function createTask(
  name: string,
  datasetIds: string[],
  rulePackageId: string | null,
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
