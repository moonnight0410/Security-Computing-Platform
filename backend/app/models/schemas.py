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


def required_text(value: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise ValueError("瀛楁涓嶈兘涓虹┖")
    return cleaned


class RuleTemplateCreate(BaseModel):
    name: str
    description: str | None = None
    rules: list[dict[str, Any]] = Field(default_factory=list)
    created_by: str

    @field_validator("name", "created_by")
    @classmethod
    def validate_required_fields(cls, value: str) -> str:
        return required_text(value)


class RuleTemplate(BaseModel):
    id: str
    name: str
    description: str | None = None
    rules: list[dict[str, Any]] = Field(default_factory=list)
    rules_count: int = 0
    created_by: str
    created_at: str
    updated_at: str


class RuleSnippetCreate(BaseModel):
    name: str
    description: str | None = None
    rule: dict[str, Any]
    created_by: str

    @field_validator("name", "created_by")
    @classmethod
    def validate_required_fields(cls, value: str) -> str:
        return required_text(value)


class RuleSnippet(BaseModel):
    id: str
    name: str
    description: str | None = None
    rule: dict[str, Any]
    created_by: str
    created_at: str
    updated_at: str


class TaskCreate(BaseModel):
    name: str
    dataset_ids: list[str] = Field(default_factory=list)
    rule_package_id: str | None = None
    rule_package_revision_id: str | None = None
    output_policy: Literal["local_only", "execution_receipt", "manual_assertion", "aggregate_summary"] = "local_only"
    aggregate_threshold: int | None = None
    aggregate_group_by: Literal["department", "matter_type", "month"] | None = None
    description: str | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        return required_text(value)


class TaskUpdate(BaseModel):
    name: str
    dataset_ids: list[str] = Field(default_factory=list)
    rule_package_id: str | None = None
    rule_package_revision_id: str | None = None
    output_policy: Literal["local_only", "execution_receipt", "manual_assertion", "aggregate_summary"] = "local_only"
    aggregate_threshold: int | None = None
    aggregate_group_by: Literal["department", "matter_type", "month"] | None = None
    description: str | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        return required_text(value)


class Task(BaseModel):
    id: str
    name: str
    dataset_ids: list[str] = Field(default_factory=list)
    rule_package_id: str | None = None
    rule_package_revision_id: str | None = None
    output_policy: Literal["local_only", "execution_receipt", "manual_assertion", "aggregate_summary"] = "local_only"
    aggregate_threshold: int | None = None
    aggregate_group_by: Literal["department", "matter_type", "month"] | None = None
    status: Literal["draft", "ready", "running", "completed", "failed"] = "draft"
    description: str | None = None
    created_at: str
    updated_at: str | None = None


def required_text(value: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise ValueError("字段不能为空")
    return cleaned


class RulePackageCreate(BaseModel):
    name: str
    version: str = "0.1.0"
    purpose: str
    signer_name: str = ""
    signature_ref: str = ""
    signature: str = ""
    rules: list[dict[str, Any]] = Field(default_factory=list)
    notes: str | None = None
    editor_name: str = "经办员A"
    change_summary: str | None = None

    @field_validator("name", "purpose", "editor_name")
    @classmethod
    def validate_required_fields(cls, value: str) -> str:
        return required_text(value)

    @field_validator("signer_name", "signature_ref", "signature")
    @classmethod
    def trim_signature_fields(cls, value: str) -> str:
        return value.strip()


class RulePackageDraftSave(BaseModel):
    name: str
    version: str = "0.1.0"
    purpose: str
    signer_name: str = ""
    signature_ref: str = ""
    signature: str = ""
    rules: list[dict[str, Any]] = Field(default_factory=list)
    notes: str | None = None
    editor_name: str
    change_summary: str | None = None
    auto_saved: bool = False

    @field_validator("name", "purpose", "editor_name")
    @classmethod
    def validate_required_fields(cls, value: str) -> str:
        return required_text(value)

    @field_validator("signer_name", "signature_ref", "signature")
    @classmethod
    def trim_signature_fields(cls, value: str) -> str:
        return value.strip()


class RulePackageApprove(BaseModel):
    approver_name: str
    comment: str | None = None

    @field_validator("approver_name")
    @classmethod
    def validate_approver(cls, value: str) -> str:
        return required_text(value)


class RulePackageBatchAction(BaseModel):
    package_ids: list[str] = Field(default_factory=list)
    approver_name: str | None = None
    comment: str | None = None


class RulePackageDeprecate(BaseModel):
    operator_name: str
    reason: str

    @field_validator("operator_name", "reason")
    @classmethod
    def validate_required_fields(cls, value: str) -> str:
        return required_text(value)


RulePackageStatus = Literal["draft", "pending_review", "approved", "invalid", "deprecated", "deleted"]
RulePackageVerificationStatus = Literal["not_signed", "verified", "failed", "legacy_unverified"]


class RulePackage(BaseModel):
    id: str
    name: str
    version: str
    purpose: str
    signer_name: str = ""
    signature_ref: str = ""
    signature: str = ""
    rules: list[dict[str, Any]] = Field(default_factory=list)
    rules_count: int
    status: RulePackageStatus = "draft"
    verification_status: RulePackageVerificationStatus = "not_signed"
    verification_message: str | None = None
    verified_at: str | None = None
    approved_by: str | None = None
    approved_at: str | None = None
    created_at: str
    updated_at: str | None = None
    current_revision_id: str | None = None
    current_revision_no: int = 1
    latest_editor_name: str | None = None
    latest_edited_at: str | None = None
    signature_outdated: bool = True
    deleted_at: str | None = None
    deprecated_at: str | None = None
    deprecated_by: str | None = None
    deprecation_reason: str | None = None
    notes: str | None = None


class RulePackageRevision(BaseModel):
    id: str
    rule_package_id: str
    revision_no: int
    name: str
    version: str
    purpose: str
    signer_name: str = ""
    signature_ref: str = ""
    signature: str = ""
    rules: list[dict[str, Any]] = Field(default_factory=list)
    rules_count: int
    status: RulePackageStatus = "draft"
    verification_status: RulePackageVerificationStatus = "not_signed"
    verification_message: str | None = None
    verified_at: str | None = None
    approved_by: str | None = None
    approved_at: str | None = None
    notes: str | None = None
    change_summary: str | None = None
    editor_name: str | None = None
    saved_by_auto: bool = False
    signature_outdated: bool = True
    based_on_revision_id: str | None = None
    content_hash: str
    created_at: str


class RulePackageDiffFieldChange(BaseModel):
    field: str
    before: Any | None = None
    after: Any | None = None


class RulePackageDiffRuleChange(BaseModel):
    change_type: Literal["added", "removed", "modified"]
    rule_key: str
    field: str
    operator: str
    before_value: Any | None = None
    after_value: Any | None = None


class RulePackageRevisionDiff(BaseModel):
    package_id: str
    package_name: str
    from_revision_id: str
    from_revision_no: int
    to_revision_id: str
    to_revision_no: int
    based_on_match: bool
    field_changes: list[RulePackageDiffFieldChange] = Field(default_factory=list)
    rule_changes: list[RulePackageDiffRuleChange] = Field(default_factory=list)
    summary: dict[str, Any] = Field(default_factory=dict)


class RulePackageTaskReference(BaseModel):
    task_id: str
    task_name: str
    task_status: str
    created_at: str
    output_policy: str
    referenced_revision_id: str | None = None
    referenced_revision_no: int | None = None
    referenced_revision_status: RulePackageStatus | None = None
    is_current_revision: bool = False


class RulePackageRevisionReferenceSummary(BaseModel):
    revision_id: str
    revision_no: int
    revision_status: RulePackageStatus
    is_current_revision: bool = False
    task_count: int = 0


class RulePackageUsageReport(BaseModel):
    package_id: str
    package_name: str
    current_revision_id: str | None = None
    current_revision_no: int | None = None
    total_task_count: int = 0
    current_revision_task_count: int = 0
    historical_revision_task_count: int = 0
    revision_summaries: list[RulePackageRevisionReferenceSummary] = Field(default_factory=list)
    tasks: list[RulePackageTaskReference] = Field(default_factory=list)


class RulePackageBatchResult(BaseModel):
    package_id: str
    name: str
    success: bool
    status: str
    message: str


class OperatorInfo(BaseModel):
    code: str
    name: str
    category: str
    description: str
    output_boundary: Literal["local_only", "safe_summary"]


class AssertionReviewState(BaseModel):
    status: Literal["pending_review", "approved", "rejected"]
    statement: str
    created_at: str
    reviewer_name: str | None = None
    reviewed_at: str | None = None
    review_comment: str | None = None
    rejection_reason: str | None = None


class TaskResult(BaseModel):
    id: str
    task_id: str
    status: Literal["completed", "failed"]
    created_at: str
    summary: dict[str, Any] = Field(default_factory=dict)
    receipt: dict[str, Any] = Field(default_factory=dict)
    assertion: AssertionReviewState | None = None
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
        return required_text(value)


class ExportRequestApprove(BaseModel):
    approver_name: str
    comment: str | None = None

    @field_validator("approver_name")
    @classmethod
    def approver_required(cls, value: str) -> str:
        return required_text(value)


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


class ExportArchiveCreate(BaseModel):
    export_file_ids: list[str] = Field(default_factory=list)
    archived_by: str
    purpose: str

    @field_validator("archived_by", "purpose")
    @classmethod
    def archive_text_required(cls, value: str) -> str:
        return required_text(value)


class ExportArchiveVerification(BaseModel):
    valid: bool
    manifest_hash: str
    signature_verified: bool
    audit_chain_valid: bool
    errors: list[str] = Field(default_factory=list)


class ExportArchive(BaseModel):
    id: str
    export_file_ids: list[str] = Field(default_factory=list)
    archived_by: str
    purpose: str
    archived_at: str
    archive_dir: str
    manifest_path: str
    report_path: str
    signature_path: str
    signer_name: str
    signer_key_ref: str
    manifest_hash: str
    file_count: int
    verification: ExportArchiveVerification


class AssertionReviewRequest(BaseModel):
    reviewer_name: str
    decision: Literal["approved", "rejected"]
    final_statement: str | None = None
    comment: str | None = None

    @field_validator("reviewer_name")
    @classmethod
    def reviewer_required(cls, value: str) -> str:
        return required_text(value)


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


class TrustedSignerInfo(BaseModel):
    signer_name: str
    key_type: Literal["rsa-public-key"]
    signature_ref: str
    status: Literal["active", "disabled"]
    public_key_path: str
    description: str | None = None


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


class GovernanceDashboard(BaseModel):
    task_counts: dict[str, int] = Field(default_factory=dict)
    output_counts: dict[str, int] = Field(default_factory=dict)
    rule_package_counts: dict[str, int] = Field(default_factory=dict)
    pending_assertion_count: int = 0
    audit_total_entries: int = 0
    recent_tasks: list[Task] = Field(default_factory=list)
    recent_export_requests: list[ExportRequest] = Field(default_factory=list)
    recent_export_files: list[ExportFile] = Field(default_factory=list)
    recent_archives: list[ExportArchive] = Field(default_factory=list)
