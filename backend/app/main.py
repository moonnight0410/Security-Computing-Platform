from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import IMPORTS_DIR, WORKSPACE_ROOT, ensure_workspace
from app.models.schemas import (
    AuditEntry,
    AssertionReviewRequest,
    Dataset,
    DomainPolicy,
    AuditChainVerification,
    ExportArchive,
    ExportArchiveCreate,
    ExportFile,
    ExportPackage,
    ExportRequest,
    ExportRequestApprove,
    ExportRequestCreate,
    FieldMapping,
    FieldMappingCreate,
    GovernanceDashboard,
    HealthResponse,
    OperatorInfo,
    RulePackage,
    RulePackageApprove,
    RulePackageBatchAction,
    RulePackageBatchResult,
    RulePackageRevisionDiff,
    RuleSnippet,
    RuleSnippetCreate,
    RuleTemplate,
    RuleTemplateCreate,
    RulePackageUsageReport,
    RulePackageCreate,
    RulePackageDeprecate,
    RulePackageDraftSave,
    RulePackageRevision,
    Task,
    TaskCreate,
    TaskResult,
    TrustedSignerInfo,
)
from app.services.archives import archive_export_files, load_archive_signer, verify_archive_report
from app.services.assertions import review_assertion
from app.services.audit import utc_now, verify_audit_chain, write_audit
from app.services.app_logging import configure_logging, get_logger
from app.services.execution import execute_local_task
from app.services.exports import approve_export_request, build_export_package, create_export_request, persist_export_package
from app.services.governance_dashboard import build_governance_dashboard
from app.services.operators import list_operators
from app.services.profiling import profile_csv
from app.services.rule_assets import create_rule_snippet, create_rule_template
from app.services.rule_packages import (
    approve_revision,
    build_rule_package_usage_report,
    create_edit_revision,
    create_rule_package_entities,
    deprecate_package,
    editable_revision_for_package,
    compare_rule_package_revisions,
    latest_revision,
    materialize_package_from_revision,
    package_can_be_deleted,
    save_rule_package_revision,
    submit_revision_for_verification,
)
from app.services.rule_signatures import apply_rule_package_verification, list_trusted_signers
from app.services.storage import add_record, load_state, replace_collection

ensure_workspace()
configure_logging()
logger = get_logger(__name__)

AGGREGATE_MIN_THRESHOLD = 10
AGGREGATE_ALLOWED_DIMENSIONS = {"department", "matter_type", "month"}
ALLOWED_UPLOAD_SUFFIXES = {".csv", ".xlsx", ".xls"}

app = FastAPI(
    title="政府部门联查数据计算单机系统",
    version="0.11.0-stage11-domain-local",
    description="Stage 11 API with reusable rule assets, nested AND/OR composition, and governance dashboard.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("unhandled path=%s method=%s", request.url.path, request.method)
    return JSONResponse(
        status_code=500,
        content={"detail": "服务内部错误，已写入本地日志"},
    )


@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        mode="offline-single-node",
        workspace=str(WORKSPACE_ROOT),
    )


@app.get("/api/domain-policy", response_model=DomainPolicy)
def domain_policy() -> DomainPolicy:
    return DomainPolicy(
        mode="domain-local-only",
        summary="所有本域数据、加密数据、哈希数据、去标识键、派生主键和明细结果均不得出域。",
        prohibited_exports=[
            "原始数据",
            "加密数据",
            "哈希数据",
            "去标识数据",
            "派生主键 / 子键",
            "对象级明细结果",
            "可反推对象存在性的细粒度统计",
        ],
        allowed_exchange=[
            "不含数据的规则包",
            "不含数据的算子包",
            "空模板",
            "执行状态回执",
            "经授权且不含明细的结论声明",
        ],
        allowed_outputs=[
            "执行状态回执",
            "经授权结论声明",
            "满足最小阈值的聚合统计",
        ],
        aggregate_min_threshold=AGGREGATE_MIN_THRESHOLD,
        aggregate_grouping_policy="仅允许单维粗粒度分组",
        aggregate_allowed_dimensions=sorted(AGGREGATE_ALLOWED_DIMENSIONS),
        assertion_approval_policy="执行人与审核人分离，结论声明需正式审核通过后方可申请输出",
        rule_package_import_policy="规则包必须通过本域 RSA 公钥验签，并经单名审批人批准后才能用于任务",
        signature_required=True,
        default_output_policy="local_only",
    )


@app.get("/api/datasets", response_model=list[Dataset])
def list_datasets() -> list[Dataset]:
    return [Dataset(**item) for item in load_state()["datasets"]]


