import { ChangeEvent, FormEvent, startTransition, useEffect, useState } from "react";

import {
  approveExportRequest,
  approveRulePackage,
  batchApproveRulePackages,
  batchVerifyRulePackages,
  createExportArchive,
  createExportRequest,
  createRulePackage,
  createTask,
  deleteTask,
  executeTask,
  getAudit,
  getDatasets,
  getDomainPolicy,
  getExportArchives,
  getExportFiles,
  getExportPackage,
  getExportRequests,
  getFieldMapping,
  getGovernanceDashboard,
  getHealth,
  getOperators,
  getResults,
  getRulePackages,
  getRuleSigners,
  getTasks,
  persistExportFile,
  reviewAssertion,
  saveFieldMapping,
  updateTask,
  uploadDataset,
  verifyAuditChain,
  verifyExportArchive,
  verifyRulePackage,
} from "./api";
import GovernanceBoard from "./GovernanceBoard";
import RulePackageCenter from "./RulePackageCenter";
import type {
  AuditChainVerification,
  AuditEntry,
  Dataset,
  DomainPolicy,
  ExportArchive,
  ExportFile,
  ExportPackage,
  ExportRequest,
  FieldMapping,
  GovernanceDashboard,
  HealthResponse,
  OperatorInfo,
  RulePackage,
  RulePackageBatchResult,
  Task,
  TaskResult,
  TrustedSignerInfo,
} from "./types";

type OutputPolicy = "local_only" | "execution_receipt" | "manual_assertion" | "aggregate_summary";
type AggregateGroupBy = "department" | "matter_type" | "month";
type ExportType = "receipt" | "assertion" | "aggregate_summary";

type ImportedRulePackage = {
  name: string;
  version: string;
  purpose: string;
  signer_name: string;
  signature_ref: string;
  signature: string;
  rules: Array<Record<string, unknown>>;
  notes?: string | null;
};

function formatTime(value?: string | null): string {
  if (!value) {
    return "-";
  }
  return new Date(value).toLocaleString("zh-CN", {
    hour12: false,
  });
}

function outputPolicyLabel(policy: OutputPolicy): string {
  if (policy === "execution_receipt") {
    return "执行回执";
  }
  if (policy === "manual_assertion") {
    return "结论声明";
  }
  if (policy === "aggregate_summary") {
    return "聚合统计";
  }
  return "仅本域留存";
}

function aggregateDimensionLabel(value?: AggregateGroupBy | null): string {
  if (value === "matter_type") {
    return "事项类型";
  }
  if (value === "month") {
    return "月份";
  }
  return "部门";
}

function normalizeImportedRulePackage(raw: unknown, defaultSigner?: TrustedSignerInfo): ImportedRulePackage {
  const source =
    raw && typeof raw === "object" && "package" in raw && raw.package && typeof raw.package === "object"
      ? (raw.package as Record<string, unknown>)
      : (raw as Record<string, unknown>);

  if (!source || typeof source !== "object") {
    throw new Error("规则包文件内容不是合法 JSON 对象。");
  }

  const rules = source.rules;
  if (!Array.isArray(rules)) {
    throw new Error("规则包文件缺少 rules 数组。");
  }

  const name = String(source.name ?? "").trim();
  const purpose = String(source.purpose ?? "").trim();
  if (!name || !purpose) {
    throw new Error("规则包文件缺少 name 或 purpose。");
  }

  return {
    name,
    version: String(source.version ?? "0.1.0").trim() || "0.1.0",
    purpose,
    signer_name: String(source.signer_name ?? defaultSigner?.signer_name ?? "").trim(),
    signature_ref: String(source.signature_ref ?? defaultSigner?.signature_ref ?? "").trim(),
    signature: String(source.signature ?? "").trim(),
    rules: rules as Array<Record<string, unknown>>,
    notes: source.notes ? String(source.notes) : undefined,
  };
}

function countRuleItems(rules: Array<Record<string, unknown>>): number {
  const countNode = (node: Record<string, unknown>): number => {
    if (node.type === "group" && Array.isArray(node.children)) {
      return node.children.reduce((total, child) => total + countNode(child as Record<string, unknown>), 0);
    }
    return 1;
  };
  return rules.reduce((total, rule) => total + countNode(rule), 0);
}

