# 政府部门联查数据计算单机系统

当前阶段：Stage 8，输出文件归档封存、批量管理与正式公私钥验签阶段。

当前背景约束已经更新为：所有数据只能在本域内处理，原始数据、加密数据、哈希数据、去标识数据、派生主键 / 子键和对象级明细结果均不得出域。因此，本项目当前定位不是“跨域交换数据后联查”，而是“规则包流转 + 本域本地计算 + 本域留痕 + 执行回执 + 经授权结论声明 + 满足阈值的聚合统计”。

当前已确认治理选项为 `BBB`：

- 聚合统计：仅允许单维粗粒度分组。
- 结论声明：执行人与审核人分离。
- 规则包：签名引用 + 单人审批导入。

## 目录结构

```text
backend/      FastAPI 后端骨架
frontend/     Vite React 前端骨架
docs/         阶段说明文档
workspace/    本域本地工作目录
```

## Stage 8 已完成

- 规则包验签从演示 HMAC 升级为 RSA 公私钥签名与公钥验签。
- 新增 `scripts/bootstrap-stage8-keys.ps1`，本地生成受信任签名人和归档封存中心密钥。
- 规则包支持批量验签与批量审批。
- 输出文件支持多文件归档封存，生成归档清单、签名文件和验签报告。
- 新增归档报告重新验签接口，便于复核封存完整性。
- workspace 新增归档目录和本地密钥目录，并默认忽略运行态文件。

Stage 8 验证脚本：

```powershell
.\scripts\run-stage8-checks.ps1
```

## 后端启动

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
.\.venv\Scripts\uvicorn app.main:app --host 127.0.0.1 --port 8000
```

也可以使用本地脚本：

```powershell
.\scripts\start-backend.ps1
```

健康检查：

```text
http://127.0.0.1:8000/api/health
```

本域边界策略：

```text
http://127.0.0.1:8000/api/domain-policy
```

## 前端启动

```powershell
cd frontend
npm install
npm run dev
```

也可以使用本地脚本：

```powershell
.\scripts\start-frontend.ps1
```

访问地址：

```text
http://127.0.0.1:5173
```

## Stage 1 已完成

- 本域数据导入与字段画像雏形。
- 不含数据的规则包登记接口与页面。
- 本域任务草稿接口与页面。
- 本域输出策略雏形：`local_only`、`execution_receipt`、`manual_assertion`、`aggregate_summary`。
- 聚合统计最小阈值控制，当前默认阈值为 `10`。
- 聚合统计单维分组限制：`department`、`matter_type`、`month`。
- 规则包签名引用与审批通过后方可用于任务。
- 本域审计记录与工作目录规划。
- 出域边界策略接口和前端提示。

## Stage 1 边界

- 不实现跨域数据交换。
- 不实现哈希集合、密文集合、去标识键交换。
- 不实现对象级结果导出。
- 不实现完整算子库、规则引擎、主键 / 子键派生和去标识匹配执行。
- 不实现聚合统计实际计算，只实现输出策略和阈值边界。
- 不实现结论声明实际审批流，只固化为双人流程边界。

## Stage 2 已完成

- 字段映射持久化：主键、子键、敏感字段和聚合分组字段。
- 本域任务执行：读取本域 CSV，在内存中完成主键 / 子键派生和去标识摘要。
- 基础算子库接口：标准化、键派生、去标识、聚合阈值、执行回执。
- 结果摘要查看：只返回计数、重复组数量、回执、待审核结论和阈值后聚合统计。
- 本域安全边界：不返回原始值、派生键、去标识摘要和对象级明细。

## Stage 3 已完成

- 后端错误处理增强：上传类型限制、空文件检查、CSV 编码错误提示、规则包审批人校验、执行失败审计。
- 本地日志增强：写入 `workspace/logs/app.log`，支持滚动日志。
- 审计落盘增强：除 JSON 状态外，追加写入 `workspace/audit/audit-log.jsonl`。
- 状态兼容增强：对旧阶段遗留状态补默认字段并迁移旧规则包状态。
- 本地测试：新增 `backend/tests/test_execution.py`，验证阈值输出和小样本抑制。
- 部署脚本：新增后端启动、前端启动、停止服务、Stage 3 检查脚本。

## Stage 4 已完成

- 本地状态存储从 JSON 兼容层升级为 SQLite：`workspace/config/app-state.sqlite3`。
- 旧 JSON 状态自动迁移到 SQLite。
- 规则包支持最小规则表达式：字段、操作符、值。
- 任务执行支持规则表达式统计：通过数量、失败数量、未知数量。
- 前端规则包登记支持录入一个规则表达式。
- 测试集扩展到真实联查样例，覆盖聚合统计、阈值抑制、规则表达式和泄露防护。

## Stage 5 已完成

- 新增安全输出申请、审批和输出包预览。
- 输出类型支持执行回执、结论声明、聚合统计。
- 审批人与申请人不能相同。
- 未审批通过的申请不能生成输出包。
- 输出包只包含安全摘要，不包含对象级明细、派生键或去标识摘要。
- 审计 JSONL 增加 `previous_hash` 和 `entry_hash` 链式哈希字段。

## 本地检查

```powershell
.\scripts\run-stage5-checks.ps1
```

该脚本会执行：

- 后端编译检查。
- 后端单元测试。
- 前端生产构建。

## 停止服务

```powershell
.\scripts\stop-local.ps1
```