@app.post("/api/datasets/import", response_model=Dataset)
async def import_dataset(file: UploadFile = File(...)) -> Dataset:
    original_name = Path(file.filename or "dataset.csv").name
    suffix = Path(original_name).suffix.lower()
    if suffix not in ALLOWED_UPLOAD_SUFFIXES:
        raise HTTPException(status_code=400, detail="仅支持 CSV、XLSX、XLS 文件")

    dataset_id = str(uuid4())
    stored_name = f"{dataset_id}{suffix or '.dat'}"
    stored_path = IMPORTS_DIR / stored_name

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="上传文件为空")

    stored_path.write_bytes(content)

    fields = []
    row_count = 0
    note = None
    if suffix == ".csv":
        try:
            row_count, fields = profile_csv(stored_path)
        except UnicodeDecodeError as error:
            raise HTTPException(status_code=400, detail="CSV 编码无法识别，请使用 UTF-8 编码") from error
        except Exception as error:
            raise HTTPException(status_code=400, detail=f"CSV 解析失败：{error}") from error
    else:
        note = "当前仅对 CSV 生成字段画像，Excel 文件先完成本地落盘。"

    dataset = Dataset(
        id=dataset_id,
        name=Path(original_name).stem,
        source_filename=original_name,
        stored_path=str(stored_path),
        status="imported",
        row_count=row_count,
        field_count=len(fields),
        fields=fields,
        created_at=utc_now(),
        note=note,
    )

    add_record("datasets", dataset.model_dump())
    write_audit(
        action="dataset.import",
        object_type="dataset",
        object_id=dataset.id,
        summary=f"本域导入数据集：{dataset.source_filename}",
        metadata={"row_count": row_count, "field_count": len(fields), "export_policy": "local_only"},
    )
    return dataset


@app.get("/api/datasets/{dataset_id}", response_model=Dataset)
def get_dataset(dataset_id: str) -> Dataset:
    for item in load_state()["datasets"]:
        if item["id"] == dataset_id:
            return Dataset(**item)
    raise HTTPException(status_code=404, detail="Dataset not found")


def find_dataset(dataset_id: str) -> Dataset:
    for item in load_state()["datasets"]:
        if item["id"] == dataset_id:
            return Dataset(**item)
    raise HTTPException(status_code=404, detail="Dataset not found")


def dataset_field_names(dataset: Dataset) -> set[str]:
    return {field.name for field in dataset.fields}


@app.get("/api/datasets/{dataset_id}/field-mapping", response_model=FieldMapping)
def get_field_mapping(dataset_id: str) -> FieldMapping:
    for item in load_state()["field_mappings"]:
        if item["dataset_id"] == dataset_id:
            return FieldMapping(**item)

    dataset = find_dataset(dataset_id)
    fields = [field.name for field in dataset.fields]
    default_mapping = FieldMapping(
        dataset_id=dataset_id,
        primary_key_fields=fields[:1],
        sub_key_fields=fields[1:2],
        sensitive_fields=fields[:1],
        group_fields={},
        updated_at=utc_now(),
    )
    return default_mapping


@app.put("/api/datasets/{dataset_id}/field-mapping", response_model=FieldMapping)
def save_field_mapping(dataset_id: str, payload: FieldMappingCreate) -> FieldMapping:
    dataset = find_dataset(dataset_id)
    field_names = dataset_field_names(dataset)
    configured_fields = set(payload.primary_key_fields + payload.sub_key_fields + payload.sensitive_fields)
    configured_fields.update(value for value in payload.group_fields.values() if value)
    invalid_fields = sorted(field for field in configured_fields if field not in field_names)
    if invalid_fields:
        raise HTTPException(status_code=400, detail={"invalid_fields": invalid_fields})

    mapping = FieldMapping(
        dataset_id=dataset_id,
        primary_key_fields=payload.primary_key_fields,
        sub_key_fields=payload.sub_key_fields,
        sensitive_fields=payload.sensitive_fields,
        group_fields={key: value for key, value in payload.group_fields.items() if value},
        updated_at=utc_now(),
    )

    mappings = [item for item in load_state()["field_mappings"] if item["dataset_id"] != dataset_id]
    mappings.append(mapping.model_dump())
    replace_collection("field_mappings", mappings)
    write_audit(
        action="field_mapping.save",
        object_type="dataset",
        object_id=dataset_id,
        summary=f"保存字段映射：{dataset.source_filename}",
        metadata={
            "primary_key_fields": mapping.primary_key_fields,
            "sub_key_fields": mapping.sub_key_fields,
            "sensitive_fields_count": len(mapping.sensitive_fields),
            "group_fields": mapping.group_fields,
        },
    )
    return mapping


@app.get("/api/rule-templates", response_model=list[RuleTemplate])
def list_rule_templates() -> list[RuleTemplate]:
    return [RuleTemplate(**item) for item in load_state().get("rule_templates", [])]


@app.post("/api/rule-templates", response_model=RuleTemplate)
def create_rule_template_endpoint(payload: RuleTemplateCreate) -> RuleTemplate:
    template = create_rule_template(payload)
    add_record("rule_templates", template.model_dump())
    write_audit(
        action="rule_template.create",
        object_type="rule_template",
        object_id=template.id,
        summary=f"创建规则模板：{template.name}",
        metadata={"created_by": template.created_by, "rules_count": template.rules_count},
    )
    return template


