import hashlib
import json
from uuid import uuid4

from app.core.config import EXPORTS_DIR, ensure_workspace
from app.models.schemas import ExportFile, ExportPackage, ExportRequest, ExportRequestCreate, TaskResult
from app.services.audit import utc_now


def create_export_request(payload: ExportRequestCreate) -> ExportRequest:
    return ExportRequest(
        id=str(uuid4()),
        result_id=payload.result_id,
        export_type=payload.export_type,
        requester_name=payload.requester_name,
        purpose=payload.purpose,
        requested_at=utc_now(),
    )


def approve_export_request(request: ExportRequest, approver_name: str) -> ExportRequest:
    if request.requester_name.strip() == approver_name.strip():
        raise ValueError("审批人与申请人不能相同")
    if request.status != "pending":
        raise ValueError("只能审批待审批的输出申请")
    request.status = "approved"
    request.approver_name = approver_name
    request.approved_at = utc_now()
    return request


def build_export_package(request: ExportRequest, result: TaskResult) -> ExportPackage:
    if request.status != "approved":
        raise ValueError("输出申请尚未审批通过")

    if request.export_type == "receipt":
        payload = {"receipt": result.receipt}
    elif request.export_type == "assertion":
        if not result.assertion:
            raise ValueError("该结果没有可输出的结论声明")
        payload = {"assertion": result.assertion}
    elif request.export_type == "aggregate_summary":
        if not result.aggregate_summary:
            raise ValueError("该结果没有满足阈值的聚合统计")
        payload = {
            "aggregate_summary": result.aggregate_summary,
            "suppressed_groups": result.suppressed_groups,
        }
    else:
        raise ValueError("不支持的输出类型")

    return ExportPackage(
        request_id=request.id,
        result_id=result.id,
        export_type=request.export_type,
        generated_at=utc_now(),
        payload=payload,
        safety_notes=[
            "输出包不包含原始数据。",
            "输出包不包含派生主键、子键或去标识摘要。",
            "输出包不包含对象级明细。",
        ],
    )


def persist_export_package(package: ExportPackage) -> ExportFile:
    ensure_workspace()
    export_file_id = str(uuid4())
    timestamp = utc_now().replace(":", "").replace(".", "")
    file_name = f"export-{package.export_type}-{package.request_id}-{timestamp}.json"
    stored_path = EXPORTS_DIR / file_name

    content = json.dumps(package.model_dump(), ensure_ascii=False, sort_keys=True, indent=2)
    encoded = content.encode("utf-8")
    stored_path.write_bytes(encoded)

    return ExportFile(
        id=export_file_id,
        request_id=package.request_id,
        result_id=package.result_id,
        export_type=package.export_type,
        stored_path=str(stored_path),
        file_name=file_name,
        sha256=hashlib.sha256(encoded).hexdigest(),
        byte_size=len(encoded),
        generated_at=utc_now(),
        safety_notes=[
            "文件仅写入本域受控 exports 目录。",
            "文件内容来自已审批安全输出包。",
            *package.safety_notes,
        ],
    )
