import { FormEvent, useEffect, useMemo, useRef, useState } from "react";

import {
  approveRulePackageCenter,
  beginRulePackageEdit,
  createRulePackageDraft,
  createRuleSnippet,
  createRuleTemplate,
  deleteRulePackage,
  deprecateRulePackage,
  getRulePackageReferences,
  getRulePackageRevisionDiff,
  getRulePackageRevisions,
  getRuleSnippets,
  getRuleTemplates,
  saveRulePackageDraft,
  submitRulePackageVerification,
} from "./api";
import type {
  RuleGroupNode,
  RuleNode,
  RulePackage,
  RulePackageRevision,
  RulePackageRevisionDiff,
  RulePackageUsageReport,
  RuleSnippet,
  RuleTemplate,
  TrustedSignerInfo,
} from "./types";

type RuleOperator = "eq" | "neq" | "exists" | "not_empty" | "gte" | "lte" | "in";

type EditableRuleLeaf = {
  id: string;
  type: "rule";
  field: string;
  operator: RuleOperator;
  value: string;
};

type EditableRuleGroup = {
  id: string;
  type: "group";
  logic: "and" | "or";
  children: EditableRuleNode[];
};

type EditableRuleNode = EditableRuleLeaf | EditableRuleGroup;

type RuleDraft = {
  name: string;
  version: string;
  purpose: string;
  notes: string;
  signer_name: string;
  signature_ref: string;
  signature: string;
  editor_name: string;
  change_summary: string;
  rules: EditableRuleGroup;
};

type Props = {
  packages: RulePackage[];
  signers: TrustedSignerInfo[];
  isPendingGlobal: boolean;
  onNotice: (message: string) => void;
  onRefresh: () => Promise<void>;
};

const DEFAULT_EDITOR = "经办员A";
const DEFAULT_APPROVER = "审核员B";
const DEFAULT_DEPRECATE_OPERATOR = "治理员A";

function makeId(): string {
  return Math.random().toString(36).slice(2, 10);
}

function formatTime(value: string): string {
  return new Date(value).toLocaleString("zh-CN", { hour12: false });
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined || value === "") {
    return "未设置";
  }
  if (Array.isArray(value) || typeof value === "object") {
    return JSON.stringify(value);
  }
  return String(value);
}

function createEmptyLeaf(): EditableRuleLeaf {
  return {
    id: makeId(),
    type: "rule",
    field: "",
    operator: "eq",
    value: "",
  };
}

function createEmptyGroup(logic: "and" | "or" = "and"): EditableRuleGroup {
  return {
    id: makeId(),
    type: "group",
    logic,
    children: [createEmptyLeaf()],
  };
}

function convertNode(raw: Record<string, unknown>): EditableRuleNode {
  if ((raw.type === "group" || ("logic" in raw && "children" in raw)) && Array.isArray(raw.children)) {
    return {
      id: makeId(),
      type: "group",
      logic: raw.logic === "or" ? "or" : "and",
      children: raw.children.map((child) => convertNode(child as Record<string, unknown>)),
    };
  }

  return {
    id: makeId(),
    type: "rule",
    field: String(raw.field ?? ""),
    operator: (raw.operator as RuleOperator) ?? "eq",
    value: Array.isArray(raw.value) ? raw.value.join(",") : String(raw.value ?? ""),
  };
}

function parseRules(rules: Array<Record<string, unknown>>): EditableRuleGroup {
  if (rules.length === 1 && (rules[0].type === "group" || ("logic" in rules[0] && "children" in rules[0]))) {
    const root = convertNode(rules[0]);
    return root.type === "group" ? root : createEmptyGroup();
  }

  return {
    id: makeId(),
    type: "group",
    logic: "and",
    children: rules.length ? rules.map((rule) => convertNode(rule)) : [createEmptyLeaf()],
  };
}

function serializeNode(node: EditableRuleNode): Record<string, unknown> {
  if (node.type === "group") {
    return {
      type: "group",
      logic: node.logic,
      children: node.children.map((child) => serializeNode(child)),
    };
  }

  return {
    type: "rule",
    field: node.field.trim(),
    operator: node.operator,
    value:
      node.operator === "exists" || node.operator === "not_empty"
        ? null
        : node.operator === "in"
          ? node.value
              .split(",")
              .map((item) => item.trim())
              .filter(Boolean)
          : node.value.trim(),
  };
}

