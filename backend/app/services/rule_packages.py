import hashlib
import json
from copy import deepcopy
from typing import Any
from uuid import uuid4

from app.models.schemas import (
    RulePackage,
    RulePackageApprove,
    RulePackageCreate,
    RulePackageDiffFieldChange,
    RulePackageDiffRuleChange,
    RulePackageDeprecate,
    RulePackageDraftSave,
    RulePackageRevision,
    RulePackageRevisionDiff,
    RulePackageRevisionReferenceSummary,
    RulePackageTaskReference,
    RulePackageUsageReport,
)
from app.services.audit import utc_now
from app.services.rule_logic import comparable_rule_value, count_rule_items, flatten_rule_descriptors
from app.services.rule_signatures import apply_rule_package_verification


NON_EDITABLE_PACKAGE_STATUSES = {"approved", "deprecated", "deleted"}


def content_hash_from_payload(payload: RulePackageCreate | RulePackageDraftSave) -> str:
    serialized = json.dumps(
        {
            "name": payload.name,
            "version": payload.version,
            "purpose": payload.purpose,
            "signer_name": payload.signer_name,
            "signature_ref": payload.signature_ref,
            "signature": payload.signature,
            "rules": payload.rules,
            "notes": payload.notes,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def create_rule_package_entities(payload: RulePackageCreate) -> tuple[RulePackage, RulePackageRevision]:
    now = utc_now()
    package_id = str(uuid4())
    revision_id = str(uuid4())
    hashed = content_hash_from_payload(payload)
    revision = RulePackageRevision(
        id=revision_id,
        rule_package_id=package_id,
        revision_no=1,
        name=payload.name,
        version=payload.version,
        purpose=payload.purpose,
        signer_name=payload.signer_name,
        signature_ref=payload.signature_ref,
        signature=payload.signature,
        rules=deepcopy(payload.rules),
        rules_count=count_rule_items(payload.rules),
        status="draft",
        verification_status="not_signed",
        notes=payload.notes,
        change_summary=payload.change_summary or "创建首版草稿",
        editor_name=payload.editor_name,
        saved_by_auto=False,
        signature_outdated=not bool(payload.signature),
        based_on_revision_id=None,
        content_hash=hashed,
        created_at=now,
    )
    package = RulePackage(
        id=package_id,
        name=payload.name,
        version=payload.version,
        purpose=payload.purpose,
        signer_name=payload.signer_name,
        signature_ref=payload.signature_ref,
        signature=payload.signature,
        rules=deepcopy(payload.rules),
        rules_count=count_rule_items(payload.rules),
        status="draft",
        verification_status="not_signed",
        created_at=now,
        updated_at=now,
        current_revision_id=revision_id,
        current_revision_no=1,
        latest_editor_name=payload.editor_name,
        latest_edited_at=now,
        signature_outdated=not bool(payload.signature),
        notes=payload.notes,
    )
    return package, revision


def next_revision_number(revisions: list[RulePackageRevision], package_id: str) -> int:
    current = [item.revision_no for item in revisions if item.rule_package_id == package_id]
    return (max(current) if current else 0) + 1


def latest_revision(revisions: list[RulePackageRevision], revision_id: str | None) -> RulePackageRevision | None:
    if not revision_id:
        return None
    return next((item for item in revisions if item.id == revision_id), None)


def materialize_package_from_revision(
    package: RulePackage,
    revision: RulePackageRevision,
    *,
    package_status: str | None = None,
) -> RulePackage:
    package.name = revision.name
    package.version = revision.version
    package.purpose = revision.purpose
    package.signer_name = revision.signer_name
    package.signature_ref = revision.signature_ref
    package.signature = revision.signature
    package.rules = deepcopy(revision.rules)
    package.rules_count = revision.rules_count
    package.verification_status = revision.verification_status
    package.verification_message = revision.verification_message
    package.verified_at = revision.verified_at
    package.approved_by = revision.approved_by
    package.approved_at = revision.approved_at
    package.notes = revision.notes
    package.current_revision_id = revision.id
    package.current_revision_no = revision.revision_no
    package.latest_editor_name = revision.editor_name
    package.latest_edited_at = revision.created_at
    package.updated_at = revision.created_at
    package.signature_outdated = revision.signature_outdated
    if package_status is not None:
        package.status = package_status
    else:
        package.status = revision.status
    return package


def editable_revision_for_package(
    package: RulePackage,
    revisions: list[RulePackageRevision],
) -> RulePackageRevision | None:
    current = latest_revision(revisions, package.current_revision_id)
    if current is None:
        return None
    if package.status in NON_EDITABLE_PACKAGE_STATUSES:
        return None
    if current.status in NON_EDITABLE_PACKAGE_STATUSES:
        return None
    return current


def create_edit_revision(
    package: RulePackage,
    revisions: list[RulePackageRevision],
    *,
    editor_name: str,
) -> RulePackageRevision:
    current = latest_revision(revisions, package.current_revision_id)
    if current is None:
        raise ValueError("规则包当前修订不存在")
    revision_no = next_revision_number(revisions, package.id)
    now = utc_now()
    return RulePackageRevision(
        id=str(uuid4()),
        rule_package_id=package.id,
        revision_no=revision_no,
        name=current.name,
        version=current.version,
        purpose=current.purpose,
        signer_name=current.signer_name,
        signature_ref=current.signature_ref,
        signature="",
        rules=deepcopy(current.rules),
        rules_count=current.rules_count,
        status="draft",
        verification_status="not_signed",
        verification_message="内容派生为新修订草稿，需重新签名与验签",
        notes=current.notes,
        change_summary="基于已审批版本自动创建修订草稿",
        editor_name=editor_name,
        saved_by_auto=False,
        signature_outdated=True,
        based_on_revision_id=current.id,
        content_hash=current.content_hash,
        created_at=now,
    )


def save_rule_package_revision(
    package: RulePackage,
    revisions: list[RulePackageRevision],
    payload: RulePackageDraftSave,
) -> RulePackageRevision:
    current = latest_revision(revisions, package.current_revision_id)
    based_on_revision_id = current.id if current else None
    revision_no = next_revision_number(revisions, package.id)
    now = utc_now()
    revision = RulePackageRevision(
        id=str(uuid4()),
        rule_package_id=package.id,
        revision_no=revision_no,
        name=payload.name,
        version=payload.version,
        purpose=payload.purpose,
        signer_name=payload.signer_name,
        signature_ref=payload.signature_ref,
        signature=payload.signature,
        rules=deepcopy(payload.rules),
        rules_count=count_rule_items(payload.rules),
        status="draft",
        verification_status="not_signed",
        verification_message="草稿已保存，待重新签名或提交验签",
        notes=payload.notes,
        change_summary=payload.change_summary or ("离开页面自动保存" if payload.auto_saved else "保存草稿"),
        editor_name=payload.editor_name,
        saved_by_auto=payload.auto_saved,
        signature_outdated=True,
        based_on_revision_id=based_on_revision_id,
        content_hash=content_hash_from_payload(payload),
        created_at=now,
    )
    return revision


def submit_revision_for_verification(revision: RulePackageRevision) -> RulePackageRevision:
    verified = apply_rule_package_verification(revision)
    return verified  # type: ignore[return-value]


def approve_revision(revision: RulePackageRevision, payload: RulePackageApprove) -> RulePackageRevision:
    if revision.verification_status != "verified":
        raise ValueError("规则包尚未通过本域签名验签")
    revision.status = "approved"
    revision.approved_by = payload.approver_name
    revision.approved_at = utc_now()
    revision.signature_outdated = False
    return revision


def deprecate_package(package: RulePackage, revision: RulePackageRevision, payload: RulePackageDeprecate) -> None:
    timestamp = utc_now()
    package.status = "deprecated"
    package.deprecated_at = timestamp
    package.deprecated_by = payload.operator_name
    package.deprecation_reason = payload.reason
    package.updated_at = timestamp
    revision.status = "deprecated"


def package_can_be_deleted(package: RulePackage, tasks: list[dict[str, object]]) -> tuple[bool, str | None]:
    if package.status not in {"draft", "invalid"}:
        return False, "仅允许删除草稿或验签失败规则包"
    if package.approved_at:
        return False, "已审批规则包不可删除"
    referenced = any(
        task.get("rule_package_id") == package.id or task.get("rule_package_revision_id") == package.current_revision_id
        for task in tasks
    )
    if referenced:
        return False, "已被任务引用的规则包不可删除"
    return True, None


def comparable_revision_fields(revision: RulePackageRevision) -> dict[str, Any]:
    return {
        "name": revision.name,
        "version": revision.version,
        "purpose": revision.purpose,
        "signer_name": revision.signer_name,
        "signature_ref": revision.signature_ref,
        "notes": revision.notes,
        "change_summary": revision.change_summary,
        "status": revision.status,
        "verification_status": revision.verification_status,
        "rules_count": revision.rules_count,
        "signature_outdated": revision.signature_outdated,
    }


def compare_rule_package_revisions(
    package: RulePackage,
    from_revision: RulePackageRevision,
    to_revision: RulePackageRevision,
) -> RulePackageRevisionDiff:
    field_changes: list[RulePackageDiffFieldChange] = []
    from_fields = comparable_revision_fields(from_revision)
    to_fields = comparable_revision_fields(to_revision)
    for field_name in from_fields:
        if from_fields[field_name] != to_fields[field_name]:
            field_changes.append(
                RulePackageDiffFieldChange(
                    field=field_name,
                    before=from_fields[field_name],
                    after=to_fields[field_name],
                )
            )

    from_rules = {item["path"]: item for item in flatten_rule_descriptors(from_revision.rules)}
    to_rules = {item["path"]: item for item in flatten_rule_descriptors(to_revision.rules)}
    rule_changes: list[RulePackageDiffRuleChange] = []

    for key in sorted(set(from_rules) | set(to_rules)):
        before_rule = from_rules.get(key)
        after_rule = to_rules.get(key)
        if before_rule is None and after_rule is not None:
            rule_changes.append(
                RulePackageDiffRuleChange(
                    change_type="added",
                    rule_key=key,
                    field=str(after_rule.get("field", after_rule.get("node_type", ""))),
                    operator=str(after_rule.get("operator", after_rule.get("logic", ""))),
                    after_value=comparable_rule_value(after_rule.get("value") if after_rule.get("node_type") == "rule" else after_rule.get("logic")),
                )
            )
            continue
        if before_rule is not None and after_rule is None:
            rule_changes.append(
                RulePackageDiffRuleChange(
                    change_type="removed",
                    rule_key=key,
                    field=str(before_rule.get("field", before_rule.get("node_type", ""))),
                    operator=str(before_rule.get("operator", before_rule.get("logic", ""))),
                    before_value=comparable_rule_value(before_rule.get("value") if before_rule.get("node_type") == "rule" else before_rule.get("logic")),
                )
            )
            continue
        if before_rule is None or after_rule is None:
            continue
        comparable_before = comparable_rule_value(before_rule)
        comparable_after = comparable_rule_value(after_rule)
        if comparable_before != comparable_after:
            rule_changes.append(
                RulePackageDiffRuleChange(
                    change_type="modified",
                    rule_key=key,
                    field=str(after_rule.get("field", after_rule.get("node_type", ""))),
                    operator=str(after_rule.get("operator", after_rule.get("logic", ""))),
                    before_value=comparable_before,
                    after_value=comparable_after,
                )
            )

    based_on_match = to_revision.based_on_revision_id == from_revision.id
    return RulePackageRevisionDiff(
        package_id=package.id,
        package_name=package.name,
        from_revision_id=from_revision.id,
        from_revision_no=from_revision.revision_no,
        to_revision_id=to_revision.id,
        to_revision_no=to_revision.revision_no,
        based_on_match=based_on_match,
        field_changes=field_changes,
        rule_changes=rule_changes,
        summary={
            "field_change_count": len(field_changes),
            "rule_change_count": len(rule_changes),
            "added_rule_count": sum(1 for item in rule_changes if item.change_type == "added"),
            "removed_rule_count": sum(1 for item in rule_changes if item.change_type == "removed"),
            "modified_rule_count": sum(1 for item in rule_changes if item.change_type == "modified"),
            "based_on_match": based_on_match,
            "from_rules_count": from_revision.rules_count,
            "to_rules_count": to_revision.rules_count,
        },
    )


def build_rule_package_usage_report(
    package: RulePackage,
    revisions: list[RulePackageRevision],
    tasks: list[dict[str, object]],
) -> RulePackageUsageReport:
    package_revisions = [item for item in revisions if item.rule_package_id == package.id and item.status != "deleted"]
    revision_map = {item.id: item for item in package_revisions}
    revision_counts = {item.id: 0 for item in package_revisions}
    matched_tasks: list[RulePackageTaskReference] = []

    for task in tasks:
        task_revision_id = str(task.get("rule_package_revision_id") or "") or None
        task_package_id = str(task.get("rule_package_id") or "") or None
        if task_package_id != package.id and task_revision_id not in revision_map:
            continue

        revision = revision_map.get(task_revision_id or "")
        if revision is not None:
            revision_counts[revision.id] += 1

        matched_tasks.append(
            RulePackageTaskReference(
                task_id=str(task.get("id") or ""),
                task_name=str(task.get("name") or ""),
                task_status=str(task.get("status") or ""),
                created_at=str(task.get("created_at") or ""),
                output_policy=str(task.get("output_policy") or "local_only"),
                referenced_revision_id=revision.id if revision is not None else None,
                referenced_revision_no=revision.revision_no if revision is not None else None,
                referenced_revision_status=revision.status if revision is not None else None,
                is_current_revision=revision is not None and revision.id == package.current_revision_id,
            )
        )

    matched_tasks.sort(key=lambda item: (item.created_at, item.task_id), reverse=True)

    revision_summaries = sorted(
        [
            RulePackageRevisionReferenceSummary(
                revision_id=item.id,
                revision_no=item.revision_no,
                revision_status=item.status,
                is_current_revision=item.id == package.current_revision_id,
                task_count=revision_counts.get(item.id, 0),
            )
            for item in package_revisions
        ],
        key=lambda item: item.revision_no,
    )

    return RulePackageUsageReport(
        package_id=package.id,
        package_name=package.name,
        current_revision_id=package.current_revision_id,
        current_revision_no=package.current_revision_no,
        total_task_count=len(matched_tasks),
        current_revision_task_count=sum(1 for item in matched_tasks if item.is_current_revision),
        historical_revision_task_count=sum(
            1
            for item in matched_tasks
            if item.referenced_revision_id is not None and not item.is_current_revision
        ),
        revision_summaries=revision_summaries,
        tasks=matched_tasks,
    )