export default function App() {
  const [, setHealth] = useState<HealthResponse | null>(null);
  const [notice, setNotice] = useState("Stage 12：规则包导入登记与本域任务草稿完整工作面板。");
  const [domainPolicy, setDomainPolicy] = useState<DomainPolicy | null>(null);
  const [governanceDashboard, setGovernanceDashboard] = useState<GovernanceDashboard | null>(null);
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [fieldMapping, setFieldMapping] = useState<FieldMapping | null>(null);
  const [rulePackages, setRulePackages] = useState<RulePackage[]>([]);
  const [trustedSigners, setTrustedSigners] = useState<TrustedSignerInfo[]>([]);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [results, setResults] = useState<TaskResult[]>([]);
  const [exportRequests, setExportRequests] = useState<ExportRequest[]>([]);
  const [exportFiles, setExportFiles] = useState<ExportFile[]>([]);
  const [exportArchives, setExportArchives] = useState<ExportArchive[]>([]);
  const [exportPackage, setExportPackage] = useState<ExportPackage | null>(null);
  const [auditVerification, setAuditVerification] = useState<AuditChainVerification | null>(null);
  const [operators, setOperators] = useState<OperatorInfo[]>([]);
  const [audit, setAudit] = useState<AuditEntry[]>([]);
  const [selectedDatasetId, setSelectedDatasetId] = useState("");
  const [selectedRulePackageId, setSelectedRulePackageId] = useState("");
  const [selectedTaskId, setSelectedTaskId] = useState("");
  const [activeView, setActiveView] = useState<"workbench" | "rule-packages">("workbench");
  const [isPending, setIsPending] = useState(false);

  const [taskName, setTaskName] = useState("本域联查任务草稿");
  const [taskDescription, setTaskDescription] = useState("用于本域内规则联查与安全输出控制。");
  const [outputPolicy, setOutputPolicy] = useState<OutputPolicy>("local_only");
  const [aggregateThreshold, setAggregateThreshold] = useState(10);
  const [aggregateGroupBy, setAggregateGroupBy] = useState<AggregateGroupBy>("department");

  const [primaryField, setPrimaryField] = useState("");
  const [subField, setSubField] = useState("");
  const [sensitiveField, setSensitiveField] = useState("");
  const [departmentField, setDepartmentField] = useState("");
  const [matterTypeField, setMatterTypeField] = useState("");
  const [monthField, setMonthField] = useState("");

  const [approverName, setApproverName] = useState("规则审批人A");
  const [selectedRulePackageIds, setSelectedRulePackageIds] = useState<string[]>([]);
  const [batchMessage, setBatchMessage] = useState<RulePackageBatchResult[] | null>(null);
  const [rulePackageImportFileName, setRulePackageImportFileName] = useState("");
  const [rulePackageImportDraft, setRulePackageImportDraft] = useState<ImportedRulePackage | null>(null);

  const [exportType, setExportType] = useState<ExportType>("receipt");
  const [exportRequester, setExportRequester] = useState("经办人A");
  const [exportApprover, setExportApprover] = useState("审批人B");
  const [exportPurpose, setExportPurpose] = useState("事项办理结果反馈");
  const [selectedExportFileIds, setSelectedExportFileIds] = useState<string[]>([]);
  const [archiveOperator, setArchiveOperator] = useState("归档员A");
  const [archivePurpose, setArchivePurpose] = useState("归档封存与验签报告生成");

  const [assertionReviewer, setAssertionReviewer] = useState("审批人C");
  const [assertionFinalStatement, setAssertionFinalStatement] = useState("");
  const [assertionComment, setAssertionComment] = useState("");

  async function refresh() {
    const [
      nextHealth,
      nextPolicy,
      nextDashboard,
      nextDatasets,
      nextRulePackages,
      nextRuleSigners,
      nextTasks,
      nextResults,
      nextExportRequests,
      nextExportFiles,
      nextExportArchives,
      nextOperators,
      nextAudit,
    ] = await Promise.all([
      getHealth(),
      getDomainPolicy(),
      getGovernanceDashboard(),
      getDatasets(),
      getRulePackages(),
      getRuleSigners(),
      getTasks(),
      getResults(),
      getExportRequests(),
      getExportFiles(),
      getExportArchives(),
      getOperators(),
      getAudit(),
    ]);

    startTransition(() => {
      setHealth(nextHealth);
      setDomainPolicy(nextPolicy);
      setGovernanceDashboard(nextDashboard);
      setDatasets(nextDatasets);
      setRulePackages(nextRulePackages);
      setTrustedSigners(nextRuleSigners);
      setTasks(nextTasks);
      setResults(nextResults);
      setExportRequests(nextExportRequests);
      setExportFiles(nextExportFiles);
      setExportArchives(nextExportArchives);
      setOperators(nextOperators);
      setAudit(nextAudit);

      setSelectedDatasetId((current) => current || nextDatasets[0]?.id || "");
      setSelectedRulePackageId((current) => current || nextRulePackages.find((item) => item.status === "approved")?.id || "");
      setAggregateThreshold(nextPolicy.aggregate_min_threshold);
    });
  }

  useEffect(() => {
    refresh().catch((error: unknown) => {
      setNotice(error instanceof Error ? error.message : "无法连接本地后端服务。");
    });
  }, []);

  useEffect(() => {
    if (!selectedDatasetId) {
      setFieldMapping(null);
      return;
    }

    getFieldMapping(selectedDatasetId)
      .then((mapping) => {
        setFieldMapping(mapping);
        setPrimaryField(mapping.primary_key_fields[0] ?? "");
        setSubField(mapping.sub_key_fields[0] ?? "");
        setSensitiveField(mapping.sensitive_fields[0] ?? "");
        setDepartmentField(mapping.group_fields.department ?? "");
        setMatterTypeField(mapping.group_fields.matter_type ?? "");
        setMonthField(mapping.group_fields.month ?? "");
      })
      .catch((error: unknown) => {
        setNotice(error instanceof Error ? error.message : "字段映射加载失败。");
      });
  }, [selectedDatasetId]);

  function resetTaskDraftForm() {
    setSelectedTaskId("");
    setTaskName("本域联查任务草稿");
    setTaskDescription("用于本域内规则联查与安全输出控制。");
    setOutputPolicy("local_only");
    setAggregateGroupBy("department");
    setAggregateThreshold(domainPolicy?.aggregate_min_threshold ?? 10);
    setSelectedRulePackageId(rulePackages.find((item) => item.status === "approved")?.id ?? "");
  }

  function fillTaskDraftForm(task: Task) {
    setSelectedTaskId(task.id);
    setTaskName(task.name);
    setTaskDescription(task.description ?? "");
    setSelectedDatasetId(task.dataset_ids[0] ?? "");
    setSelectedRulePackageId(task.rule_package_id ?? "");
    setOutputPolicy(task.output_policy);
    setAggregateThreshold(task.aggregate_threshold ?? domainPolicy?.aggregate_min_threshold ?? 10);
    setAggregateGroupBy(task.aggregate_group_by ?? "department");
  }

  async function handleUpload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const input = form.elements.namedItem("dataset") as HTMLInputElement | null;
    const file = input?.files?.[0];
    if (!file) {
      setNotice("请选择需要导入到本域的数据文件。");
      return;
    }

    setIsPending(true);
    try {
      const dataset = await uploadDataset(file);
      await refresh();
      setSelectedDatasetId(dataset.id);
      setNotice(`已完成本域数据导入：${dataset.source_filename}。`);
      form.reset();
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "数据导入失败。");
    } finally {
      setIsPending(false);
    }
  }

  async function handleRulePackageFileChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) {
      setRulePackageImportDraft(null);
      setRulePackageImportFileName("");
      return;
    }

    setIsPending(true);
    try {
      const text = await file.text();
      const parsed = JSON.parse(text) as unknown;
      const normalized = normalizeImportedRulePackage(parsed, trustedSigners[0]);
      setRulePackageImportDraft(normalized);
      setRulePackageImportFileName(file.name);
      setNotice(`已完成规则包预检：${normalized.name}。`);
    } catch (error) {
      setRulePackageImportDraft(null);
      setRulePackageImportFileName(file.name);
      setNotice(error instanceof Error ? error.message : "规则包文件解析失败。");
    } finally {
      setIsPending(false);
    }
  }

  async function handleImportRulePackage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!rulePackageImportDraft) {
      setNotice("请先选择并通过预检的规则包文件。");
      return;
    }

    setIsPending(true);
    try {
      const created = await createRulePackage(rulePackageImportDraft);
      await refresh();
      setRulePackageImportDraft(null);
      setRulePackageImportFileName("");
      event.currentTarget.reset();
      setNotice(`已登记规则包：${created.name}，验签状态为 ${created.verification_status}。`);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "规则包登记失败。");
    } finally {
      setIsPending(false);
    }
  }

  async function handleSaveFieldMapping(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedDatasetId) {
      setNotice("请先选择本域数据集。");
      return;
    }

    setIsPending(true);
    try {
      const mapping = await saveFieldMapping(selectedDatasetId, {
        primary_key_fields: primaryField ? [primaryField] : [],
        sub_key_fields: subField ? [subField] : [],
        sensitive_fields: sensitiveField ? [sensitiveField] : [],
        group_fields: {
          department: departmentField,
          matter_type: matterTypeField,
          month: monthField,
        },
      });
      setFieldMapping(mapping);
      setNotice("字段映射已保存。");
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "字段映射保存失败。");
    } finally {
      setIsPending(false);
    }
  }

  function buildTaskPayload() {
    return {
      name: taskName,
      dataset_ids: selectedDatasetId ? [selectedDatasetId] : [],
      rule_package_id: selectedRulePackageId || null,
      rule_package_revision_id: null,
      output_policy: outputPolicy,
      aggregate_threshold: outputPolicy === "aggregate_summary" ? aggregateThreshold : undefined,
      aggregate_group_by: outputPolicy === "aggregate_summary" ? aggregateGroupBy : undefined,
      description: taskDescription || undefined,
    };
  }

  async function handleCreateTaskDraft(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsPending(true);
    try {
      const task = await createTask(buildTaskPayload());
      await refresh();
      fillTaskDraftForm(task);
      setNotice(`已创建本域任务草稿：${task.name}。`);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "创建任务草稿失败。");
    } finally {
      setIsPending(false);
    }
  }

  async function handleUpdateTaskDraft() {
    if (!selectedTaskId) {
      setNotice("请先选择需要编辑的任务草稿。");
      return;
    }

    setIsPending(true);
    try {
      const task = await updateTask(selectedTaskId, buildTaskPayload());
      await refresh();
      fillTaskDraftForm(task);
      setNotice(`已更新任务草稿：${task.name}。`);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "更新任务草稿失败。");
    } finally {
      setIsPending(false);
    }
  }

  async function handleSaveAsNewDraft() {
    setIsPending(true);
    try {
      const task = await createTask({
        ...buildTaskPayload(),
        name: selectedTaskId ? `${taskName}-副本` : taskName,
      });
      await refresh();
      fillTaskDraftForm(task);
      setNotice(`已另存为新任务草稿：${task.name}。`);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "另存任务草稿失败。");
    } finally {
      setIsPending(false);
    }
  }

  async function handleDeleteTaskDraft(taskId: string) {
    setIsPending(true);
    try {
      await deleteTask(taskId);
      await refresh();
      if (selectedTaskId === taskId) {
        resetTaskDraftForm();
      }
      setNotice("已删除任务草稿。");
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "删除任务草稿失败。");
    } finally {
      setIsPending(false);
    }
  }

  async function handleApproveRulePackage(rulePackageId: string) {
    setIsPending(true);
    try {
      const rulePackage = await approveRulePackage(rulePackageId, approverName);
      await refresh();
      setNotice(`规则包已审批通过：${rulePackage.name}。`);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "规则包审批失败。");
    } finally {
      setIsPending(false);
    }
  }

  async function handleVerifyRulePackage(rulePackageId: string) {
    setIsPending(true);
    try {
      const rulePackage = await verifyRulePackage(rulePackageId);
      await refresh();
      setNotice(`规则包验签结果：${rulePackage.verification_message ?? rulePackage.verification_status}。`);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "规则包验签失败。");
    } finally {
      setIsPending(false);
    }
  }

  async function handleBatchVerifyRulePackages() {
    if (!selectedRulePackageIds.length) {
      setNotice("请先选择需要批量验签的规则包。");
      return;
    }

    setIsPending(true);
    try {
      const nextResults = await batchVerifyRulePackages(selectedRulePackageIds);
      setBatchMessage(nextResults);
      await refresh();
      setNotice(`已完成 ${nextResults.length} 个规则包的批量验签。`);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "批量验签失败。");
    } finally {
      setIsPending(false);
    }
  }

  async function handleBatchApproveRulePackages() {
    if (!selectedRulePackageIds.length) {
      setNotice("请先选择需要批量审批的规则包。");
      return;
    }

    setIsPending(true);
    try {
      const nextResults = await batchApproveRulePackages(selectedRulePackageIds, approverName);
      setBatchMessage(nextResults);
      await refresh();
      setNotice(`已完成 ${nextResults.length} 个规则包的批量审批。`);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "批量审批失败。");
    } finally {
      setIsPending(false);
    }
  }

  async function handleExecuteTask(taskId: string) {
    setIsPending(true);
    try {
      const result = await executeTask(taskId);
      await refresh();
      setSelectedTaskId(taskId);
      setNotice(`任务执行完成，处理 ${String(result.summary.row_count ?? 0)} 行。`);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "任务执行失败。");
    } finally {
      setIsPending(false);
    }
  }

  async function handleCreateExportRequest(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!focusedResult) {
      setNotice("请先执行任务生成结果。");
      return;
    }

    setIsPending(true);
    try {
      const request = await createExportRequest(focusedResult.id, exportType, exportRequester, exportPurpose);
      await refresh();
      setNotice(`已创建输出申请：${request.export_type}。`);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "创建输出申请失败。");
    } finally {
      setIsPending(false);
    }
  }

  async function handleApproveExportRequest(requestId: string) {
    setIsPending(true);
    try {
      const request = await approveExportRequest(requestId, exportApprover);
      await refresh();
      setNotice(`已审批输出申请：${request.export_type}。`);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "审批输出申请失败。");
    } finally {
      setIsPending(false);
    }
  }

  async function handlePreviewExportPackage(requestId: string) {
    setIsPending(true);
    try {
      const nextPackage = await getExportPackage(requestId);
      setExportPackage(nextPackage);
      setNotice(`已生成输出包预览：${nextPackage.export_type}。`);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "输出包预览生成失败。");
    } finally {
      setIsPending(false);
    }
  }

  async function handlePersistExportFile(requestId: string) {
    setIsPending(true);
    try {
      const file = await persistExportFile(requestId);
      await refresh();
      setNotice(`已写入本域输出文件：${file.file_name}。`);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "输出包落盘失败。");
    } finally {
      setIsPending(false);
    }
  }

  async function handleCreateExportArchive() {
    if (!selectedExportFileIds.length) {
      setNotice("请先选择需要归档封存的输出文件。");
      return;
    }

    setIsPending(true);
    try {
      const archive = await createExportArchive(selectedExportFileIds, archiveOperator, archivePurpose);
      await refresh();
      setNotice(`已创建归档封存：${archive.id}。`);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "创建归档封存失败。");
    } finally {
      setIsPending(false);
    }
  }

  async function handleVerifyExportArchive(archiveId: string) {
    setIsPending(true);
    try {
      const archive = await verifyExportArchive(archiveId);
      await refresh();
      setNotice(archive.verification.valid ? `归档验签通过：${archive.id}。` : `归档验签失败：${archive.id}。`);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "归档验签失败。");
    } finally {
      setIsPending(false);
    }
  }

  async function handleVerifyAuditChain() {
    setIsPending(true);
    try {
      const result = await verifyAuditChain();
      setAuditVerification(result);
      setNotice(result.valid ? `审计链校验通过，已检查 ${result.checked_entries} 条记录。` : "审计链校验失败。");
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "审计链校验失败。");
    } finally {
      setIsPending(false);
    }
  }

  async function handleReviewAssertion(decision: "approved" | "rejected") {
    if (!focusedResult?.assertion) {
      setNotice("当前没有待审批的结论声明。");
      return;
    }

    setIsPending(true);
    try {
      const result = await reviewAssertion(
        focusedResult.id,
        assertionReviewer,
        decision,
        assertionFinalStatement || undefined,
        assertionComment || undefined,
      );
      await refresh();
      setNotice(`结论声明已${decision === "approved" ? "审批通过" : "驳回"}：${result.assertion?.status ?? "-"}`);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "结论声明审批失败。");
    } finally {
      setIsPending(false);
    }
  }

  const latestDataset = datasets.find((dataset) => dataset.id === selectedDatasetId) ?? datasets[0];
  const latestResult = results[results.length - 1];
  const focusedTask = tasks.find((task) => task.id === selectedTaskId) ?? null;
  const focusedResult = (focusedTask && results.find((item) => item.task_id === focusedTask.id)) ?? latestResult ?? null;
  const approvedRulePackages = rulePackages.filter((rulePackage) => rulePackage.status === "approved");
  const fieldNames = latestDataset?.fields.map((field) => field.name) ?? [];

  if (activeView === "rule-packages") {
    return (
      <main className="shell">
        <section className="workspace-topbar">
          <div>
            <p className="eyebrow">Rule Package Center</p>
            <h1>规则包编辑页</h1>
          </div>
          <button className="workspace-topbar__button" type="button" onClick={() => setActiveView("workbench")}>
            返回工作台
          </button>
        </section>
        <p className="notice">{notice}</p>
        <RulePackageCenter
          packages={rulePackages}
          signers={trustedSigners}
          isPendingGlobal={isPending}
          onNotice={setNotice}
          onRefresh={refresh}
        />
      </main>
    );
  }

  return (
    <main className="shell">
      <section className="workspace-topbar">
        <div>
          <p className="eyebrow">Workbench</p>
          <h1>本域工作台</h1>
        </div>
        <button className="workspace-topbar__button" type="button" onClick={() => setActiveView("rule-packages")}>
          打开规则包编辑页
        </button>
      </section>

      <p className="notice">{notice}</p>

      <GovernanceBoard dashboard={governanceDashboard} />

      <section className="workbench">
        <article className="panel panel--upload">
          <div className="panel__heading">
            <div>
              <p className="eyebrow">01 Local Data</p>
              <h2>本域数据导入</h2>
            </div>
          </div>
          <form className="upload-form" onSubmit={handleUpload}>
            <label>
              选择本域结构化文件
              <input name="dataset" type="file" accept=".csv,.xlsx,.xls" />
            </label>
            <button disabled={isPending} type="submit">
              本域导入并生成画像
            </button>
          </form>
          <p className="hint">导入文件仅写入本地 `workspace/imports`，不提供任何明细出域接口。</p>
        </article>

        <article className="panel">
          <div className="panel__heading">
            <div>
              <p className="eyebrow">02 Rule Package</p>
              <h2>规则包登记</h2>
            </div>
          </div>

          <form className="task-form" onSubmit={handleImportRulePackage}>
            <label>
              导入规则包文件
              <input type="file" accept=".json" onChange={(event) => void handleRulePackageFileChange(event)} />
            </label>
            <button disabled={isPending || !rulePackageImportDraft} type="submit">
              登记导入规则包
            </button>
          </form>

          {rulePackageImportDraft ? (
            <div className="result-block">
              <strong>导入预检</strong>
              <small>文件：{rulePackageImportFileName || "-"}</small>
              <small>名称：{rulePackageImportDraft.name}</small>
              <small>版本：{rulePackageImportDraft.version}</small>
              <small>签名人：{rulePackageImportDraft.signer_name || "未填写"}</small>
              <small>签名引用：{rulePackageImportDraft.signature_ref || "未填写"}</small>
              <small>规则条目：{countRuleItems(rulePackageImportDraft.rules)}</small>
              <small>用途：{rulePackageImportDraft.purpose}</small>
            </div>
          ) : (
            <p className="hint">此处不再手工录入规则字段、操作符和值，统一通过 JSON 规则包导入登记；复杂创建与编辑请进入规则包编辑页。</p>
          )}

          <label>
            审批人
            <input value={approverName} onChange={(event) => setApproverName(event.target.value)} />
          </label>

          <div className="task-row">
            <button disabled={isPending} type="button" onClick={handleBatchVerifyRulePackages}>
              批量验签
            </button>
            <button disabled={isPending} type="button" onClick={handleBatchApproveRulePackages}>
              批量审批
            </button>
          </div>

          {batchMessage?.length ? (
            <div className="result-block">
              <strong>批量处理结果</strong>
              {batchMessage.map((item) => (
                <small key={item.package_id}>
                  {item.name} / {item.status} / {item.message}
                </small>
              ))}
            </div>
          ) : null}

          <div className="task-list">
            {rulePackages.slice(0, 6).map((rulePackage) => (
              <div className="task-row" key={rulePackage.id}>
                <label className="inline-check">
                  <input
                    checked={selectedRulePackageIds.includes(rulePackage.id)}
                    type="checkbox"
                    onChange={(event) =>
                      setSelectedRulePackageIds((current) =>
                        event.target.checked ? [...current, rulePackage.id] : current.filter((item) => item !== rulePackage.id),
                      )
                    }
                  />
                  选择
                </label>
                <strong>{rulePackage.name}</strong>
                <span>{rulePackage.status}</span>
                <small>验签：{rulePackage.verification_status}</small>
                <small>规则数：{rulePackage.rules_count}</small>
                <small>签名引用：{rulePackage.signature_ref || "-"}</small>
                {rulePackage.status !== "approved" ? (
                  <div className="panel-actions">
                    <button disabled={isPending} type="button" onClick={() => void handleVerifyRulePackage(rulePackage.id)}>
                      验签
                    </button>
                    <button disabled={isPending} type="button" onClick={() => void handleApproveRulePackage(rulePackage.id)}>
                      审批
                    </button>
                  </div>
                ) : (
                  <small>审批人：{rulePackage.approved_by ?? "-"}</small>
                )}
              </div>
            ))}
          </div>
        </article>

        <article className="panel">
          <div className="panel__heading">
            <div>
              <p className="eyebrow">03 Profile</p>
              <h2>本域字段画像</h2>
            </div>
          </div>
          {latestDataset ? (
            <>
              <div className="dataset-card">
                <strong>{latestDataset.source_filename}</strong>
                <span>
                  {latestDataset.row_count} 行 / {latestDataset.field_count} 字段
                </span>
                {latestDataset.note ? <em>{latestDataset.note}</em> : null}
              </div>
              <div className="field-list">
                {latestDataset.fields.slice(0, 8).map((field) => (
                  <div className="field-row" key={field.name}>
                    <strong>{field.name}</strong>
                    <span>{field.inferred_type}</span>
                    <small>
                      空值 {field.empty_count} / 重复 {field.duplicate_count}
                    </small>
                  </div>
                ))}
              </div>
            </>
          ) : (
            <p className="empty">暂无本域数据集。</p>
          )}
        </article>

        <article className="panel task-draft-panel">
          <div className="panel__heading">
            <div>
              <p className="eyebrow">04 Local Task</p>
              <h2>本域任务草稿</h2>
            </div>
            <button className="workspace-topbar__button" type="button" onClick={resetTaskDraftForm}>
              新建草稿
            </button>
          </div>

          <form className="task-form" onSubmit={handleCreateTaskDraft}>
            <label>
              任务名称
              <input value={taskName} onChange={(event) => setTaskName(event.target.value)} />
            </label>
            <label>
              任务说明
              <input value={taskDescription} onChange={(event) => setTaskDescription(event.target.value)} />
            </label>
            <label>
              数据集
              <select value={selectedDatasetId} onChange={(event) => setSelectedDatasetId(event.target.value)}>
                <option value="">暂不绑定</option>
                {datasets.map((dataset) => (
                  <option key={dataset.id} value={dataset.id}>
                    {dataset.source_filename}
                  </option>
                ))}
              </select>
            </label>
            <label>
              规则包
              <select value={selectedRulePackageId} onChange={(event) => setSelectedRulePackageId(event.target.value)}>
                <option value="">不绑定规则包</option>
                {approvedRulePackages.map((rulePackage) => (
                  <option key={rulePackage.id} value={rulePackage.id}>
                    {rulePackage.name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              输出策略
              <select value={outputPolicy} onChange={(event) => setOutputPolicy(event.target.value as OutputPolicy)}>
                <option value="local_only">仅本域留存</option>
                <option value="execution_receipt">执行回执</option>
                <option value="manual_assertion">结论声明</option>
                <option value="aggregate_summary">聚合统计</option>
              </select>
            </label>
            {outputPolicy === "aggregate_summary" ? (
              <>
                <label>
                  分组维度
                  <select value={aggregateGroupBy} onChange={(event) => setAggregateGroupBy(event.target.value as AggregateGroupBy)}>
                    <option value="department">部门</option>
                    <option value="matter_type">事项类型</option>
                    <option value="month">月份</option>
                  </select>
                </label>
                <label>
                  最小阈值
                  <input
                    min={domainPolicy?.aggregate_min_threshold ?? 10}
                    step={1}
                    type="number"
                    value={aggregateThreshold}
                    onChange={(event) => setAggregateThreshold(Number(event.target.value))}
                  />
                </label>
              </>
            ) : null}

            <div className="task-row task-draft-actions">
              <button disabled={isPending} type="submit">
                创建草稿
              </button>
              <button disabled={isPending || !selectedTaskId} type="button" onClick={() => void handleUpdateTaskDraft()}>
                保存修改
              </button>
              <button disabled={isPending} type="button" onClick={() => void handleSaveAsNewDraft()}>
                另存为新草稿
              </button>
            </div>
          </form>

          <div className="result-block">
            <strong>草稿摘要</strong>
            <small>当前模式：{selectedTaskId ? "编辑已有草稿" : "创建新草稿"}</small>
            <small>输出策略：{outputPolicyLabel(outputPolicy)}</small>
            <small>聚合维度：{outputPolicy === "aggregate_summary" ? aggregateDimensionLabel(aggregateGroupBy) : "未启用"}</small>
            <small>最小阈值：{outputPolicy === "aggregate_summary" ? String(aggregateThreshold) : "-"}</small>
          </div>

          <div className="task-list">
            {tasks.length ? (
              [...tasks].reverse().slice(0, 8).map((task) => {
                const taskDataset = datasets.find((item) => item.id === task.dataset_ids[0]);
                const taskResult = results.find((item) => item.task_id === task.id);
                return (
                  <div className="task-row" key={task.id}>
                    <strong>{task.name}</strong>
                    <span>{task.status}</span>
                    <small>数据集：{taskDataset?.source_filename ?? "-"}</small>
                    <small>规则包：{rulePackages.find((item) => item.id === task.rule_package_id)?.name ?? "-"}</small>
                    <small>输出策略：{outputPolicyLabel(task.output_policy)}</small>
                    <small>更新时间：{formatTime(task.updated_at ?? task.created_at)}</small>
                    <small>结果状态：{taskResult ? taskResult.status : "未执行"}</small>
                    <div className="panel-actions">
                      <button disabled={isPending} type="button" onClick={() => fillTaskDraftForm(task)}>
                        编辑
                      </button>
                      <button disabled={isPending} type="button" onClick={() => void handleExecuteTask(task.id)}>
                        执行
                      </button>
                      <button disabled={isPending} type="button" onClick={() => void handleDeleteTaskDraft(task.id)}>
                        删除
                      </button>
                    </div>
                  </div>
                );
              })
            ) : (
              <p className="empty">暂无本域任务草稿。</p>
            )}
          </div>

          {focusedTask ? (
            <div className="result-block">
              <strong>选中任务详情</strong>
              <small>任务：{focusedTask.name}</small>
              <small>状态：{focusedTask.status}</small>
              <small>创建时间：{formatTime(focusedTask.created_at)}</small>
              <small>最近更新时间：{formatTime(focusedTask.updated_at ?? focusedTask.created_at)}</small>
              {focusedResult ? <small>执行结果：{focusedResult.status}</small> : <small>执行结果：未生成</small>}
            </div>
          ) : null}
        </article>

        <article className="panel">
          <div className="panel__heading">
            <div>
              <p className="eyebrow">05 Mapping</p>
              <h2>字段映射</h2>
            </div>
          </div>
          <form className="task-form" onSubmit={handleSaveFieldMapping}>
            <label>
              主键字段
              <select value={primaryField} onChange={(event) => setPrimaryField(event.target.value)}>
                <option value="">不配置</option>
                {fieldNames.map((field) => (
                  <option key={field} value={field}>
                    {field}
                  </option>
                ))}
              </select>
            </label>
            <label>
              子键字段
              <select value={subField} onChange={(event) => setSubField(event.target.value)}>
                <option value="">不配置</option>
                {fieldNames.map((field) => (
                  <option key={field} value={field}>
                    {field}
                  </option>
                ))}
              </select>
            </label>
            <label>
              敏感字段
              <select value={sensitiveField} onChange={(event) => setSensitiveField(event.target.value)}>
                <option value="">不配置</option>
                {fieldNames.map((field) => (
                  <option key={field} value={field}>
                    {field}
                  </option>
                ))}
              </select>
            </label>
            <label>
              部门分组字段
              <select value={departmentField} onChange={(event) => setDepartmentField(event.target.value)}>
                <option value="">不配置</option>
                {fieldNames.map((field) => (
                  <option key={field} value={field}>
                    {field}
                  </option>
                ))}
              </select>
            </label>
            <label>
              事项类型字段
              <select value={matterTypeField} onChange={(event) => setMatterTypeField(event.target.value)}>
                <option value="">不配置</option>
                {fieldNames.map((field) => (
                  <option key={field} value={field}>
                    {field}
                  </option>
                ))}
              </select>
            </label>
            <label>
              月份字段
              <select value={monthField} onChange={(event) => setMonthField(event.target.value)}>
                <option value="">不配置</option>
                {fieldNames.map((field) => (
                  <option key={field} value={field}>
                    {field}
                  </option>
                ))}
              </select>
            </label>
            <button disabled={isPending || !selectedDatasetId} type="submit">
              保存字段映射
            </button>
          </form>
          {fieldMapping ? <p className="hint">最近映射更新时间：{formatTime(fieldMapping.updated_at)}</p> : null}
        </article>

        <article className="panel panel--audit">
          <div className="panel__heading">
            <div>
              <p className="eyebrow">06 Audit</p>
              <h2>边界审计</h2>
            </div>
          </div>
          <button disabled={isPending} type="button" onClick={handleVerifyAuditChain}>
            校验审计链完整性
          </button>
          {auditVerification ? (
            <div className="result-block">
              <strong>{auditVerification.valid ? "审计链完整" : "审计链异常"}</strong>
              <small>
                已检查 {auditVerification.checked_entries} / {auditVerification.total_entries} 条，链头{" "}
                {auditVerification.head_hash ?? "GENESIS"}
              </small>
              {auditVerification.errors.map((error) => (
                <small key={error}>{error}</small>
              ))}
            </div>
          ) : null}
          <div className="audit-list">
            {audit.length ? (
              audit.slice(-6).reverse().map((entry) => (
                <div className="audit-row" key={entry.id}>
                  <strong>{entry.summary}</strong>
                  <span>
                    {entry.action} / {formatTime(entry.created_at)}
                  </span>
                </div>
              ))
            ) : (
              <p className="empty">暂无审计记录。</p>
            )}
          </div>
        </article>

        <article className="panel">
          <div className="panel__heading">
            <div>
              <p className="eyebrow">07 Execute</p>
              <h2>执行与结果</h2>
            </div>
          </div>
          <div className="task-list">
            {tasks.length ? (
              [...tasks].reverse().slice(0, 8).map((task) => (
                <div className="task-row" key={task.id}>
                  <strong>{task.name}</strong>
                  <span>{task.output_policy}</span>
                  <small>状态：{task.status}</small>
                  {task.aggregate_threshold ? <small>阈值：{task.aggregate_threshold}</small> : null}
                  {task.aggregate_group_by ? <small>分组：{aggregateDimensionLabel(task.aggregate_group_by)}</small> : null}
                  <button disabled={isPending || task.status === "completed"} type="button" onClick={() => void handleExecuteTask(task.id)}>
                    执行本域任务
                  </button>
                </div>
              ))
            ) : (
              <p className="empty">暂无待执行任务。</p>
            )}
          </div>
        </article>

        <article className="panel">
          <div className="panel__heading">
            <div>
              <p className="eyebrow">08 Result</p>
              <h2>摘要结果</h2>
            </div>
          </div>
          {focusedResult ? (
            <div className="result-grid">
              {Object.entries(focusedResult.summary).map(([key, value]) => (
                <div className="metric" key={key}>
                  <span>{key}</span>
                  <strong>{String(value)}</strong>
                </div>
              ))}

              {focusedResult.aggregate_summary.length ? (
                <div className="result-block">
                  <strong>聚合统计</strong>
                  {focusedResult.aggregate_summary.map((item, index) => (
                    <small key={`${String(item.group)}-${index}`}>
                      {String(item.dimension)} / {String(item.group)} / {String(item.count)}
                    </small>
                  ))}
                </div>
              ) : null}

              {focusedResult.assertion ? (
                <div className="result-block">
                  <strong>结论声明</strong>
                  <small>{focusedResult.assertion.statement}</small>
                  <small>状态：{focusedResult.assertion.status}</small>
                  {focusedResult.assertion.reviewer_name ? <small>审批人：{focusedResult.assertion.reviewer_name}</small> : null}
                  {focusedResult.assertion.review_comment ? <small>审批意见：{focusedResult.assertion.review_comment}</small> : null}
                </div>
              ) : null}

              <div className="result-block">
                <strong>安全边界</strong>
                {focusedResult.local_security_notes.map((note) => (
                  <small key={note}>{note}</small>
                ))}
              </div>

              {focusedResult.assertion?.status === "pending_review" ? (
                <div className="result-block">
                  <strong>结论声明审批</strong>
                  <label>
                    审批人
                    <input value={assertionReviewer} onChange={(event) => setAssertionReviewer(event.target.value)} />
                  </label>
                  <label>
                    正式结论
                    <input value={assertionFinalStatement} onChange={(event) => setAssertionFinalStatement(event.target.value)} />
                  </label>
                  <label>
                    审批意见
                    <input value={assertionComment} onChange={(event) => setAssertionComment(event.target.value)} />
                  </label>
                  <div className="panel-actions">
                    <button disabled={isPending} type="button" onClick={() => void handleReviewAssertion("approved")}>
                      审批通过
                    </button>
                    <button disabled={isPending} type="button" onClick={() => void handleReviewAssertion("rejected")}>
                      驳回
                    </button>
                  </div>
                </div>
              ) : null}
            </div>
          ) : (
            <p className="empty">暂无执行结果。</p>
          )}
        </article>

        <article className="panel">
          <div className="panel__heading">
            <div>
              <p className="eyebrow">09 Operators</p>
              <h2>算子库</h2>
            </div>
          </div>
          <div className="task-list">
            {operators.map((operator) => (
              <div className="task-row" key={operator.code}>
                <strong>{operator.name}</strong>
                <span>{operator.category}</span>
                <small>{operator.description}</small>
              </div>
            ))}
          </div>
        </article>

        <article className="panel">
          <div className="panel__heading">
            <div>
              <p className="eyebrow">10 Export</p>
              <h2>安全输出审批</h2>
            </div>
          </div>
          <form className="task-form" onSubmit={handleCreateExportRequest}>
            <label>
              输出类型
              <select value={exportType} onChange={(event) => setExportType(event.target.value as ExportType)}>
                <option value="receipt">执行回执</option>
                <option value="assertion">结论声明</option>
                <option value="aggregate_summary">聚合统计</option>
              </select>
            </label>
            <label>
              申请人
              <input value={exportRequester} onChange={(event) => setExportRequester(event.target.value)} />
            </label>
            <label>
              审批人
              <input value={exportApprover} onChange={(event) => setExportApprover(event.target.value)} />
            </label>
            <label>
              输出用途
              <input value={exportPurpose} onChange={(event) => setExportPurpose(event.target.value)} />
            </label>
            <button disabled={isPending || !focusedResult} type="submit">
              创建输出申请
            </button>
          </form>

          <div className="task-list">
            {exportRequests.slice(-4).reverse().map((request) => (
              <div className="task-row" key={request.id}>
                <strong>{request.export_type}</strong>
                <span>{request.status}</span>
                <small>申请人：{request.requester_name}</small>
                {request.status !== "approved" ? (
                  <button disabled={isPending} type="button" onClick={() => void handleApproveExportRequest(request.id)}>
                    审批输出
                  </button>
                ) : (
                  <div className="panel-actions">
                    <button disabled={isPending} type="button" onClick={() => void handlePreviewExportPackage(request.id)}>
                      预览输出包
                    </button>
                    <button disabled={isPending} type="button" onClick={() => void handlePersistExportFile(request.id)}>
                      写入本域文件
                    </button>
                  </div>
                )}
              </div>
            ))}
          </div>

          {exportPackage ? (
            <div className="result-block">
              <strong>输出包预览</strong>
              <small>{JSON.stringify(exportPackage.payload)}</small>
              {exportPackage.safety_notes.map((note) => (
                <small key={note}>{note}</small>
              ))}
            </div>
          ) : null}

          {exportFiles.length ? (
            <div className="result-block">
              <strong>本域输出文件</strong>
              <label>
                归档员
                <input value={archiveOperator} onChange={(event) => setArchiveOperator(event.target.value)} />
              </label>
              <label>
                归档用途
                <input value={archivePurpose} onChange={(event) => setArchivePurpose(event.target.value)} />
              </label>
              <button disabled={isPending} type="button" onClick={handleCreateExportArchive}>
                归档封存
              </button>
              {exportFiles.slice(-4).reverse().map((file) => (
                <label className="inline-check" key={file.id}>
                  <input
                    checked={selectedExportFileIds.includes(file.id)}
                    type="checkbox"
                    onChange={(event) =>
                      setSelectedExportFileIds((current) =>
                        event.target.checked ? [...current, file.id] : current.filter((item) => item !== file.id),
                      )
                    }
                  />
                  {file.file_name} / {file.byte_size} bytes / {file.sha256.slice(0, 12)}
                </label>
              ))}
            </div>
          ) : null}

          {exportArchives.length ? (
            <div className="result-block">
              <strong>归档封存与验签报告</strong>
              {exportArchives.slice(-4).reverse().map((archive) => (
                <div className="panel-actions" key={archive.id}>
                  <small>
                    {archive.id} / {archive.file_count} 文件 / {archive.verification.valid ? "验签通过" : "待复核"}
                  </small>
                  <button disabled={isPending} type="button" onClick={() => void handleVerifyExportArchive(archive.id)}>
                    重新验签
                  </button>
                </div>
              ))}
            </div>
          ) : null}
        </article>
      </section>
    </main>
  );
}