function emptyDraft(signers: TrustedSignerInfo[]): RuleDraft {
  const signer = signers[0];
  return {
    name: "事项规则包草稿",
    version: "0.1.0",
    purpose: "用于本域联查任务的规则草稿，不携带任何对象级数据",
    notes: "",
    signer_name: signer?.signer_name ?? "",
    signature_ref: signer?.signature_ref ?? "",
    signature: "",
    editor_name: DEFAULT_EDITOR,
    change_summary: "创建首版草稿",
    rules: createEmptyGroup("and"),
  };
}

function draftFromRevision(revision: RulePackageRevision): RuleDraft {
  return {
    name: revision.name,
    version: revision.version,
    purpose: revision.purpose,
    notes: revision.notes ?? "",
    signer_name: revision.signer_name,
    signature_ref: revision.signature_ref,
    signature: revision.signature,
    editor_name: revision.editor_name ?? DEFAULT_EDITOR,
    change_summary: revision.change_summary ?? "",
    rules: parseRules(revision.rules),
  };
}

function updateNode(tree: EditableRuleGroup, targetId: string, updater: (node: EditableRuleNode) => EditableRuleNode): EditableRuleGroup {
  const walk = (node: EditableRuleNode): EditableRuleNode => {
    if (node.id === targetId) {
      return updater(node);
    }
    if (node.type === "group") {
      return { ...node, children: node.children.map((child) => walk(child)) };
    }
    return node;
  };

  const updated = walk(tree);
  return updated.type === "group" ? updated : tree;
}

function appendChild(tree: EditableRuleGroup, groupId: string, child: EditableRuleNode): EditableRuleGroup {
  return updateNode(tree, groupId, (node) =>
    node.type === "group" ? { ...node, children: [...node.children, child] } : node,
  );
}

function removeNode(tree: EditableRuleGroup, targetId: string): EditableRuleGroup {
  if (tree.id === targetId) {
    return tree;
  }

  const walkGroup = (group: EditableRuleGroup): EditableRuleGroup => {
    const nextChildren = group.children
      .filter((child) => child.id !== targetId)
      .map((child) => (child.type === "group" ? walkGroup(child) : child));
    return { ...group, children: nextChildren.length ? nextChildren : [createEmptyLeaf()] };
  };

  return walkGroup(tree);
}