@app.get("/api/rule-snippets", response_model=list[RuleSnippet])
def list_rule_snippets() -> list[RuleSnippet]:
    return [RuleSnippet(**item) for item in load_state().get("rule_snippets", [])]


@app.post("/api/rule-snippets", response_model=RuleSnippet)
def create_rule_snippet_endpoint(payload: RuleSnippetCreate) -> RuleSnippet:
    snippet = create_rule_snippet(payload)
    add_record("rule_snippets", snippet.model_dump())
    write_audit(
        action="rule_snippet.create",
        object_type="rule_snippet",
        object_id=snippet.id,
        summary=f"创建规则条目：{snippet.name}",
        metadata={"created_by": snippet.created_by},
    )
    return snippet


@app.get("/api/rule-packages", response_model=list[RulePackage])
def list_rule_packages() -> list[RulePackage]:
    return [RulePackage(**item) for item in load_state()["rule_packages"]]


@app.get("/api/rule-signers", response_model=list[TrustedSignerInfo])
def list_rule_signers() -> list[TrustedSignerInfo]:
    return list_trusted_signers()


@app.post("/api/rule-packages", response_model=RulePackage)
def create_rule_package(payload: RulePackageCreate) -> RulePackage:
    package = RulePackage(
        id=str(uuid4()),
        name=payload.name,
        version=payload.version,
        purpose=payload.purpose,
        signer_name=payload.signer_name,
        signature_ref=payload.signature_ref,
        signature=payload.signature,
        rules=payload.rules,
        rules_count=len(payload.rules),
        created_at=utc_now(),
        notes=payload.notes,
    )
    package = apply_rule_package_verification(package)
    add_record("rule_packages", package.model_dump())
    write_audit(
        action="rule_package.import",
        object_type="rule_package",
        object_id=package.id,
        summary=f"导入待审批规则包：{package.name}",
        metadata={
            "version": package.version,
            "rules_count": package.rules_count,
            "signer_name": package.signer_name,
            "signature_ref": package.signature_ref,
            "status": package.status,
            "verification_status": package.verification_status,
        },
    )
    return package


@app.post("/api/rule-packages/{package_id}/verify", response_model=RulePackage)
def verify_rule_package(package_id: str) -> RulePackage:
    packages = [RulePackage(**item) for item in load_state()["rule_packages"]]
    target: RulePackage | None = None
    updated: list[dict[str, object]] = []

    for package in packages:
        if package.id == package_id:
            package = apply_rule_package_verification(package)
            target = package
        updated.append(package.model_dump())

    if target is None:
        raise HTTPException(status_code=404, detail="Rule package not found")

    replace_collection("rule_packages", updated)
    write_audit(
        action="rule_package.verify",
        object_type="rule_package",
        object_id=target.id,
        summary=f"执行规则包签名验签：{target.name}",
        metadata={
            "signer_name": target.signer_name,
            "signature_ref": target.signature_ref,
            "verification_status": target.verification_status,
        },
    )
    return target


@app.post("/api/rule-packages/batch-verify", response_model=list[RulePackageBatchResult])
def batch_verify_rule_packages(payload: RulePackageBatchAction) -> list[RulePackageBatchResult]:
    packages = [RulePackage(**item) for item in load_state()["rule_packages"]]
    package_ids = set(payload.package_ids)
    results: list[RulePackageBatchResult] = []
    updated: list[dict[str, object]] = []

    for package in packages:
        if package.id in package_ids:
            package = apply_rule_package_verification(package)
            results.append(
                RulePackageBatchResult(
                    package_id=package.id,
                    name=package.name,
                    success=package.verification_status == "verified",
                    status=package.verification_status,
                    message=package.verification_message or package.verification_status,
                )
            )
        updated.append(package.model_dump())

    replace_collection("rule_packages", updated)
    write_audit(
        action="rule_package.batch_verify",
        object_type="rule_package",
        summary=f"批量执行规则包验签，共 {len(results)} 个",
        metadata={"package_ids": payload.package_ids},
    )
    return results


@app.post("/api/rule-packages/{package_id}/approve", response_model=RulePackage)
def approve_rule_package(package_id: str, payload: RulePackageApprove) -> RulePackage:
    if not payload.approver_name.strip():
        raise HTTPException(status_code=400, detail="审批人不能为空")

    packages = [RulePackage(**item) for item in load_state()["rule_packages"]]
    target: RulePackage | None = None
    updated: list[dict[str, object]] = []

    for package in packages:
        if package.id == package_id:
            if package.verification_status != "verified":
                raise HTTPException(status_code=400, detail="规则包尚未通过本域签名验签")
            package.status = "approved"
            package.approved_by = payload.approver_name
            package.approved_at = utc_now()
            target = package
        updated.append(package.model_dump())

    if target is None:
        raise HTTPException(status_code=404, detail="Rule package not found")

    replace_collection("rule_packages", updated)
    write_audit(
        action="rule_package.approve",
        object_type="rule_package",
        object_id=target.id,
        summary=f"审批通过规则包：{target.name}",
        metadata={"approver_name": payload.approver_name, "comment": payload.comment},
    )
    return target


