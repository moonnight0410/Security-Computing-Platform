import { FormEvent, startTransition, useEffect, useState } from "react";

import {
  approveExportRequest,
  approveRulePackage,
  batchApproveRulePackages,
  batchVerifyRulePackages,
  createExportArchive,
  createExportRequest,
  createRulePackage,
  createTask,
  executeTask,
  getAudit,
  getDatasets,
  getDomainPolicy,
  getExportArchives,
  getFieldMapping,
  getHealth,
  getExportFiles,
  getExportPackage,
  getExportRequests,
  getOperators,
  getRulePackages,
  getRuleSigners,
  getResults,
  getTasks,
  persistExportFile,
  reviewAssertion,
  saveFieldMapping,
  uploadDataset,
  verifyExportArchive,
  verifyRulePackage,
  verifyAuditChain,
} from "./api";
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
  HealthResponse,
  OperatorInfo,
  RulePackageBatchResult,
  RulePackage,
  Task,
  TaskResult,
  TrustedSignerInfo,
} from "./types";

const STAGE_CARDS = [
  { label: "本域数据", value: "只在本域导入、画像、留存", tone: "sand" },
  { label: "字段映射", value: "配置主键、子键、敏感字段", tone: "ink" },
  { label: "本地执行", value: "主键、去标识、算子均域内执行", tone: "green" },
  { label: "结果边界", value: "只返回摘要、回执和阈值统计", tone: "rust" },
];

function formatTime(value: string): string {
  return new Date(value).toLocaleString("zh-CN", {
    hour12: false,
  });
}

