import type { GovernanceDashboard } from "./types";

type Props = {
  dashboard: GovernanceDashboard | null;
};

function formatTime(value: string): string {
  return new Date(value).toLocaleString("zh-CN", { hour12: false });
}

function countOf(source: Record<string, number>, key: string): number {
  return source[key] ?? 0;
}

export default function GovernanceBoard({ dashboard }: Props) {
  if (!dashboard) {
    return (
      <article className="panel governance-board">
        <div className="panel__heading">
          <div>
            <p className="eyebrow">Governance</p>
            <h2>任务与输出治理看板</h2>
          </div>
        </div>
        <p className="empty">治理看板加载中。</p>
      </article>
    );
  }

  return (
    <article className="panel governance-board">
      <div className="panel__heading">
        <div>
          <p className="eyebrow">Governance</p>
          <h2>任务与输出治理看板</h2>
        </div>
      </div>

      <div className="governance-board__cards">
        <div className="metric">
          <span>任务总数</span>
          <strong>{countOf(dashboard.task_counts, "draft") + countOf(dashboard.task_counts, "completed") + countOf(dashboard.task_counts, "failed")}</strong>
          <small>草稿 {countOf(dashboard.task_counts, "draft")} / 完成 {countOf(dashboard.task_counts, "completed")} / 失败 {countOf(dashboard.task_counts, "failed")}</small>
        </div>
        <div className="metric">
          <span>输出申请</span>
          <strong>{countOf(dashboard.output_counts, "pending") + countOf(dashboard.output_counts, "approved") + countOf(dashboard.output_counts, "rejected")}</strong>
          <small>待审 {countOf(dashboard.output_counts, "pending")} / 已批 {countOf(dashboard.output_counts, "approved")}</small>
        </div>
        <div className="metric">
          <span>输出文件与归档</span>
          <strong>{countOf(dashboard.output_counts, "files")}</strong>
          <small>文件 {countOf(dashboard.output_counts, "files")} / 归档 {countOf(dashboard.output_counts, "archives")}</small>
        </div>
        <div className="metric">
          <span>规则包治理</span>
          <strong>{countOf(dashboard.rule_package_counts, "approved") + countOf(dashboard.rule_package_counts, "draft") + countOf(dashboard.rule_package_counts, "pending_review")}</strong>
          <small>已批 {countOf(dashboard.rule_package_counts, "approved")} / 待审 {countOf(dashboard.rule_package_counts, "pending_review")}</small>
        </div>
        <div className="metric">
          <span>待审核结论</span>
          <strong>{dashboard.pending_assertion_count}</strong>
          <small>需执行人与审核人分离</small>
        </div>
        <div className="metric">
          <span>审计记录</span>
          <strong>{dashboard.audit_total_entries}</strong>
          <small>全流程本地留痕</small>
        </div>
      </div>

      <div className="governance-board__streams">
        <div className="result-block">
          <strong>最近任务</strong>
          {dashboard.recent_tasks.length ? (
            dashboard.recent_tasks.map((task) => (
              <small key={task.id}>
                {task.name} / {task.status} / {task.output_policy} / {formatTime(task.created_at)}
              </small>
            ))
          ) : (
            <small>暂无任务记录。</small>
          )}
        </div>
        <div className="result-block">
          <strong>最近输出申请</strong>
          {dashboard.recent_export_requests.length ? (
            dashboard.recent_export_requests.map((request) => (
              <small key={request.id}>
                {request.export_type} / {request.status} / {request.requester_name} / {formatTime(request.requested_at)}
              </small>
            ))
          ) : (
            <small>暂无输出申请。</small>
          )}
        </div>
        <div className="result-block">
          <strong>最近输出文件</strong>
          {dashboard.recent_export_files.length ? (
            dashboard.recent_export_files.map((file) => (
              <small key={file.id}>
                {file.file_name} / {file.export_type} / {formatTime(file.generated_at)}
              </small>
            ))
          ) : (
            <small>暂无输出文件。</small>
          )}
        </div>
        <div className="result-block">
          <strong>最近归档封存</strong>
          {dashboard.recent_archives.length ? (
            dashboard.recent_archives.map((archive) => (
              <small key={archive.id}>
                {archive.id} / {archive.file_count} 文件 / {archive.verification.valid ? "验签通过" : "待复核"} / {formatTime(archive.archived_at)}
              </small>
            ))
          ) : (
            <small>暂无归档记录。</small>
          )}
        </div>
      </div>
    </article>
  );
}