@app.post("/api/rule-packages/batch-approve", response_model=list[RulePackageBatchResult])
def batch_approve_rule_packages(payload: RulePackageBatchAction) -> list[RulePackageBatchResult]:
    if not payload.approver_name or not payload.approver_name.strip():
        raise HTTPException(status_code=400, detail="审批人不能为空")

    packages = [RulePackage(**item) for item in load_state()["rule_packages"]]
    package_ids = set(payload.package_ids)
    results: list[RulePackageBatchResult] = []
    updated: list[dict[str, object]] = []

    for package in packages:
        if package.id in package_ids:
            if package.verification_status != "verified":
                results.append(
                    RulePackageBatchResult(
                        package_id=package.id,
                        name=package.name,
                        success=False,
                        status=package.status,
                        message="规则包尚未通过本域签名验签",
                    )
                )
            else:
                package.status = "approved"
                package.approved_by = payload.approver_name
                package.approved_at = utc_now()
                results.append(
                    RulePackageBatchResult(
                        package_id=package.id,
                        name=package.name,
                        success=True,
                        status=package.status,
                        message="审批通过",
                    )
                )
        updated.append(package.model_dump())

    replace_collection("rule_packages", updated)
    write_audit(
        action="rule_package.batch_approve",
        object_type="rule_package",
        summary=f"批量审批规则包，共 {len(results)} 个",
        metadata={"package_ids": payload.package_ids, "approver_name": payload.approver_name},
    )
    return results


def load_rule_package_center_state() -> tuple[list[RulePackage], list[RulePackageRevision]]:
    state = load_state()
    packages = [RulePackage(**item) for item in state["rule_packages"]]
    revisions = [RulePackageRevision(**item) for item in state.get("rule_package_revisions", [])]
    return packages, revisions


def save_rule_package_center_state(packages: list[RulePackage], revisions: list[RulePackageRevision]) -> None:
    replace_collection("rule_packages", [item.model_dump() for item in packages])
    replace_collection("rule_package_revisions", [item.model_dump() for item in revisions])


def find_rule_package_center_package(packages: list[RulePackage], package_id: str) -> RulePackage:
    package = next((item for item in packages if item.id == package_id and item.status != "deleted"), None)
    if package is None:
        raise HTTPException(status_code=404, detail="Rule package not found")
    return package


@app.get("/api/rule-package-center/packages", response_model=list[RulePackage])
def list_rule_package_center_packages() -> list[RulePackage]:
    packages, _ = load_rule_package_center_state()
    return [item for item in packages if item.status != "deleted"]


@app.post("/api/rule-package-center/packages", response_model=RulePackage)
def create_rule_package_center_package(payload: RulePackageCreate) -> RulePackage:
    package, revision = create_rule_package_entities(payload)
    add_record("rule_packages", package.model_dump())
    add_record("rule_package_revisions", revision.model_dump())
    write_audit(
        action="rule_package.create",
        object_type="rule_package",
        object_id=package.id,
        summary=f"创建规则包草稿：{package.name}",
        metadata={
            "version": package.version,
            "rules_count": package.rules_count,
            "editor_name": payload.editor_name,
            "current_revision_id": package.current_revision_id,
        },
    )
    return package


@app.get("/api/rule-package-center/packages/{package_id}", response_model=RulePackage)
def get_rule_package_center_package(package_id: str) -> RulePackage:
    packages, _ = load_rule_package_center_state()
    return find_rule_package_center_package(packages, package_id)


@app.get("/api/rule-package-center/packages/{package_id}/revisions", response_model=list[RulePackageRevision])
def list_rule_package_center_revisions(package_id: str) -> list[RulePackageRevision]:
    packages, revisions = load_rule_package_center_state()
    find_rule_package_center_package(packages, package_id)
    return sorted(
        [item for item in revisions if item.rule_package_id == package_id and item.status != "deleted"],
        key=lambda item: (item.revision_no, item.created_at),
    )


@app.get("/api/rule-package-center/packages/{package_id}/revision-diff", response_model=RulePackageRevisionDiff)
def get_rule_package_center_revision_diff(
    package_id: str,
    from_revision_id: str,
    to_revision_id: str,
) -> RulePackageRevisionDiff:
    packages, revisions = load_rule_package_center_state()
    package = find_rule_package_center_package(packages, package_id)
    package_revisions = {item.id: item for item in revisions if item.rule_package_id == package_id and item.status != "deleted"}
    from_revision = package_revisions.get(from_revision_id)
    to_revision = package_revisions.get(to_revision_id)
    if from_revision is None or to_revision is None:
        raise HTTPException(status_code=404, detail="Rule package revision not found")
    return compare_rule_package_revisions(package, from_revision, to_revision)


@app.get("/api/rule-package-center/packages/{package_id}/references", response_model=RulePackageUsageReport)
def get_rule_package_center_references(package_id: str) -> RulePackageUsageReport:
    state = load_state()
    packages = [RulePackage(**item) for item in state["rule_packages"]]
    revisions = [RulePackageRevision(**item) for item in state.get("rule_package_revisions", [])]
    package = find_rule_package_center_package(packages, package_id)
    return build_rule_package_usage_report(package, revisions, state["tasks"])