export default function RulePackageCenter({ packages, signers, isPendingGlobal, onNotice, onRefresh }: Props) {
  const [selectedPackageId, setSelectedPackageId] = useState<string>("");
  const [revisions, setRevisions] = useState<RulePackageRevision[]>([]);
  const [usageReport, setUsageReport] = useState<RulePackageUsageReport | null>(null);
  const [diffReport, setDiffReport] = useState<RulePackageRevisionDiff | null>(null);
  const [templates, setTemplates] = useState<RuleTemplate[]>([]);
  const [snippets, setSnippets] = useState<RuleSnippet[]>([]);
  const [selectedDiffFromId, setSelectedDiffFromId] = useState("");
  const [selectedDiffToId, setSelectedDiffToId] = useState("");
  const [activeGroupId, setActiveGroupId] = useState("");
  const [draft, setDraft] = useState<RuleDraft>(() => emptyDraft(signers));
  const [templateName, setTemplateName] = useState("常用联查模板");
  const [templateDescription, setTemplateDescription] = useState("复用规则结构，不含任何业务数据。");
  const [isNewDraft, setIsNewDraft] = useState(true);
  const [isDirty, setIsDirty] = useState(false);
  const [isPending, setIsPending] = useState(false);
  const [approverName, setApproverName] = useState(DEFAULT_APPROVER);
  const [deprecateOperator, setDeprecateOperator] = useState(DEFAULT_DEPRECATE_OPERATOR);
  const [deprecateReason, setDeprecateReason] = useState("规则已被新口径替代");

  const dirtyRef = useRef(isDirty);
  const draftRef = useRef(draft);
  const selectedPackageIdRef = useRef(selectedPackageId);
  const isNewDraftRef = useRef(isNewDraft);

  useEffect(() => {
    dirtyRef.current = isDirty;
    draftRef.current = draft;
    selectedPackageIdRef.current = selectedPackageId;
    isNewDraftRef.current = isNewDraft;
  }, [draft, isDirty, isNewDraft, selectedPackageId]);

  useEffect(() => {
    if (!draft.signer_name && signers.length) {
      setDraft((current) => ({
        ...current,
        signer_name: signers[0].signer_name,
        signature_ref: signers[0].signature_ref,
      }));
    }
  }, [signers, draft.signer_name]);

  useEffect(() => {
    if (!selectedPackageId && packages.length) {
      setSelectedPackageId(packages[0].id);
    }
  }, [packages, selectedPackageId]);

  useEffect(() => {
    setActiveGroupId(draft.rules.id);
  }, [draft.rules.id]);

  async function reloadRuleAssets() {
    const [nextTemplates, nextSnippets] = await Promise.all([getRuleTemplates(), getRuleSnippets()]);
    setTemplates(nextTemplates);
    setSnippets(nextSnippets);
  }

  async function reloadPackageGovernance(packageId: string) {
    const [items, references] = await Promise.all([
      getRulePackageRevisions(packageId),
      getRulePackageReferences(packageId),
    ]);
    setRevisions(items);
    setUsageReport(references);
  }

  async function loadRevisionDiff(packageId: string, fromRevisionId: string, toRevisionId: string) {
    if (!fromRevisionId || !toRevisionId || fromRevisionId === toRevisionId) {
      setDiffReport(null);
      return;
    }
    const report = await getRulePackageRevisionDiff(packageId, fromRevisionId, toRevisionId);
    setDiffReport(report);
  }

  useEffect(() => {
    reloadRuleAssets().catch((error: unknown) => {
      onNotice(error instanceof Error ? error.message : "规则资产加载失败");
    });
  }, [onNotice]);

  useEffect(() => {
    if (!selectedPackageId) {
      setRevisions([]);
      setUsageReport(null);
      setDiffReport(null);
      return;
    }
    reloadPackageGovernance(selectedPackageId).catch((error: unknown) => {
      onNotice(error instanceof Error ? error.message : "规则包治理信息加载失败");
    });
  }, [onNotice, selectedPackageId]);

  useEffect(() => {
    if (!revisions.length) {
      setSelectedDiffFromId("");
      setSelectedDiffToId("");
      setDiffReport(null);
      return;
    }
    const latest = revisions[revisions.length - 1];
    const previous = revisions[revisions.length - 2] ?? revisions[0];
    setSelectedDiffToId((current) => (revisions.some((item) => item.id === current) ? current : latest.id));
    setSelectedDiffFromId((current) => (revisions.some((item) => item.id === current) ? current : previous.id));
  }, [revisions]);

  useEffect(() => {
    if (!selectedPackageId || !selectedDiffFromId || !selectedDiffToId || selectedDiffFromId === selectedDiffToId) {
      setDiffReport(null);
      return;
    }
    loadRevisionDiff(selectedPackageId, selectedDiffFromId, selectedDiffToId).catch((error: unknown) => {
      onNotice(error instanceof Error ? error.message : "规则包修订差异加载失败");
    });
  }, [onNotice, selectedDiffFromId, selectedDiffToId, selectedPackageId]);

  useEffect(() => {
    const handlePageHide = () => {
      if (!dirtyRef.current) {
        return;
      }
      const currentDraft = draftRef.current;
      const currentPackageId = selectedPackageIdRef.current;
      const serializedRules = [serializeNode(currentDraft.rules)];
      if (isNewDraftRef.current) {
        void createRulePackageDraft({
          ...currentDraft,
          rules: serializedRules,
        });
        return;
      }
      if (!currentPackageId) {
        return;
      }
      void saveRulePackageDraft(currentPackageId, {
        ...currentDraft,
        rules: serializedRules,
        auto_saved: true,
      });
    };

    window.addEventListener("pagehide", handlePageHide);
    return () => {
      window.removeEventListener("pagehide", handlePageHide);
      handlePageHide();
    };
  }, []);

  const selectedPackage = useMemo(
    () => packages.find((item) => item.id === selectedPackageId) ?? null,
    [packages, selectedPackageId],
  );

  const revisionUsageMap = useMemo(
    () => new Map((usageReport?.revision_summaries ?? []).map((item) => [item.revision_id, item.task_count])),
    [usageReport],
  );

  async function persistDraft(autoSaved = false) {
    const payload = {
      ...draft,
      rules: [serializeNode(draft.rules)],
      auto_saved: autoSaved,
    };
    if (isNewDraft) {
      const nextPackage = await createRulePackageDraft(payload);
      await onRefresh();
      await reloadPackageGovernance(nextPackage.id);
      setSelectedPackageId(nextPackage.id);
      setIsNewDraft(false);
      setIsDirty(false);
      onNotice(autoSaved ? `已自动创建规则包草稿：${nextPackage.name}` : `已创建规则包草稿：${nextPackage.name}`);
      return;
    }
    if (!selectedPackageId) {
      return;
    }
    const revision = await saveRulePackageDraft(selectedPackageId, payload);
    await onRefresh();
    await reloadPackageGovernance(selectedPackageId);
    setDraft(draftFromRevision(revision));
    setIsDirty(false);
    onNotice(autoSaved ? `已自动保存修订 R${revision.revision_no}` : `已保存修订 R${revision.revision_no}`);
  }

  async function handleSaveDraft(event?: FormEvent) {
    event?.preventDefault();
    setIsPending(true);
    try {
      await persistDraft(false);
    } catch (error) {
      onNotice(error instanceof Error ? error.message : "规则包保存失败");
    } finally {
      setIsPending(false);
    }
  }

  async function handleSelectPackage(packageId: string) {
    if (isDirty) {
      setIsPending(true);
      try {
        await persistDraft(true);
      } catch {
        // best effort
      } finally {
        setIsPending(false);
      }
    }
    setSelectedPackageId(packageId);
    setIsNewDraft(false);
  }

  async function handleEditPackage(rulePackageId: string) {
    setIsPending(true);
    try {
      const revision = await beginRulePackageEdit(rulePackageId, draft.editor_name || DEFAULT_EDITOR);
      setSelectedPackageId(rulePackageId);
      setIsNewDraft(false);
      setDraft(draftFromRevision(revision));
      setIsDirty(false);
      await onRefresh();
      await reloadPackageGovernance(rulePackageId);
      onNotice(
        selectedPackage?.status === "approved"
          ? "已基于已审批版本自动派生新的修订草稿"
          : `进入修订 R${revision.revision_no} 编辑`,
      );
    } catch (error) {
      onNotice(error instanceof Error ? error.message : "进入规则包编辑失败");
    } finally {
      setIsPending(false);
    }
  }

  async function handleSubmitVerification() {
    if (!selectedPackageId) {
      return;
    }
    setIsPending(true);
    try {
      const result = await submitRulePackageVerification(selectedPackageId);
      await onRefresh();
      await reloadPackageGovernance(selectedPackageId);
      setIsDirty(false);
      onNotice(`规则包验签结果：${result.verification_message ?? result.verification_status}`);
    } catch (error) {
      onNotice(error instanceof Error ? error.message : "提交验签失败");
    } finally {
      setIsPending(false);
    }
  }

  async function handleApprovePackage() {
    if (!selectedPackageId) {
      return;
    }
    setIsPending(true);
    try {
      const result = await approveRulePackageCenter(selectedPackageId, approverName);
      await onRefresh();
      await reloadPackageGovernance(selectedPackageId);
      setIsDirty(false);
      onNotice(`规则包已审批通过：${result.name}`);
    } catch (error) {
      onNotice(error instanceof Error ? error.message : "审批规则包失败");
    } finally {
      setIsPending(false);
    }
  }

  async function handleDeprecatePackage() {
    if (!selectedPackageId) {
      return;
    }
    setIsPending(true);
    try {
      const result = await deprecateRulePackage(selectedPackageId, deprecateOperator, deprecateReason);
      await onRefresh();
      await reloadPackageGovernance(selectedPackageId);
      onNotice(`规则包已废弃：${result.name}`);
    } catch (error) {
      onNotice(error instanceof Error ? error.message : "废弃规则包失败");
    } finally {
      setIsPending(false);
    }
  }

  async function handleDeletePackage() {
    if (!selectedPackageId) {
      return;
    }
    setIsPending(true);
    try {
      await deleteRulePackage(selectedPackageId);
      await onRefresh();
      setSelectedPackageId("");
      setRevisions([]);
      setUsageReport(null);
      setDiffReport(null);
      setDraft(emptyDraft(signers));
      setIsNewDraft(true);
      setIsDirty(false);
      onNotice("规则包草稿已删除");
    } catch (error) {
      onNotice(error instanceof Error ? error.message : "删除规则包失败");
    } finally {
      setIsPending(false);
    }
  }

  async function handleSaveTemplate() {
    setIsPending(true);
    try {
      await createRuleTemplate({
        name: templateName,
        description: templateDescription,
        rules: [serializeNode(draft.rules)],
        created_by: draft.editor_name || DEFAULT_EDITOR,
      });
      await reloadRuleAssets();
      onNotice(`已保存规则模板：${templateName}`);
    } catch (error) {
      onNotice(error instanceof Error ? error.message : "保存规则模板失败");
    } finally {
      setIsPending(false);
    }
  }

  async function handleSaveSnippet(node: EditableRuleLeaf) {
    if (!node.field.trim()) {
      onNotice("规则字段为空，不能保存为条目。");
      return;
    }
    setIsPending(true);
    try {
      await createRuleSnippet({
        name: `${node.field}-${node.operator}`,
        description: "从当前规则包编辑器保存的规则条目。",
        rule: serializeNode(node),
        created_by: draft.editor_name || DEFAULT_EDITOR,
      });
      await reloadRuleAssets();
      onNotice(`已保存规则条目：${node.field}-${node.operator}`);
    } catch (error) {
      onNotice(error instanceof Error ? error.message : "保存规则条目失败");
    } finally {
      setIsPending(false);
    }
  }

  function markDirty(nextRules: EditableRuleGroup) {
    setDraft((current) => ({ ...current, rules: nextRules }));
    setIsDirty(true);
  }

  function renderNode(node: EditableRuleNode, depth = 0) {
    if (node.type === "group") {
      return (
        <div className="rule-tree-group" key={node.id} style={{ marginLeft: depth ? `${depth * 12}px` : undefined }}>
          <div className="rule-tree-group__header">
            <strong>{depth === 0 ? "根分组" : "子分组"}</strong>
            <div className="rule-tree-group__actions">
              <select
                value={node.logic}
                onChange={(event) => markDirty(updateNode(draft.rules, node.id, () => ({ ...node, logic: event.target.value as "and" | "or" })))}
              >
                <option value="and">AND</option>
                <option value="or">OR</option>
              </select>
              <button type="button" onClick={() => setActiveGroupId(node.id)}>
                设为插入目标
              </button>
              <button type="button" onClick={() => markDirty(appendChild(draft.rules, node.id, createEmptyLeaf()))}>
                加规则
              </button>
              <button type="button" onClick={() => markDirty(appendChild(draft.rules, node.id, createEmptyGroup("and")))}>
                加子组
              </button>
              {depth > 0 ? (
                <button type="button" onClick={() => markDirty(removeNode(draft.rules, node.id))}>
                  删除分组
                </button>
              ) : null}
            </div>
          </div>
          <div className="rule-tree-group__body">{node.children.map((child) => renderNode(child, depth + 1))}</div>
        </div>
      );
    }

    return (
      <div className="rule-tree-leaf" key={node.id} style={{ marginLeft: depth ? `${depth * 12}px` : undefined }}>
        <input
          value={node.field}
          placeholder="字段"
          onChange={(event) => markDirty(updateNode(draft.rules, node.id, () => ({ ...node, field: event.target.value })))}
        />
        <select
          value={node.operator}
          onChange={(event) => markDirty(updateNode(draft.rules, node.id, () => ({ ...node, operator: event.target.value as RuleOperator })))}
        >
          <option value="eq">等于</option>
          <option value="neq">不等于</option>
          <option value="exists">存在</option>
          <option value="not_empty">非空</option>
          <option value="gte">大于等于</option>
          <option value="lte">小于等于</option>
          <option value="in">属于</option>
        </select>
        <input
          value={node.value}
          placeholder={node.operator === "in" ? "逗号分隔多个值" : "值"}
          onChange={(event) => markDirty(updateNode(draft.rules, node.id, () => ({ ...node, value: event.target.value })))}
        />
        <button type="button" onClick={() => void handleSaveSnippet(node)}>
          收藏条目
        </button>
        <button type="button" onClick={() => markDirty(removeNode(draft.rules, node.id))}>
          删除
        </button>
      </div>
    );
  }

  return (
    <section className="rule-center">
      <article className="panel rule-center__list">
        <div className="panel__heading">
          <div>
            <p className="eyebrow">Rule Center</p>
            <h2>规则包中心</h2>
          </div>
          <button
            disabled={isPending || isPendingGlobal}
            type="button"
            onClick={() => {
              setDraft(emptyDraft(signers));
              setIsNewDraft(true);
              setIsDirty(false);
              setSelectedPackageId("");
              setUsageReport(null);
              setDiffReport(null);
            }}
          >
            新建规则包
          </button>
        </div>
        <div className="task-list">
          {packages.map((item) => (
            <div className="task-row" key={item.id}>
              <strong>{item.name}</strong>
              <span>{item.status}</span>
              <small>当前修订 R{item.current_revision_no}</small>
              <small>
                最近编辑：{item.latest_editor_name ?? "未知"} / {formatTime(item.latest_edited_at ?? item.created_at)}
              </small>
              <small>{item.signature_outdated ? "待重新签名" : item.verification_status}</small>
              <button disabled={isPending || isPendingGlobal} type="button" onClick={() => void handleSelectPackage(item.id)}>
                查看
              </button>
              <button disabled={isPending || isPendingGlobal} type="button" onClick={() => void handleEditPackage(item.id)}>
                编辑
              </button>
            </div>
          ))}
        </div>

        <div className="result-block">
          <strong>模板库</strong>
          <label>
            模板名称
            <input value={templateName} onChange={(event) => setTemplateName(event.target.value)} />
          </label>
          <label>
            模板说明
            <input value={templateDescription} onChange={(event) => setTemplateDescription(event.target.value)} />
          </label>
          <button disabled={isPending || isPendingGlobal} type="button" onClick={() => void handleSaveTemplate()}>
            保存当前表达式为模板
          </button>
          {templates.map((template) => (
            <div className="asset-row" key={template.id}>
              <strong>{template.name}</strong>
              <small>{template.rules_count} 条规则</small>
              <button
                type="button"
                onClick={() => {
                  setDraft((current) => ({ ...current, rules: parseRules(template.rules) }));
                  setIsDirty(true);
                }}
              >
                套用模板
              </button>
            </div>
          ))}
        </div>

        <div className="result-block">
          <strong>条目库</strong>
          <small>当前插入目标：{activeGroupId === draft.rules.id ? "根分组" : activeGroupId || "未选择"}</small>
          {snippets.map((snippet) => (
            <div className="asset-row" key={snippet.id}>
              <strong>{snippet.name}</strong>
              <small>{snippet.description ?? "规则条目复用资产"}</small>
              <button
                type="button"
                onClick={() => {
                  const nextNode = convertNode(snippet.rule);
                  markDirty(appendChild(draft.rules, activeGroupId || draft.rules.id, nextNode));
                }}
              >
                插入条目
              </button>
            </div>
          ))}
        </div>
      </article>

      <article className="panel rule-center__editor">
        <div className="panel__heading">
          <div>
            <p className="eyebrow">Composer</p>
            <h2>{isNewDraft ? "新建规则包草稿" : selectedPackage?.name ?? "规则包编辑"}</h2>
          </div>
          <small>{isDirty ? "有未保存改动" : "已同步"}</small>
        </div>
        <form className="task-form" onSubmit={(event) => void handleSaveDraft(event)}>
          <label>
            规则包名称
            <input value={draft.name} onChange={(event) => { setDraft({ ...draft, name: event.target.value }); setIsDirty(true); }} />
          </label>
          <label>
            版本号
            <input value={draft.version} onChange={(event) => { setDraft({ ...draft, version: event.target.value }); setIsDirty(true); }} />
          </label>
          <label>
            规则包用途
            <input value={draft.purpose} onChange={(event) => { setDraft({ ...draft, purpose: event.target.value }); setIsDirty(true); }} />
          </label>
          <label>
            编辑人
            <input value={draft.editor_name} onChange={(event) => { setDraft({ ...draft, editor_name: event.target.value }); setIsDirty(true); }} />
          </label>
          <label>
            变更摘要
            <input value={draft.change_summary} onChange={(event) => { setDraft({ ...draft, change_summary: event.target.value }); setIsDirty(true); }} />
          </label>
          <label>
            备注
            <input value={draft.notes} onChange={(event) => { setDraft({ ...draft, notes: event.target.value }); setIsDirty(true); }} />
          </label>
          <label>
            签名人
            <select
              value={draft.signer_name}
              onChange={(event) => {
                const signer = signers.find((item) => item.signer_name === event.target.value);
                setDraft({
                  ...draft,
                  signer_name: event.target.value,
                  signature_ref: signer?.signature_ref ?? "",
                });
                setIsDirty(true);
              }}
            >
              <option value="">未设置</option>
              {signers.map((signer) => (
                <option key={signer.signer_name} value={signer.signer_name}>
                  {signer.signer_name}
                </option>
              ))}
            </select>
          </label>
          <label>
            签名引用
            <input value={draft.signature_ref} onChange={(event) => { setDraft({ ...draft, signature_ref: event.target.value }); setIsDirty(true); }} />
          </label>
          <label>
            签名值
            <input value={draft.signature} onChange={(event) => { setDraft({ ...draft, signature: event.target.value }); setIsDirty(true); }} />
          </label>

          <div className="result-block">
            <strong>组合规则编排</strong>
            <small>支持嵌套 AND / OR 分组，可将模板整套套用，也可将条目插入到选中的分组。</small>
            <div className="rule-tree">{renderNode(draft.rules)}</div>
          </div>

          <div className="task-row">
            <button disabled={isPending || isPendingGlobal} type="submit">
              保存草稿
            </button>
            <button disabled={isPending || isPendingGlobal || isNewDraft} type="button" onClick={() => void handleSubmitVerification()}>
              提交验签
            </button>
          </div>
        </form>
      </article>

      <article className="panel rule-center__history">
        <div className="panel__heading">
          <div>
            <p className="eyebrow">Governance</p>
            <h2>修订治理与回溯</h2>
          </div>
        </div>

        <div className="governance-stack">
          <div className="result-block">
            <strong>当前治理动作</strong>
            <label>
              审批人
              <input value={approverName} onChange={(event) => setApproverName(event.target.value)} />
            </label>
            <button disabled={isPending || isPendingGlobal || !selectedPackageId} type="button" onClick={() => void handleApprovePackage()}>
              审批通过当前修订
            </button>
            <label>
              废弃操作人
              <input value={deprecateOperator} onChange={(event) => setDeprecateOperator(event.target.value)} />
            </label>
            <label>
              废弃原因
              <input value={deprecateReason} onChange={(event) => setDeprecateReason(event.target.value)} />
            </label>
            <button
              disabled={isPending || isPendingGlobal || !selectedPackageId || selectedPackage?.status !== "approved"}
              type="button"
              onClick={() => void handleDeprecatePackage()}
            >
              废弃当前规则包
            </button>
            <button disabled={isPending || isPendingGlobal || !selectedPackageId} type="button" onClick={() => void handleDeletePackage()}>
              删除草稿
            </button>
          </div>

          <div className="result-block">
            <strong>修订历史</strong>
            <div className="task-list">
              {revisions.map((revision) => (
                <div className="task-row" key={revision.id}>
                  <strong>R{revision.revision_no}</strong>
                  <span>{revision.status}</span>
                  <small>{revision.change_summary ?? "无变更摘要"}</small>
                  <small>编辑人：{revision.editor_name ?? "未知"} / {formatTime(revision.created_at)}</small>
                  <small>
                    {revision.verification_status} / {revision.signature_outdated ? "待重新签名" : "签名最新"} / 引用 {revisionUsageMap.get(revision.id) ?? 0} 个任务
                  </small>
                </div>
              ))}
            </div>
          </div>

          <div className="result-block">
            <strong>修订差异对比</strong>
            <div className="diff-toolbar">
              <label>
                对比起点
                <select value={selectedDiffFromId} onChange={(event) => setSelectedDiffFromId(event.target.value)}>
                  {revisions.map((revision) => (
                    <option key={`from-${revision.id}`} value={revision.id}>
                      R{revision.revision_no} / {revision.status}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                对比终点
                <select value={selectedDiffToId} onChange={(event) => setSelectedDiffToId(event.target.value)}>
                  {revisions.map((revision) => (
                    <option key={`to-${revision.id}`} value={revision.id}>
                      R{revision.revision_no} / {revision.status}
                    </option>
                  ))}
                </select>
              </label>
              <button
                disabled={isPending || isPendingGlobal || !selectedPackageId || !selectedDiffFromId || !selectedDiffToId || selectedDiffFromId === selectedDiffToId}
                type="button"
                onClick={() => void loadRevisionDiff(selectedPackageId, selectedDiffFromId, selectedDiffToId)}
              >
                重新对比
              </button>
            </div>
            {diffReport ? (
              <>
                <div className="metric-strip">
                  <div className="metric">
                    <span>字段变化</span>
                    <strong>{String(diffReport.summary.field_change_count ?? 0)}</strong>
                  </div>
                  <div className="metric">
                    <span>结构变化</span>
                    <strong>{String(diffReport.summary.rule_change_count ?? 0)}</strong>
                  </div>
                  <div className="metric">
                    <span>派生关系</span>
                    <strong>{diffReport.based_on_match ? "直接派生" : "跨版本对比"}</strong>
                  </div>
                </div>
                <div className="task-list">
                  {diffReport.field_changes.map((change) => (
                    <div className="task-row" key={`${change.field}-${String(change.before)}-${String(change.after)}`}>
                      <strong>{change.field}</strong>
                      <span>字段</span>
                      <small>前值：{formatValue(change.before)}</small>
                      <small>后值：{formatValue(change.after)}</small>
                    </div>
                  ))}
                  {diffReport.rule_changes.map((change) => (
                    <div className="task-row" key={change.rule_key}>
                      <strong>{change.rule_key}</strong>
                      <span>{change.change_type}</span>
                      <small>前值：{formatValue(change.before_value)}</small>
                      <small>后值：{formatValue(change.after_value)}</small>
                    </div>
                  ))}
                </div>
              </>
            ) : (
              <p className="empty">选择两个不同修订后即可查看差异。</p>
            )}
          </div>

          <div className="result-block">
            <strong>引用回溯</strong>
            {usageReport ? (
              <>
                <div className="metric-strip">
                  <div className="metric">
                    <span>总引用任务</span>
                    <strong>{usageReport.total_task_count}</strong>
                  </div>
                  <div className="metric">
                    <span>当前修订引用</span>
                    <strong>{usageReport.current_revision_task_count}</strong>
                  </div>
                  <div className="metric">
                    <span>历史修订引用</span>
                    <strong>{usageReport.historical_revision_task_count}</strong>
                  </div>
                </div>
                <div className="task-list">
                  {usageReport.tasks.length ? (
                    usageReport.tasks.map((task) => (
                      <div className="task-row" key={task.task_id}>
                        <strong>{task.task_name}</strong>
                        <span>{task.output_policy}</span>
                        <small>任务状态：{task.task_status} / 创建时间：{formatTime(task.created_at)}</small>
                        <small>
                          引用修订：{task.referenced_revision_no ? `R${task.referenced_revision_no}` : "未绑定"} / {task.is_current_revision ? "当前版" : "历史版"}
                        </small>
                      </div>
                    ))
                  ) : (
                    <p className="empty">当前规则包尚未被任何任务引用。</p>
                  )}
                </div>
              </>
            ) : (
              <p className="empty">引用关系加载中。</p>
            )}
          </div>
        </div>
      </article>
    </section>
  );
}
