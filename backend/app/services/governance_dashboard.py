from collections import Counter

from app.models.schemas import (
    ExportArchive,
    ExportFile,
    ExportRequest,
    GovernanceDashboard,
    RulePackage,
    Task,
    TaskResult,
)


def build_governance_dashboard(state: dict[str, list[dict[str, object]]]) -> GovernanceDashboard:
    tasks = [Task(**item) for item in state["tasks"]]
    results = [TaskResult(**item) for item in state["results"]]
    export_requests = [ExportRequest(**item) for item in state["export_requests"]]
    export_files = [ExportFile(**item) for item in state["export_files"]]
    export_archives = [ExportArchive(**item) for item in state["export_archives"]]
    rule_packages = [RulePackage(**item) for item in state["rule_packages"]]

    task_counts = Counter(task.status for task in tasks)
    output_counts = Counter(request.status for request in export_requests)
    rule_package_counts = Counter(package.status for package in rule_packages)
    pending_assertion_count = sum(1 for result in results if result.assertion and result.assertion.status == "pending_review")

    return GovernanceDashboard(
        task_counts=dict(task_counts),
        output_counts={
            **dict(output_counts),
            "files": len(export_files),
            "archives": len(export_archives),
        },
        rule_package_counts=dict(rule_package_counts),
        pending_assertion_count=pending_assertion_count,
        audit_total_entries=len(state["audit"]),
        recent_tasks=sorted(tasks, key=lambda item: item.created_at, reverse=True)[:6],
        recent_export_requests=sorted(export_requests, key=lambda item: item.requested_at, reverse=True)[:6],
        recent_export_files=sorted(export_files, key=lambda item: item.generated_at, reverse=True)[:6],
        recent_archives=sorted(export_archives, key=lambda item: item.archived_at, reverse=True)[:6],
    )