@app.post("/api/rule-package-center/packages/{package_id}/edit", response_model=RulePackageRevision)
def edit_rule_package_center_package(package_id: str, editor_name: str = "经办员A") -> RulePackageRevision:
    packages, revisions = load_rule_package_center_state()
    package = find_rule_package_center_package(packages, package_id)
    revision = editable_revision_for_package(package, revisions)
    if revision is not None:
        return revision

    revision = create_edit_revision(package, revisions, editor_name=editor_name)
    revisions.append(revision)
    materialize_package_from_revision(package, revision, package_status="draft")
    save_rule_package_center_state(packages, revisions)
    write_audit(
        action="rule_package.edit.start",
        object_type="rule_package",
        object_id=package.id,
        summary=f"基于已生效版本创建修订草稿：{package.name}",
        metadata={
            "editor_name": editor_name,
            "revision_id": revision.id,
            "based_on_revision_id": revision.based_on_revision_id,
        },
    )
    return revision


@app.post("/api/rule-package-center/packages/{package_id}/draft-save", response_model=RulePackageRevision)
def save_rule_package_center_draft(package_id: str, payload: RulePackageDraftSave) -> RulePackageRevision:
    packages, revisions = load_rule_package_center_state()
    package = find_rule_package_center_package(packages, package_id)
    revision = save_rule_package_revision(package, revisions, payload)
    revisions.append(revision)
    materialize_package_from_revision(package, revision, package_status="draft")
    save_rule_package_center_state(packages, revisions)
    write_audit(
        action="rule_package.draft_save",
        object_type="rule_package",
        object_id=package.id,
        summary=f"{'自动' if payload.auto_saved else '手动'}保存规则包草稿：{package.name}",
        metadata={
            "revision_id": revision.id,
            "revision_no": revision.revision_no,
            "editor_name": payload.editor_name,
            "auto_saved": payload.auto_saved,
            "rules_count": revision.rules_count,
        },
    )
    return revision


@app.post("/api/rule-package-center/packages/{package_id}/submit-verification", response_model=RulePackage)
def submit_rule_package_center_verification(package_id: str) -> RulePackage:
    packages, revisions = load_rule_package_center_state()
    package = find_rule_package_center_package(packages, package_id)
    revision = latest_revision(revisions, package.current_revision_id)
    if revision is None:
        raise HTTPException(status_code=404, detail="Rule package revision not found")
    revision = submit_revision_for_verification(revision)
    materialize_package_from_revision(package, revision)
    save_rule_package_center_state(packages, revisions)
    write_audit(
        action="rule_package.verify",
        object_type="rule_package",
        object_id=package.id,
        summary=f"执行规则包签名验签：{package.name}",
        metadata={
            "revision_id": revision.id,
            "signer_name": revision.signer_name,
            "signature_ref": revision.signature_ref,
            "verification_status": revision.verification_status,
        },
    )
    return package


@app.post("/api/rule-package-center/packages/{package_id}/approve", response_model=RulePackage)
def approve_rule_package_center_package(package_id: str, payload: RulePackageApprove) -> RulePackage:
    packages, revisions = load_rule_package_center_state()
    package = find_rule_package_center_package(packages, package_id)
    revision = latest_revision(revisions, package.current_revision_id)
    if revision is None:
        raise HTTPException(status_code=404, detail="Rule package revision not found")
    try:
        revision = approve_revision(revision, payload)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    materialize_package_from_revision(package, revision, package_status="approved")
    save_rule_package_center_state(packages, revisions)
    write_audit(
        action="rule_package.approve",
        object_type="rule_package",
        object_id=package.id,
        summary=f"审批通过规则包：{package.name}",
        metadata={
            "approver_name": payload.approver_name,
            "comment": payload.comment,
            "revision_id": revision.id,
        },
    )
    return package


@app.post("/api/rule-package-center/packages/{package_id}/deprecate", response_model=RulePackage)
def deprecate_rule_package_center_package(package_id: str, payload: RulePackageDeprecate) -> RulePackage:
    packages, revisions = load_rule_package_center_state()
    package = find_rule_package_center_package(packages, package_id)
    if package.status != "approved":
        raise HTTPException(status_code=400, detail="仅允许废弃已审批规则包")
    revision = latest_revision(revisions, package.current_revision_id)
    if revision is None:
        raise HTTPException(status_code=404, detail="Rule package revision not found")
    deprecate_package(package, revision, payload)
    save_rule_package_center_state(packages, revisions)
    write_audit(
        action="rule_package.deprecate",
        object_type="rule_package",
        object_id=package.id,
        summary=f"废弃规则包：{package.name}",
        metadata={"operator_name": payload.operator_name, "reason": payload.reason},
    )
    return package


