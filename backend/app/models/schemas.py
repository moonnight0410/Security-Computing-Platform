from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class FieldProfile(BaseModel):
    name: str
    inferred_type: str
    empty_count: int
    non_empty_count: int
    duplicate_count: int
    samples: list[str] = Field(default_factory=list)


class Dataset(BaseModel):
    id: str
    name: str
    source_filename: str
    stored_path: str
    status: Literal["imported", "failed"]
    row_count: int
    field_count: int
    fields: list[FieldProfile] = Field(default_factory=list)
    created_at: str
    note: str | None = None


class FieldMapping(BaseModel):
    dataset_id: str
    primary_key_fields: list[str] = Field(default_factory=list)
    sub_key_fields: list[str] = Field(default_factory=list)
    sensitive_fields: list[str] = Field(default_factory=list)
    group_fields: dict[str, str] = Field(default_factory=dict)
    updated_at: str


class FieldMappingCreate(BaseModel):
    primary_key_fields: list[str] = Field(default_factory=list)
    sub_key_fields: list[str] = Field(default_factory=list)
    sensitive_fields: list[str] = Field(default_factory=list)
    group_fields: dict[str, str] = Field(default_factory=dict)


class TaskCreate(BaseModel):
    name: str
    dataset_ids: list[str] = Field(default_factory=list)
    rule_package_id: str | None = None
    output_policy: Literal["local_only", "execution_receipt", "manual_assertion", "aggregate_summary"] = "local_only"
    aggregate_threshold: int | None = None
    aggregate_group_by: Literal["department", "matter_type", "month"] | None = None
    description: str | None = None


class Task(BaseModel):
    id: str
    name: str
    dataset_ids: list[str] = Field(default_factory=list)
    rule_package_id: str | None = None
    output_policy: Literal["local_only", "execution_receipt", "manual_assertion", "aggregate_summary"] = "local_only"
    aggregate_threshold: int | None = None
    aggregate_group_by: Literal["department", "matter_type", "month"] | None = None
    status: Literal["draft", "ready", "running", "completed", "failed"] = "draft"
    description: str | None = None
    created_at: str


class RulePackageCreate(BaseModel):
    name: str
    version: str = "0.1.0"
    purpose: str
    signature_ref: str
    rules: list[dict[str, Any]] = Field(default_factory=list)
    notes: str | None = None

    @field_validator("signature_ref")
    @classmethod
    def signature_ref_required(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("规则包签名引用不能为空")
        return cleaned


class RulePackageApprove(BaseModel):
    approver_name: str
    comment: str | None = None


class RulePackage(BaseModel):
    id: str
    name: str
    version: str
    purpose: str
    signature_ref: str = "LEGACY-NO-SIGNATURE"
    rules: list[dict[str, Any]] = Field(default_factory=list)
    rules_count: int
    status: Literal["imported", "pending_review", "approved", "rejected", "invalid"] = "pending_review"
    approved_by: str | None = None
    approved_at: str | None = None
    created_at: str
    notes: str | None = None


class OperatorInfo(BaseModel):
    code: str
    name: str
    category: str
    description: str
    output_boundary: Literal["local_only", "safe_summary"]


class TaskResult(BaseModel):
    id: str
    task_id: str
    status: Literal["completed", "failed"]
    created_at: str
    summary: dict[str, Any] = Field(default_factory=dict)
    receipt: dict[str, Any] = Field(default_factory=dict)
    assertion: dict[str, Any] | None = None
    aggregate_summary: list[dict[str, Any]] = Field(default_factory=list)
    suppressed_groups: int = 0
    local_security_notes: list[str] = Field(default_factory=list)


class ExportRequestCreate(BaseModel):
    result_id: str
    export_type: Literal["receipt", "assertion", "aggregate_summary"]
    requester_name: str
    purpose: str

    @field_validator("requester_name", "purpose")
    @classmethod
    def non_empty_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("字段不能为空")
        return cleaned


class ExportRequestApprove(BaseModel):
    approver_name: str
    comment: str | None = None

    @field_validator("approver_name")
    @classmethod
    def approver_required(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("审批人不能为空")
        return cleaned


class ExportRequest(BaseModel):
    id: str
    result_id: str
    export_type: Literal["receipt", "assertion", "aggregate_summary"]
    requester_name: str
    purpose: str
    status: Literal["pending", "approved", "rejected"] = "pending"
    approver_name: str | None = None
    requested_at: str
    approved_at: str | None = None
    rejection_reason: str | None = None


class ExportPackage(BaseModel):
    request_id: str
    result_id: str
    export_type: Literal["receipt", "assertion", "aggregate_summary"]
    generated_at: str
    payload: dict[str, Any]
    safety_notes: list[str] = Field(default_factory=list)


class ExportFile(BaseModel):
    id: str
    request_id: str
    result_id: str
    export_type: Literal["receipt", "assertion", "aggregate_summary"]
    stored_path: str
    file_name: str
    sha256: str
    byte_size: int
    generated_at: str
    safety_notes: list[str] = Field(default_factory=list)


class AuditEntry(BaseModel):
    id: str
    action: str
    object_type: str
    object_id: str | None = None
    summary: str
    created_at: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class AuditChainVerification(BaseModel):
    valid: bool
    total_entries: int
    checked_entries: int
    first_invalid_index: int | None = None
    head_hash: str | None = None
    errors: list[str] = Field(default_factory=list)


class HealthResponse(BaseModel):
    status: Literal["ok"]
    mode: Literal["offline-single-node"]
    workspace: str


class DomainPolicy(BaseModel):
    mode: Literal["domain-local-only"]
    summary: str
    prohibited_exports: list[str]
    allowed_exchange: list[str]
    allowed_outputs: list[str]
    aggregate_min_threshold: int
    aggregate_grouping_policy: str
    aggregate_allowed_dimensions: list[str]
    assertion_approval_policy: str
    rule_package_import_policy: str
    signature_required: bool
    default_output_policy: Literal["local_only"]
