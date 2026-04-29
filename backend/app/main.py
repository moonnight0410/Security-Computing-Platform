from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import IMPORTS_DIR, WORKSPACE_ROOT, ensure_workspace
from app.models.schemas import (
    AuditEntry,
    Dataset,
    DomainPolicy,
    AuditChainVerification,
    ExportFile,
    ExportPackage,
    ExportRequest,
    ExportRequestApprove,
    ExportRequestCreate,
    FieldMapping,
    FieldMappingCreate,
    HealthResponse,
    OperatorInfo,
    RulePackage,
    RulePackageApprove,
    RulePackageCreate,
    Task,
    TaskCreate,
    TaskResult,
)
from app.services.audit import utc_now, verify_audit_chain, write_audit
from app.services.app_logging import configure_logging, get_logger
from app.services.execution import execute_local_task
from app.services.exports import approve_export_request, build_export_package, create_export_request, persist_export_package
from app.services.operators import list_operators
from app.services.profiling import profile_csv
from app.services.storage import add_record, load_state, replace_collection

ensure_workspace()
configure_logging()
logger = get_logger(__name__)

AGGREGATE_MIN_THRESHOLD = 10
AGGREGATE_ALLOWED_DIMENSIONS = {"department", "matter_type", "month"}
ALLOWED_UPLOAD_SUFFIXES = {".csv", ".xlsx", ".xls"}

app = FastAPI(
    title="政府部门联查数据计算单机系统",
    version="0.6.0-stage6-domain-local",
    description="Stage 6 API with controlled export persistence and audit-chain verification.",
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
        assertion_approval_policy="执行人与审核人分离，结论声明需审核人批准后方可输出",
        rule_package_import_policy="规则包必须带签名引用，并经单名审批人批准后才能用于任务",
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


@app.get("/api/rule-packages", response_model=list[RulePackage])
def list_rule_packages() -> list[RulePackage]:
    return [RulePackage(**item) for item in load_state()["rule_packages"]]


@app.post("/api/rule-packages", response_model=RulePackage)
def create_rule_package(payload: RulePackageCreate) -> RulePackage:
    package = RulePackage(
        id=str(uuid4()),
        name=payload.name,
        version=payload.version,
        purpose=payload.purpose,
        signature_ref=payload.signature_ref,
        rules=payload.rules,
        rules_count=len(payload.rules),
        created_at=utc_now(),
        notes=payload.notes,
    )
    add_record("rule_packages", package.model_dump())
    write_audit(
        action="rule_package.import",
        object_type="rule_package",
        object_id=package.id,
        summary=f"导入待审批规则包：{package.name}",
        metadata={
            "version": package.version,
            "rules_count": package.rules_count,
            "signature_ref": package.signature_ref,
            "status": package.status,
        },
    )
    return package


@app.post("/api/rule-packages/{package_id}/approve", response_model=RulePackage)
def approve_rule_package(package_id: str, payload: RulePackageApprove) -> RulePackage:
    if not payload.approver_name.strip():
        raise HTTPException(status_code=400, detail="审批人不能为空")

    packages = [RulePackage(**item) for item in load_state()["rule_packages"]]
    target: RulePackage | None = None
    updated: list[dict[str, object]] = []

    for package in packages:
        if package.id == package_id:
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

    if payload.rule_package_id:
        packages = {item["id"]: item for item in state["rule_packages"]}
        if payload.rule_package_id not in packages:
            raise HTTPException(status_code=400, detail={"missing_rule_package_id": payload.rule_package_id})
        if packages[payload.rule_package_id]["status"] != "approved":
            raise HTTPException(status_code=400, detail={"rule_package_status": "规则包尚未审批通过"})

    if payload.output_policy == "aggregate_summary":
        threshold = payload.aggregate_threshold or AGGREGATE_MIN_THRESHOLD
        if threshold < AGGREGATE_MIN_THRESHOLD:
            raise HTTPException(
                status_code=400,
                detail={
                    "aggregate_threshold": (
                        f"聚合统计阈值不能低于 {AGGREGATE_MIN_THRESHOLD}"
                    )
                },
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
        rule_package_id=payload.rule_package_id,
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
        raise HTTPException(status_code=400, detail="Stage 2 当前仅支持单数据集本域任务执行")

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
        if task.rule_package_id:
            package_item = next(
                (item for item in load_state()["rule_packages"] if item["id"] == task.rule_package_id),
                None,
            )
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


def find_export_request(request_id: str) -> ExportRequest:
    for item in load_state()["export_requests"]:
        if item["id"] == request_id:
            return ExportRequest(**item)
    raise HTTPException(status_code=404, detail="Export request not found")


@app.get("/api/export-requests", response_model=list[ExportRequest])
def list_export_requests() -> list[ExportRequest]:
    return [ExportRequest(**item) for item in load_state()["export_requests"]]


@app.get("/api/export-files", response_model=list[ExportFile])
def list_export_files() -> list[ExportFile]:
    return [ExportFile(**item) for item in load_state()["export_files"]]


@app.post("/api/export-requests", response_model=ExportRequest)
def request_export(payload: ExportRequestCreate) -> ExportRequest:
    find_result(payload.result_id)
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


@app.get("/api/operators", response_model=list[OperatorInfo])
def operators() -> list[OperatorInfo]:
    return list_operators()


@app.get("/api/audit", response_model=list[AuditEntry])
def list_audit() -> list[AuditEntry]:
    return [AuditEntry(**item) for item in load_state()["audit"]]


@app.get("/api/audit/verify", response_model=AuditChainVerification)
def verify_audit() -> AuditChainVerification:
    return verify_audit_chain()