@app.delete("/api/rule-package-center/packages/{package_id}")
def delete_rule_package_center_package(package_id: str) -> dict[str, str]:
    state = load_state()
    packages = [RulePackage(**item) for item in state["rule_packages"]]
    revisions = [RulePackageRevision(**item) for item in state.get("rule_package_revisions", [])]
    package = find_rule_package_center_package(packages, package_id)
    can_delete, reason = package_can_be_deleted(package, state["tasks"])
    if not can_delete:
        raise HTTPException(status_code=400, detail=reason)

    remaining_packages = [item for item in packages if item.id != package_id]
    remaining_revisions = [item for item in revisions if item.rule_package_id != package_id]
    save_rule_package_center_state(remaining_packages, remaining_revisions)
    write_audit(
        action="rule_package.delete",
        object_type="rule_package",
        object_id=package.id,
        summary=f"删除规则包草稿：{package.name}",
        metadata={"current_revision_id": package.current_revision_id},
    )
    return {"status": "deleted"}


@app.get("/api/tasks", response_model=list[Task])
def list_tasks() -> list[Task]:
    return [Task(**item) for item in load_state()["tasks"]]


@app.post("/api/tasks", response_model=Task)
def create_task(payload: TaskCreate) -> Task:
    state = load_state()
    dataset_ids = {item["id"] for item in state["datasets"]}
    missing_ids = [dataset_id for dataset_id in payload.dataset_ids if dataset_id not in dataset_ids]
    if missing_ids:
        raise HTTPException(status_code=400, detail={"missing_dataset_ids": missing_ids})

    resolved_rule_package_id = payload.rule_package_id
    resolved_rule_package_revision_id = payload.rule_package_revision_id
    if payload.rule_package_revision_id:
        revisions = {item["id"]: item for item in state.get("rule_package_revisions", [])}
        revision = revisions.get(payload.rule_package_revision_id)
        if revision is None:
            raise HTTPException(
                status_code=400,
                detail={"missing_rule_package_revision_id": payload.rule_package_revision_id},
            )
        if revision["status"] != "approved":
            raise HTTPException(status_code=400, detail={"rule_package_status": "规则包修订尚未审批通过"})
        resolved_rule_package_id = str(revision["rule_package_id"])
    elif payload.rule_package_id:
        packages = {item["id"]: item for item in state["rule_packages"]}
        if payload.rule_package_id not in packages:
            raise HTTPException(status_code=400, detail={"missing_rule_package_id": payload.rule_package_id})
        if packages[payload.rule_package_id]["status"] != "approved":
            raise HTTPException(status_code=400, detail={"rule_package_status": "规则包尚未审批通过"})
        resolved_rule_package_revision_id = packages[payload.rule_package_id].get("current_revision_id")

    if payload.output_policy == "aggregate_summary":
        threshold = payload.aggregate_threshold or AGGREGATE_MIN_THRESHOLD
        if threshold < AGGREGATE_MIN_THRESHOLD:
            raise HTTPException(
                status_code=400,
                detail={"aggregate_threshold": f"聚合统计阈值不能低于 {AGGREGATE_MIN_THRESHOLD}"},
            )
        if not payload.aggregate_group_by:
            raise HTTPException(status_code=400, detail={"aggregate_group_by": "聚合统计必须选择单一分组维度"})
        if payload.aggregate_group_by not in AGGREGATE_ALLOWED_DIMENSIONS:
            raise HTTPException(status_code=400, detail={"aggregate_group_by": "不允许的分组维度"})
    else:
        threshold = payload.aggregate_threshold

    task = Task(
        id=str(uuid4()),
        name=payload.name,
        dataset_ids=payload.dataset_ids,
        rule_package_id=resolved_rule_package_id,
        rule_package_revision_id=resolved_rule_package_revision_id,
        output_policy=payload.output_policy,
        aggregate_threshold=threshold,
        aggregate_group_by=payload.aggregate_group_by,
        description=payload.description,
        created_at=utc_now(),
    )
    add_record("tasks", task.model_dump())
    write_audit(
        action="task.create",
        object_type="task",
        object_id=task.id,
        summary=f"创建草稿任务：{task.name}",
        metadata={
            "dataset_ids": task.dataset_ids,
            "rule_package_id": task.rule_package_id,
            "rule_package_revision_id": task.rule_package_revision_id,
            "output_policy": task.output_policy,
            "aggregate_threshold": task.aggregate_threshold,
            "aggregate_group_by": task.aggregate_group_by,
        },
    )
    return task


