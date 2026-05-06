import { FormEvent, useEffect, useMemo, useRef, useState } from "react";

import {
  approveRulePackageCenter,
  beginRulePackageEdit,
  createRulePackageDraft,
  deleteRulePackage,
  deprecateRulePackage,
  getRulePackageRevisions,
  saveRulePackageDraft,
  submitRulePackageVerification,
} from "./api";
import type { RulePackage, RulePackageRevision, TrustedSignerInfo } from "./types";

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
  rules: Array<{
    field: string;
    operator: "eq" | "neq" | "exists" | "not_empty" | "gte" | "lte" | "in";
    value: string;
  }>;
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
    rules: [{ field: "benefit_status", operator: "eq", value: "正常" }],
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
    rules: revision.rules.length
      ? revision.rules.map((rule) => ({
          field: String(rule.field ?? ""),
          operator: (rule.operator as RuleDraft["rules"][number]["operator"]) ?? "eq",
          value: Array.isArray(rule.value) ? rule.value.join(",") : String(rule.value ?? ""),
        }))
      : [{ field: "", operator: "eq", value: "" }],
  };
}

function serializeRules(draft: RuleDraft): Array<Record<string, unknown>> {
  return draft.rules
    .filter((rule) => rule.field.trim())
    .map((rule) => ({
      field: rule.field.trim(),
      operator: rule.operator,
      value:
        rule.operator === "exists" || rule.operator === "not_empty"
          ? null
          : rule.operator === "in"
            ? rule.value
                .split(",")
                .map((item) => item.trim())
                .filter(Boolean)
            : rule.value.trim(),
    }));
}

export default function RulePackageCenter({ packages, signers, isPendingGlobal, onNotice, onRefresh }: Props) {
  const [selectedPackageId, setSelectedPackageId] = useState<string>("");
  const [revisions, setRevisions] = useState<RulePackageRevision[]>([]);
  const [draft, setDraft] = useState<RuleDraft>(() => emptyDraft(signers));
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
    if (!selectedPackageId) {
      setRevisions([]);
      return;
    }
    getRulePackageRevisions(selectedPackageId)
      .then((items) => {
        setRevisions(items);
      })
      .catch((error: unknown) => {
        onNotice(error instanceof Error ? error.message : "规则包修订加载失败");
      });
  }, [onNotice, selectedPackageId]);

  useEffect(() => {
    const handlePageHide = () => {
      if (!dirtyRef.current) {
        return;
      }
      const currentDraft = draftRef.current;
      const currentPackageId = selectedPackageIdRef.current;
      if (isNewDraftRef.current) {
        void createRulePackageDraft({
          ...currentDraft,
          rules: serializeRules(currentDraft),
        });
        return;
      }
      if (!currentPackageId) {
        return;
      }
      void saveRulePackageDraft(currentPackageId, {
        ...currentDraft,
        rules: serializeRules(currentDraft),
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

  async function reloadRevisions(packageId: string) {
    const items = await getRulePackageRevisions(packageId);
    setRevisions(items);
  }

  async function persistDraft(autoSaved = false) {
    const payload = {
      ...draft,
      rules: serializeRules(draft),
      auto_saved: autoSaved,
    };
    if (isNewDraft) {
      const nextPackage = await createRulePackageDraft(payload);
      await onRefresh();
      await reloadRevisions(nextPackage.id);
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
    await reloadRevisions(selectedPackageId);
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
        // best effort auto-save before switch
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
      await reloadRevisions(rulePackageId);
      onNotice(selectedPackage?.status === "approved" ? "已自动创建新的修订草稿" : `进入修订 R${revision.revision_no} 编辑`);
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
      await reloadRevisions(selectedPackageId);
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
      await reloadRevisions(selectedPackageId);
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
      await reloadRevisions(selectedPackageId);
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

  function updateRule(index: number, patch: Partial<RuleDraft["rules"][number]>) {
    setDraft((current) => ({
      ...current,
      rules: current.rules.map((rule, ruleIndex) => (ruleIndex === index ? { ...rule, ...patch } : rule)),
    }));
    setIsDirty(true);
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
              <small>最近编辑：{item.latest_editor_name ?? "未知"} / {item.latest_edited_at ?? item.created_at}</small>
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
      </article>

      <article className="panel rule-center__editor">
        <div className="panel__heading">
          <div>
            <p className="eyebrow">Editor</p>
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
            <strong>规则条目</strong>
            {draft.rules.map((rule, index) => (
              <div className="rule-editor-row" key={`rule-${index}`}>
                <input value={rule.field} placeholder="字段" onChange={(event) => updateRule(index, { field: event.target.value })} />
                <select value={rule.operator} onChange={(event) => updateRule(index, { operator: event.target.value as RuleDraft["rules"][number]["operator"] })}>
                  <option value="eq">等于</option>
                  <option value="neq">不等于</option>
                  <option value="exists">存在</option>
                  <option value="not_empty">非空</option>
                  <option value="gte">大于等于</option>
                  <option value="lte">小于等于</option>
                  <option value="in">属于</option>
                </select>
                <input
                  value={rule.value}
                  placeholder={rule.operator === "in" ? "逗号分隔多个值" : "值"}
                  onChange={(event) => updateRule(index, { value: event.target.value })}
                />
                <button
                  disabled={draft.rules.length <= 1}
                  type="button"
                  onClick={() => {
                    setDraft((current) => ({
                      ...current,
                      rules: current.rules.filter((_, ruleIndex) => ruleIndex !== index),
                    }));
                    setIsDirty(true);
                  }}
                >
                  删除
                </button>
              </div>
            ))}
            <button
              type="button"
              onClick={() => {
                setDraft((current) => ({
                  ...current,
                  rules: [...current.rules, { field: "", operator: "eq", value: "" }],
                }));
                setIsDirty(true);
              }}
            >
              新增规则
            </button>
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
            <p className="eyebrow">History</p>
            <h2>修订与治理</h2>
          </div>
        </div>
        <label>
          审批人
          <input value={approverName} onChange={(event) => setApproverName(event.target.value)} />
        </label>
        <button
          disabled={isPending || isPendingGlobal || !selectedPackageId}
          type="button"
          onClick={() => void handleApprovePackage()}
        >
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
        <button
          disabled={isPending || isPendingGlobal || !selectedPackageId}
          type="button"
          onClick={() => void handleDeletePackage()}
        >
          删除草稿
        </button>
        <div className="task-list">
          {revisions.map((revision) => (
            <div className="task-row" key={revision.id}>
              <strong>R{revision.revision_no}</strong>
              <span>{revision.status}</span>
              <small>{revision.change_summary ?? "无变更摘要"}</small>
              <small>编辑人：{revision.editor_name ?? "未知"} / {revision.created_at}</small>
              <small>{revision.verification_status} / {revision.signature_outdated ? "待重新签名" : "签名最新"}</small>
            </div>
          ))}
        </div>
      </article>
    </section>
  );
}