export default function App() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [domainPolicy, setDomainPolicy] = useState<DomainPolicy | null>(null);
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
  const [taskName, setTaskName] = useState("本域联查任务草稿");
  const [rulePackageName, setRulePackageName] = useState("事项规则包草稿");
  const [rulePackagePurpose, setRulePackagePurpose] = useState("下发不含数据的联查问题、规则说明和算子声明");
  const [rulePackageSignerName, setRulePackageSignerName] = useState("市级规则中心");
  const [rulePackageSignatureRef, setRulePackageSignatureRef] = useState("SIG-CENTER-001");
  const [rulePackageSignature, setRulePackageSignature] = useState("");
  const [ruleField, setRuleField] = useState("benefit_status");
  const [ruleOperator, setRuleOperator] = useState<"eq" | "neq" | "exists" | "not_empty" | "gte" | "lte">("eq");
  const [ruleValue, setRuleValue] = useState("正常");
  const [approverName, setApproverName] = useState("审核员A");
  const [outputPolicy, setOutputPolicy] = useState<"local_only" | "execution_receipt" | "manual_assertion" | "aggregate_summary">("local_only");
  const [aggregateThreshold, setAggregateThreshold] = useState(10);
  const [aggregateGroupBy, setAggregateGroupBy] = useState<"department" | "matter_type" | "month">("department");
  const [primaryField, setPrimaryField] = useState("");
  const [subField, setSubField] = useState("");
  const [sensitiveField, setSensitiveField] = useState("");
  const [departmentField, setDepartmentField] = useState("");
  const [matterTypeField, setMatterTypeField] = useState("");
  const [monthField, setMonthField] = useState("");
  const [exportType, setExportType] = useState<"receipt" | "assertion" | "aggregate_summary">("receipt");
  const [exportRequester, setExportRequester] = useState("经办人A");
  const [exportApprover, setExportApprover] = useState("审核员B");
  const [exportPurpose, setExportPurpose] = useState("事项办理结果反馈");
  const [assertionReviewer, setAssertionReviewer] = useState("审核员C");
  const [assertionFinalStatement, setAssertionFinalStatement] = useState("");
  const [assertionComment, setAssertionComment] = useState("");
  const [selectedRulePackageIds, setSelectedRulePackageIds] = useState<string[]>([]);
  const [selectedExportFileIds, setSelectedExportFileIds] = useState<string[]>([]);
  const [archiveOperator, setArchiveOperator] = useState("归档员A");
  const [archivePurpose, setArchivePurpose] = useState("归档封存与验签报告生成");
  const [batchMessage, setBatchMessage] = useState<RulePackageBatchResult[] | null>(null);
  const [notice, setNotice] = useState("系统处于 Stage 9：规则包中心、修订快照与编辑治理阶段");
  const [isPending, setIsPending] = useState(false);
  const [activeView, setActiveView] = useState<"workbench" | "rule-packages">("workbench");

  async function refresh() {
    const [
      nextHealth,
      nextPolicy,
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
      setSelectedRulePackageId((current) => current || nextRulePackages[0]?.id || "");
      if (nextRuleSigners.length) {
        setRulePackageSignerName((current) => current || nextRuleSigners[0].signer_name);
        setRulePackageSignatureRef((current) => current || nextRuleSigners[0].signature_ref);
      }
      setAggregateThreshold(nextPolicy.aggregate_min_threshold);
    });
  }

  useEffect(() => {
    refresh().catch((error: unknown) => {
      setNotice(error instanceof Error ? error.message : "无法连接本地后端服务");
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
        setNotice(error instanceof Error ? error.message : "字段映射加载失败");
      });
  }, [selectedDatasetId]);

  useEffect(() => {
    const signer = trustedSigners.find((item) => item.signer_name === rulePackageSignerName);
    if (signer) {
      setRulePackageSignatureRef(signer.signature_ref);
    }
  }, [rulePackageSignerName, trustedSigners]);

  async function handleUpload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const input = form.elements.namedItem("dataset") as HTMLInputElement | null;
    const file = input?.files?.[0];
    if (!file) {
      setNotice("请选择需要导入到本域的数据文件");
      return;
    }

    setIsPending(true);
    try {
      const dataset = await uploadDataset(file);
      await refresh();
      setNotice(`已在本域导入数据集：${dataset.source_filename}。不会生成任何出域数据。`);
      form.reset();
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "导入失败");
    } finally {
      setIsPending(false);
    }
  }

  async function handleCreateRulePackage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsPending(true);
    try {
      const rules = ruleField
        ? [
            {
              field: ruleField,
              operator: ruleOperator,
              value: ruleOperator === "exists" || ruleOperator === "not_empty" ? null : ruleValue,
            },
          ]
        : [];
      const rulePackage = await createRulePackage(
        rulePackageName,
        rulePackagePurpose,
        rulePackageSignerName,
        rulePackageSignatureRef,
        rulePackageSignature,
        rules,
      );
      await refresh();
      setNotice(`已登记规则包：${rulePackage.name}，验签状态为 ${rulePackage.verification_status}`);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "规则包登记失败");
    } finally {
      setIsPending(false);
    }
  }

  async function handleSaveFieldMapping(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedDatasetId) {
      setNotice("请先选择本域数据集");
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
      setNotice("字段映射已保存，本域任务可执行。");
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "字段映射保存失败");
    } finally {
      setIsPending(false);
    }
  }

  async function handleApproveRulePackage(rulePackageId: string) {
    setIsPending(true);
    try {
      const rulePackage = await approveRulePackage(rulePackageId, approverName);
      await refresh();
      setNotice(`规则包已审批通过：${rulePackage.name}`);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "规则包审批失败");
    } finally {
      setIsPending(false);
    }
  }

  async function handleVerifyRulePackage(rulePackageId: string) {
    setIsPending(true);
    try {
      const rulePackage = await verifyRulePackage(rulePackageId);
      await refresh();
      setNotice(`规则包验签结果：${rulePackage.verification_message ?? rulePackage.verification_status}`);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "规则包验签失败");
    } finally {
      setIsPending(false);
    }
  }

  async function handleBatchVerifyRulePackages() {
    if (!selectedRulePackageIds.length) {
      setNotice("请先选择需要批量验签的规则包");
      return;
    }
    setIsPending(true);
    try {
      const results = await batchVerifyRulePackages(selectedRulePackageIds);
      setBatchMessage(results);
      await refresh();
      setNotice(`已完成 ${results.length} 个规则包的批量验签`);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "批量验签失败");
    } finally {
      setIsPending(false);
    }
  }

  async function handleBatchApproveRulePackages() {
    if (!selectedRulePackageIds.length) {
      setNotice("请先选择需要批量审批的规则包");
      return;
    }
    setIsPending(true);
    try {
      const results = await batchApproveRulePackages(selectedRulePackageIds, approverName);
      setBatchMessage(results);
      await refresh();
      setNotice(`已处理 ${results.length} 个规则包的批量审批`);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "批量审批失败");
    } finally {
      setIsPending(false);
    }
  }

  async function handleCreateTask(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedDatasetId) {
      setNotice("请先导入或选择一个本域数据集");
      return;
    }

    setIsPending(true);
    try {
      const task = await createTask(
        taskName,
        [selectedDatasetId],
        selectedRulePackageId || null,
        null,
        outputPolicy,
        outputPolicy === "aggregate_summary" ? aggregateThreshold : undefined,
        outputPolicy === "aggregate_summary" ? aggregateGroupBy : undefined,
      );
      await refresh();
      setNotice(`已创建本域任务草稿：${task.name}，输出策略为 ${task.output_policy}`);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "创建任务失败");
    } finally {
      setIsPending(false);
    }
  }

  async function handleExecuteTask(taskId: string) {
    setIsPending(true);
    try {
      const result = await executeTask(taskId);
      await refresh();
      setNotice(`任务执行完成，处理 ${String(result.summary.row_count ?? 0)} 行。本域对象级明细未返回。`);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "任务执行失败");
    } finally {
      setIsPending(false);
    }
  }

  async function handleCreateExportRequest(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!latestResult) {
      setNotice("请先执行任务生成结果摘要");
      return;
    }
    setIsPending(true);
    try {
      const request = await createExportRequest(latestResult.id, exportType, exportRequester, exportPurpose);
      await refresh();
      setNotice(`已创建安全输出申请：${request.export_type}`);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "创建输出申请失败");
    } finally {
      setIsPending(false);
    }
  }

  async function handleApproveExportRequest(requestId: string) {
    setIsPending(true);
    try {
      const request = await approveExportRequest(requestId, exportApprover);
      await refresh();
      setNotice(`已审批安全输出申请：${request.export_type}`);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "审批输出申请失败");
    } finally {
      setIsPending(false);
    }
  }

  async function handlePreviewExportPackage(requestId: string) {
    setIsPending(true);
    try {
      const nextPackage = await getExportPackage(requestId);
      setExportPackage(nextPackage);
      setNotice(`已生成安全输出包预览：${nextPackage.export_type}`);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "生成输出包失败");
    } finally {
      setIsPending(false);
    }
  }

  async function handlePersistExportFile(requestId: string) {
    setIsPending(true);
    try {
      const exportFile = await persistExportFile(requestId);
      await refresh();
      setNotice(`安全输出包已写入本域文件：${exportFile.file_name}`);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "输出包落盘失败");
    } finally {
      setIsPending(false);
    }
  }

  async function handleCreateExportArchive() {
    if (!selectedExportFileIds.length) {
      setNotice("请先选择需要归档封存的输出文件");
      return;
    }
    setIsPending(true);
    try {
      const archive = await createExportArchive(selectedExportFileIds, archiveOperator, archivePurpose);
      await refresh();
      setNotice(`已创建归档封存：${archive.id}，共 ${archive.file_count} 个文件`);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "创建归档封存失败");
    } finally {
      setIsPending(false);
    }
  }

  async function handleVerifyExportArchive(archiveId: string) {
    setIsPending(true);
    try {
      const archive = await verifyExportArchive(archiveId);
      await refresh();
      setNotice(archive.verification.valid ? `归档验签通过：${archive.id}` : `归档验签失败：${archive.verification.errors.join("；")}`);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "归档验签失败");
    } finally {
      setIsPending(false);
    }
  }

  async function handleVerifyAuditChain() {
    setIsPending(true);
    try {
      const result = await verifyAuditChain();
      setAuditVerification(result);
      setNotice(result.valid ? `审计链校验通过，已检查 ${result.checked_entries} 条记录。` : `审计链校验失败：${result.errors.join("；")}`);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "审计链校验失败");
    } finally {
      setIsPending(false);
    }
  }

  async function handleReviewAssertion(decision: "approved" | "rejected") {
    if (!latestResult?.assertion) {
      setNotice("当前没有待审核的结论声明");
      return;
    }

    setIsPending(true);
    try {
      const result = await reviewAssertion(
        latestResult.id,
        assertionReviewer,
        decision,
        assertionFinalStatement || undefined,
        assertionComment || undefined,
      );
      await refresh();
      setNotice(`结论声明已${decision === "approved" ? "审核通过" : "驳回"}：${result.assertion?.status ?? "unknown"}`);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "结论声明审核失败");
    } finally {
      setIsPending(false);
    }
  }

  const latestDataset = datasets.find((dataset) => dataset.id === selectedDatasetId) ?? datasets[0];
  const fieldNames = latestDataset?.fields.map((field) => field.name) ?? [];
  const approvedRulePackages = rulePackages.filter((rulePackage) => rulePackage.status === "approved");
  const latestResult = results[results.length - 1];

  return (
    <main className="shell">
      {false ? (
        <>
      <section className="hero">
        <div className="hero__copy">
          <p className="eyebrow">Domain-Local Query Console</p>
          <h1>本域数据不出域联查计算系统</h1>
          <p className="hero__lead">
            Stage 8 已补齐输出文件归档封存与验签报告、规则包批量管理，并将规则包验签升级为正式公私钥验签。
          </p>
        </div>
        <div className="hero__status">
          <span className="status-dot" />
          <strong>{health?.status === "ok" ? "本域后端在线" : "等待本域后端连接"}</strong>
          <small>{health?.workspace ?? "启动后端后显示本域工作目录"}</small>
        </div>
      </section>

      <section className="policy-banner">
        <div>
          <p className="eyebrow">Boundary</p>
          <strong>{domainPolicy?.summary ?? "本域数据边界策略加载中"}</strong>
        </div>
        <div className="policy-tags">
          {(domainPolicy?.prohibited_exports ?? ["原始数据", "加密数据", "哈希数据", "去标识数据"]).slice(0, 4).map((item) => (
            <span key={item}>{item}不得出域</span>
          ))}
        </div>
        <p className="policy-note">
          允许输出：{domainPolicy?.allowed_outputs.join("、") ?? "执行回执、结论声明、聚合统计"}；聚合统计默认最小阈值{" "}
          {domainPolicy?.aggregate_min_threshold ?? 10}。
        </p>
        <p className="policy-note">
          分组策略：{domainPolicy?.aggregate_grouping_policy ?? "仅允许单维粗粒度分组"}；结论声明审批：{domainPolicy?.assertion_approval_policy ?? "执行人与审核人分离"}。
        </p>
      </section>

      <section className="stage-grid" aria-label="Stage 1 capability map">
        {STAGE_CARDS.map((card) => (
          <article className={`stage-card stage-card--${card.tone}`} key={card.label}>
            <span>{card.label}</span>
            <strong>{card.value}</strong>
          </article>
        ))}
      </section>

        </>
      ) : null}
      <div className="notice" role="status">
        {isPending ? "正在处理本域任务..." : notice}
      </div>

      <div className="view-switch">
        <button
          className={activeView === "workbench" ? "view-switch__button view-switch__button--active" : "view-switch__button"}
          type="button"
          onClick={() => setActiveView("workbench")}
        >
          本域工作台
        </button>
        <button
          className={activeView === "rule-packages" ? "view-switch__button view-switch__button--active" : "view-switch__button"}
          type="button"
          onClick={() => setActiveView("rule-packages")}
        >
          规则包中心
        </button>
      </div>

      {activeView === "rule-packages" ? (
        <RulePackageCenter
          packages={rulePackages}
          signers={trustedSigners}
          isPendingGlobal={isPending}
          onNotice={setNotice}
          onRefresh={refresh}
        />
      ) : (
      <section className="workbench">
        <article className="panel panel--upload">
          <div className="panel__heading">
            <p className="eyebrow">01 Local Data</p>
            <h2>本域数据导入</h2>
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
          <p className="hint">文件只写入本机 `workspace/imports`，Stage 1 不提供明细导出或跨域传输接口。</p>
        </article>

        <article className="panel">
          <div className="panel__heading">
            <p className="eyebrow">02 Rule Package</p>
            <h2>规则包登记</h2>
          </div>
          <form className="task-form" onSubmit={handleCreateRulePackage}>
            <label>
              规则包名称
              <input value={rulePackageName} onChange={(event) => setRulePackageName(event.target.value)} />
            </label>
            <label>
              规则包用途
              <input value={rulePackagePurpose} onChange={(event) => setRulePackagePurpose(event.target.value)} />
            </label>
            <label>
              签名人
              <select value={rulePackageSignerName} onChange={(event) => setRulePackageSignerName(event.target.value)}>
                {trustedSigners.map((signer) => (
                  <option key={signer.signer_name} value={signer.signer_name}>
                    {signer.signer_name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              规则包签名引用
              <input value={rulePackageSignatureRef} onChange={(event) => setRulePackageSignatureRef(event.target.value)} />
            </label>
            <label>
              规则包签名值
              <input value={rulePackageSignature} onChange={(event) => setRulePackageSignature(event.target.value)} />
            </label>
            <label>
              规则字段
              <input value={ruleField} onChange={(event) => setRuleField(event.target.value)} />
            </label>
            <label>
              规则操作符
              <select value={ruleOperator} onChange={(event) => setRuleOperator(event.target.value as typeof ruleOperator)}>
                <option value="eq">等于</option>
                <option value="neq">不等于</option>
                <option value="exists">存在</option>
                <option value="not_empty">非空</option>
                <option value="gte">大于等于</option>
                <option value="lte">小于等于</option>
              </select>
            </label>
            {ruleOperator !== "exists" && ruleOperator !== "not_empty" ? (
              <label>
                规则值
                <input value={ruleValue} onChange={(event) => setRuleValue(event.target.value)} />
              </label>
            ) : null}
            <button disabled={isPending} type="submit">
              登记待审批规则包
            </button>
          </form>
          <p className="hint">先用 `scripts/bootstrap-stage8-keys.ps1` 生成密钥，再用 `scripts/generate-rule-package-signature.ps1` 本地生成签名。</p>
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
                  {item.name} · {item.status} · {item.message}
                </small>
              ))}
            </div>
          ) : null}
          <div className="task-list">
            {rulePackages.slice(0, 4).map((rulePackage) => (
              <div className="task-row" key={rulePackage.id}>
                <label>
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
                <small>
                  验签：{rulePackage.verification_status} / {rulePackage.signature_ref}
                </small>
                <small>规则数：{rulePackage.rules_count}</small>
                <small>{rulePackage.verification_message ?? "待验签"}</small>
                {rulePackage.status !== "approved" ? (
                  <>
                    <button disabled={isPending} type="button" onClick={() => handleVerifyRulePackage(rulePackage.id)}>
                      重新验签
                    </button>
                    <button disabled={isPending} type="button" onClick={() => handleApproveRulePackage(rulePackage.id)}>
                      审批通过
                    </button>
                  </>
                ) : (
                  <small>审批人：{rulePackage.approved_by ?? "已审批"}</small>
                )}
              </div>
            ))}
          </div>
        </article>

        <article className="panel">
          <div className="panel__heading">
            <p className="eyebrow">03 Profile</p>
            <h2>本域字段画像</h2>
          </div>
          {latestDataset ? (
            <div className="dataset-card">
              <strong>{latestDataset.source_filename}</strong>
              <span>
                {latestDataset.row_count} 行 · {latestDataset.field_count} 字段
              </span>
              {latestDataset.note ? <em>{latestDataset.note}</em> : null}
            </div>
          ) : (
            <p className="empty">暂无本域数据集，先导入一个 CSV 文件。</p>
          )}
          <div className="field-list">
            {latestDataset?.fields.slice(0, 8).map((field) => (
              <div className="field-row" key={field.name}>
                <strong>{field.name}</strong>
                <span>{field.inferred_type}</span>
                <small>
                  空值 {field.empty_count} · 重复 {field.duplicate_count}
                </small>
              </div>
            ))}
          </div>
        </article>

        <article className="panel">
          <div className="panel__heading">
            <p className="eyebrow">04 Local Task</p>
            <h2>本域任务草稿</h2>
          </div>
          <form className="task-form" onSubmit={handleCreateTask}>
            <label>
              任务名称
              <input value={taskName} onChange={(event) => setTaskName(event.target.value)} />
            </label>
            <label>
              选择本域数据集
              <select value={selectedDatasetId} onChange={(event) => setSelectedDatasetId(event.target.value)}>
                <option value="">暂无选择</option>
                {datasets.map((dataset) => (
                  <option key={dataset.id} value={dataset.id}>
                    {dataset.source_filename}
                  </option>
                ))}
              </select>
            </label>
            <label>
              选择规则包
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
              <select value={outputPolicy} onChange={(event) => setOutputPolicy(event.target.value as typeof outputPolicy)}>
                <option value="local_only">仅本域留存</option>
                <option value="execution_receipt">仅执行状态回执</option>
                <option value="manual_assertion">结论声明双人流程</option>
                <option value="aggregate_summary">聚合统计输出</option>
              </select>
            </label>
            {outputPolicy === "aggregate_summary" ? (
              <>
                <label>
                  聚合统计分组维度
                  <select value={aggregateGroupBy} onChange={(event) => setAggregateGroupBy(event.target.value as typeof aggregateGroupBy)}>
                    <option value="department">部门</option>
                    <option value="matter_type">事项类型</option>
                    <option value="month">月份</option>
                  </select>
                </label>
                <label>
                  聚合统计最小阈值
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
            <button disabled={isPending || !selectedDatasetId} type="submit">
              创建本域任务
            </button>
          </form>
        </article>

        <article className="panel">
          <div className="panel__heading">
            <p className="eyebrow">05 Mapping</p>
            <h2>字段映射</h2>
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
              保存本域字段映射
            </button>
          </form>
          {fieldMapping ? <p className="hint">上次映射更新时间：{formatTime(fieldMapping.updated_at)}</p> : null}
        </article>

        <article className="panel panel--audit">
          <div className="panel__heading">
            <p className="eyebrow">06 Audit</p>
            <h2>边界审计</h2>
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
                    {entry.action} · {formatTime(entry.created_at)}
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
            <p className="eyebrow">07 Execute</p>
            <h2>执行与结果</h2>
          </div>
          <div className="task-list">
            {tasks.length ? (
              tasks.slice(0, 6).map((task) => (
                <div className="task-row" key={task.id}>
                  <strong>{task.name}</strong>
                  <span>{task.output_policy}</span>
                  {task.aggregate_threshold ? <small>阈值 {task.aggregate_threshold}</small> : null}
                  {task.aggregate_group_by ? <small>分组 {task.aggregate_group_by}</small> : null}
                  <button disabled={isPending || task.status === "completed"} type="button" onClick={() => handleExecuteTask(task.id)}>
                    执行本域任务
                  </button>
                </div>
              ))
            ) : (
              <p className="empty">暂无本域任务草稿。</p>
            )}
          </div>
        </article>

        <article className="panel">
          <div className="panel__heading">
            <p className="eyebrow">08 Result</p>
            <h2>摘要结果</h2>
          </div>
          {latestResult ? (
            <div className="result-grid">
              {Object.entries(latestResult.summary).map(([key, value]) => (
                <div className="metric" key={key}>
                  <span>{key}</span>
                  <strong>{String(value)}</strong>
                </div>
              ))}
              {latestResult.aggregate_summary.length ? (
                <div className="result-block">
                  <strong>聚合统计</strong>
                  {latestResult.aggregate_summary.map((item, index) => (
                    <small key={`${String(item.group)}-${index}`}>
                      {String(item.dimension)} / {String(item.group)}：{String(item.count)}
                    </small>
                  ))}
                </div>
              ) : null}
              {latestResult.assertion ? (
                <div className="result-block">
                  <strong>结论声明</strong>
                  <small>{latestResult.assertion.statement}</small>
                  <small>状态：{latestResult.assertion.status}</small>
                  {latestResult.assertion.reviewer_name ? <small>审核人：{latestResult.assertion.reviewer_name}</small> : null}
                  {latestResult.assertion.review_comment ? <small>审核意见：{latestResult.assertion.review_comment}</small> : null}
                </div>
              ) : null}
              <div className="result-block">
                <strong>安全边界</strong>
                {latestResult.local_security_notes.map((note) => (
                  <small key={note}>{note}</small>
                ))}
              </div>
              {latestResult.assertion?.status === "pending_review" ? (
                <div className="result-block">
                  <strong>结论声明审核</strong>
                  <label>
                    审核人
                    <input value={assertionReviewer} onChange={(event) => setAssertionReviewer(event.target.value)} />
                  </label>
                  <label>
                    正式结论
                    <input value={assertionFinalStatement} onChange={(event) => setAssertionFinalStatement(event.target.value)} />
                  </label>
                  <label>
                    审核意见
                    <input value={assertionComment} onChange={(event) => setAssertionComment(event.target.value)} />
                  </label>
                  <button disabled={isPending} type="button" onClick={() => handleReviewAssertion("approved")}>
                    审核通过
                  </button>
                  <button disabled={isPending} type="button" onClick={() => handleReviewAssertion("rejected")}>
                    驳回结论
                  </button>
                </div>
              ) : null}
            </div>
          ) : (
            <p className="empty">暂无执行结果。</p>
          )}
        </article>

        <article className="panel">
          <div className="panel__heading">
            <p className="eyebrow">09 Operators</p>
            <h2>算子库</h2>
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
            <p className="eyebrow">10 Export</p>
            <h2>安全输出审批</h2>
          </div>
          <form className="task-form" onSubmit={handleCreateExportRequest}>
            <label>
              输出类型
              <select value={exportType} onChange={(event) => setExportType(event.target.value as typeof exportType)}>
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
            <button disabled={isPending || !latestResult} type="submit">
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
                  <button disabled={isPending} type="button" onClick={() => handleApproveExportRequest(request.id)}>
                    审批输出
                  </button>
                ) : (
                  <>
                    <button disabled={isPending} type="button" onClick={() => handlePreviewExportPackage(request.id)}>
                      预览输出包
                    </button>
                    <button disabled={isPending} type="button" onClick={() => handlePersistExportFile(request.id)}>
                      写入本域文件
                    </button>
                  </>
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
                <label key={file.id}>
                  <input
                    checked={selectedExportFileIds.includes(file.id)}
                    type="checkbox"
                    onChange={(event) =>
                      setSelectedExportFileIds((current) =>
                        event.target.checked ? [...current, file.id] : current.filter((item) => item !== file.id),
                      )
                    }
                  />
                  {file.file_name} · {file.byte_size} bytes · {file.sha256.slice(0, 12)}
                </label>
              ))}
            </div>
          ) : null}
          {exportArchives.length ? (
            <div className="result-block">
              <strong>归档封存与验签报告</strong>
              {exportArchives.slice(-4).reverse().map((archive) => (
                <div key={archive.id}>
                  <small>
                    {archive.id} · {archive.file_count} 个文件 · 验签 {archive.verification.valid ? "通过" : "失败"}
                  </small>
                  <button disabled={isPending} type="button" onClick={() => handleVerifyExportArchive(archive.id)}>
                    重新验签报告
                  </button>
                </div>
              ))}
            </div>
          ) : null}
        </article>
      </section>
      )}
    </main>
  );
}