@app.post("/api/tasks/{task_id}/execute", response_model=TaskResult)
def execute_task(task_id: str) -> TaskResult:
    state = load_state()
    task_items = state["tasks"]
    task_index = next((index for index, item in enumerate(task_items) if item["id"] == task_id), None)
    if task_index is None:
        raise HTTPException(status_code=404, detail="Task not found")

    task = Task(**task_items[task_index])
    if len(task.dataset_ids) != 1:
        raise HTTPException(status_code=400, detail="当前仅支持单数据集本域任务执行")

    dataset = find_dataset(task.dataset_ids[0])
    mapping = None
    for item in state["field_mappings"]:
        if item["dataset_id"] == dataset.id:
            mapping = FieldMapping(**item)
            break
    if mapping is None:
        raise HTTPException(status_code=400, detail="请先保存字段映射后再执行任务")

    try:
        package_rules: list[dict[str, object]] = []
        if task.rule_package_revision_id:
            revision_item = next(
                (item for item in state.get("rule_package_revisions", []) if item["id"] == task.rule_package_revision_id),
                None,
            )
            package_rules = revision_item.get("rules", []) if revision_item else []
        elif task.rule_package_id:
            package_item = next((item for item in state["rule_packages"] if item["id"] == task.rule_package_id), None)
            package_rules = package_item.get("rules", []) if package_item else []
        result = execute_local_task(task, dataset, mapping, package_rules)
        task.status = "completed"
    except ValueError as error:
        task.status = "failed"
        task_items[task_index] = task.model_dump()
        replace_collection("tasks", task_items)
        write_audit(
            action="task.execute.failed",
            object_type="task",
            object_id=task.id,
            summary=f"执行本域任务失败：{task.name}",
            metadata={"reason": str(error)},
        )
        raise HTTPException(status_code=400, detail=str(error)) from error

    task_items[task_index] = task.model_dump()
    replace_collection("tasks", task_items)
    results = [item for item in load_state()["results"] if item["task_id"] != task.id]
    results.append(result.model_dump())
    replace_collection("results", results)
    write_audit(
        action="task.execute",
        object_type="task",
        object_id=task.id,
        summary=f"执行本域任务：{task.name}",
        metadata={
            "rule_package_revision_id": task.rule_package_revision_id,
            "output_policy": task.output_policy,
            "row_count": result.summary.get("row_count"),
            "suppressed_groups": result.suppressed_groups,
        },
    )
    return result


@app.get("/api/results", response_model=list[TaskResult])
def list_results() -> list[TaskResult]:
    return [TaskResult(**item) for item in load_state()["results"]]


@app.get("/api/tasks/{task_id}/result", response_model=TaskResult)
def get_task_result(task_id: str) -> TaskResult:
    for item in load_state()["results"]:
        if item["task_id"] == task_id:
            return TaskResult(**item)
    raise HTTPException(status_code=404, detail="Task result not found")


def find_result(result_id: str) -> TaskResult:
    for item in load_state()["results"]:
        if item["id"] == result_id:
            return TaskResult(**item)
    raise HTTPException(status_code=404, detail="Task result not found")


def save_result(updated_result: TaskResult) -> None:
    results = [item for item in load_state()["results"] if item["task_id"] != updated_result.task_id]
    results.append(updated_result.model_dump())
    replace_collection("results", results)


def find_export_request(request_id: str) -> ExportRequest:
    for item in load_state()["export_requests"]:
        if item["id"] == request_id:
            return ExportRequest(**item)
    raise HTTPException(status_code=404, detail="Export request not found")


def find_export_files(file_ids: list[str]) -> list[ExportFile]:
    if not file_ids:
        raise HTTPException(status_code=400, detail="请选择需要归档的输出文件")
    files = [ExportFile(**item) for item in load_state()["export_files"]]
    file_map = {item.id: item for item in files}
    missing_ids = [item for item in file_ids if item not in file_map]
    if missing_ids:
        raise HTTPException(status_code=404, detail={"missing_export_file_ids": missing_ids})
    return [file_map[item] for item in file_ids]


@app.get("/api/export-requests", response_model=list[ExportRequest])
def list_export_requests() -> list[ExportRequest]:
    return [ExportRequest(**item) for item in load_state()["export_requests"]]


@app.get("/api/export-files", response_model=list[ExportFile])
def list_export_files() -> list[ExportFile]:
    return [ExportFile(**item) for item in load_state()["export_files"]]


@app.get("/api/export-archives", response_model=list[ExportArchive])
def list_export_archives() -> list[ExportArchive]:
    return [ExportArchive(**item) for item in load_state()["export_archives"]]


@app.post("/api/export-requests", response_model=ExportRequest)
def request_export(payload: ExportRequestCreate) -> ExportRequest:
    result = find_result(payload.result_id)
    if payload.export_type == "assertion":
        if result.assertion is None:
            raise HTTPException(status_code=400, detail="该结果没有可输出的结论声明")
        if result.assertion.status != "approved":
            raise HTTPException(status_code=400, detail="结论声明尚未正式审核通过")
    export_request = create_export_request(payload)
    add_record("export_requests", export_request.model_dump())
    write_audit(
        action="export.request",
        object_type="export_request",
        object_id=export_request.id,
        summary=f"创建安全输出申请：{export_request.export_type}",
        metadata={
            "result_id": export_request.result_id,
            "requester_name": export_request.requester_name,
            "export_type": export_request.export_type,
        },
    )
    return export_request


@app.post("/api/export-requests/{request_id}/approve", response_model=ExportRequest)
def approve_export(request_id: str, payload: ExportRequestApprove) -> ExportRequest:
    requests = [ExportRequest(**item) for item in load_state()["export_requests"]]
    target: ExportRequest | None = None
    updated: list[dict[str, object]] = []

    for export_request in requests:
        if export_request.id == request_id:
            try:
                export_request = approve_export_request(export_request, payload.approver_name)
            except ValueError as error:
                raise HTTPException(status_code=400, detail=str(error)) from error
            target = export_request
        updated.append(export_request.model_dump())

    if target is None:
        raise HTTPException(status_code=404, detail="Export request not found")

    replace_collection("export_requests", updated)
    write_audit(
        action="export.approve",
        object_type="export_request",
        object_id=target.id,
        summary=f"审批通过安全输出申请：{target.export_type}",
        metadata={"approver_name": payload.approver_name, "comment": payload.comment},
    )
    return target


@app.get("/api/export-requests/{request_id}/package", response_model=ExportPackage)
def get_export_package(request_id: str) -> ExportPackage:
    target = find_export_request(request_id)
    result = find_result(target.result_id)
    try:
        package = build_export_package(target, result)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    write_audit(
        action="export.package.generate",
        object_type="export_request",
        object_id=target.id,
        summary=f"生成安全输出包：{target.export_type}",
        metadata={"result_id": target.result_id, "export_type": target.export_type},
    )
    return package


@app.post("/api/export-requests/{request_id}/file", response_model=ExportFile)
def persist_export_file(request_id: str) -> ExportFile:
    target = find_export_request(request_id)
    result = find_result(target.result_id)
    try:
        package = build_export_package(target, result)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    export_file = persist_export_package(package)
    add_record("export_files", export_file.model_dump())
    write_audit(
        action="export.file.persist",
        object_type="export_file",
        object_id=export_file.id,
        summary=f"安全输出包写入本域文件：{export_file.file_name}",
        metadata={
            "request_id": export_file.request_id,
            "result_id": export_file.result_id,
            "export_type": export_file.export_type,
            "sha256": export_file.sha256,
            "byte_size": export_file.byte_size,
        },
    )
    return export_file


@app.post("/api/export-archives", response_model=ExportArchive)
def create_export_archive(payload: ExportArchiveCreate) -> ExportArchive:
    export_files = find_export_files(payload.export_file_ids)
    try:
        archive = archive_export_files(payload, export_files)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    add_record("export_archives", archive.model_dump())
    write_audit(
        action="export.archive.create",
        object_type="export_archive",
        object_id=archive.id,
        summary=f"创建输出文件归档封存：{archive.file_count} 个文件",
        metadata={
            "export_file_ids": archive.export_file_ids,
            "archived_by": archive.archived_by,
            "signer_key_ref": archive.signer_key_ref,
        },
    )
    return archive


@app.get("/api/export-archives/{archive_id}/verify", response_model=ExportArchive)
def verify_export_archive_endpoint(archive_id: str) -> ExportArchive:
    archives = [ExportArchive(**item) for item in load_state()["export_archives"]]
    signer = load_archive_signer()
    target: ExportArchive | None = None
    updated: list[dict[str, object]] = []

    for archive in archives:
        if archive.id == archive_id:
            archive.verification = verify_archive_report(
                archive.manifest_path,
                archive.signature_path,
                signer["public_key_path"],
            )
            target = archive
        updated.append(archive.model_dump())

    if target is None:
        raise HTTPException(status_code=404, detail="Export archive not found")

    replace_collection("export_archives", updated)
    write_audit(
        action="export.archive.verify",
        object_type="export_archive",
        object_id=target.id,
        summary=f"校验输出文件归档封存：{target.id}",
        metadata={"valid": target.verification.valid, "manifest_hash": target.verification.manifest_hash},
    )
    return target


@app.get("/api/operators", response_model=list[OperatorInfo])
def operators() -> list[OperatorInfo]:
    return list_operators()


@app.get("/api/governance/dashboard", response_model=GovernanceDashboard)
def governance_dashboard() -> GovernanceDashboard:
    return build_governance_dashboard(load_state())


@app.post("/api/results/{result_id}/assertion/review", response_model=TaskResult)
def review_result_assertion(result_id: str, payload: AssertionReviewRequest) -> TaskResult:
    result = find_result(result_id)
    try:
        updated_result = review_assertion(result, payload)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    save_result(updated_result)
    write_audit(
        action="assertion.review",
        object_type="result",
        object_id=updated_result.id,
        summary=f"完成结论声明审核：{payload.decision}",
        metadata={
            "task_id": updated_result.task_id,
            "reviewer_name": payload.reviewer_name,
            "decision": payload.decision,
        },
    )
    return updated_result


@app.get("/api/audit", response_model=list[AuditEntry])
def list_audit() -> list[AuditEntry]:
    return [AuditEntry(**item) for item in load_state()["audit"]]


@app.get("/api/audit/verify", response_model=AuditChainVerification)
def verify_audit() -> AuditChainVerification:
    return verify_audit_chain()
