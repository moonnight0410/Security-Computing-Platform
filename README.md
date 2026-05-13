# 政府部门联查数据计算单机系统

当前阶段：`Stage 11`

当前状态：规则模板复用、规则条目复用、嵌套 `AND / OR` 组合规则编排、任务与输出治理看板、蓝白主题前端工作台已完成。

## 项目简介

这是一个面向“本域数据不出域”约束设计的单机本地系统。项目目标不是跨部门交换原始数据，而是在受控环境内完成规则包治理、本地数据计算、安全输出、审计留痕和归档验签。

项目当前定位：

- 数据只在本地导入和处理
- 规则包可验签、审批、修订和追溯
- 结果只输出安全摘要，不输出对象级明细
- 输出过程具备审批、审计、归档和复核闭环

## 背景约束

本项目默认遵循以下边界：

- 原始数据不得出域
- 加密数据、哈希数据、去标识数据不得直接出域
- 派生主键、子键和对象级结果不得直接出域
- 允许的输出形式仅限执行回执、经审核结论声明、满足阈值的聚合统计

因此，本项目解决的是“本地计算与安全治理”问题，而不是“跨域数据汇聚”问题。

## 技术栈

- 后端：`FastAPI`
- 前端：`React 19`
- 构建：`Vite + TypeScript`
- 本地状态：`SQLite`
- 审计链：`JSONL + 链式哈希`

## 目录结构

```text
backend/      后端接口、服务逻辑、模型与测试
frontend/     前端页面、API 接入、类型与样式
docs/         设计方案、阶段报告、说明文档
scripts/      启动、停止、检查、签名辅助脚本
workspace/    本地运行态目录
```

`workspace/` 主要包含：

```text
workspace/imports/    导入数据落盘目录
workspace/exports/    输出文件目录
workspace/archives/   归档封存目录
workspace/audit/      审计链目录
workspace/logs/       本地日志目录
workspace/config/     本地状态库与密钥目录
```

## 当前已实现的核心能力

截至 `Stage 11`，系统已具备以下主线能力：

- 本地导入 `CSV`、`XLSX`、`XLS`
- 字段画像分析与字段映射配置
- 本地任务创建、执行与结果摘要生成
- 输出策略控制：`local_only`、`execution_receipt`、`manual_assertion`、`aggregate_summary`
- 聚合统计最小阈值控制，默认阈值为 `10`
- 规则表达式录入与执行统计
- 规则树组合编排，支持嵌套 `AND / OR`
- 规则模板复用与规则条目复用
- 规则包验签、审批、批量处理、修订快照与差异对比
- 任务对规则包修订版本的绑定与回溯
- 输出申请、审批、输出包预览和本地落盘
- 多文件归档封存、归档验签与复核报告
- 审计链写入与完整性校验
- 任务与输出治理看板

## Stage 10 与 Stage 11 重点成果

### Stage 10

- 规则包修订差异对比
- 历史修订引用回溯
- 当前修订与历史修订任务引用统计

### Stage 11

- 规则模板库：支持保存整套规则树并复用
- 规则条目库：支持保存单条规则并插入到指定分组
- 规则树引擎：支持 `group` / `rule` 两类节点和递归求值
- 嵌套 `AND / OR` 组合编排
- 治理看板：展示任务、输出申请、输出文件、归档、规则包、待审结论与审计总量
- 前端蓝白主题统一

## 关键接口

当前后端已提供以下重点接口：

- `GET /api/health`
- `GET /api/domain-policy`
- `GET /api/rule-templates`
- `POST /api/rule-templates`
- `GET /api/rule-snippets`
- `POST /api/rule-snippets`
- `GET /api/governance/dashboard`

## 分阶段进度

| 阶段 | 主要成果 | 状态 |
| --- | --- | --- |
| Stage 1 | 基础骨架、本域边界、工作台雏形 | 已完成 |
| Stage 2 | 字段映射、本地执行、摘要结果 | 已完成 |
| Stage 3 | 错误处理、日志、审计落盘、检查脚本 | 已完成 |
| Stage 4 | SQLite 状态存储、规则表达式增强 | 已完成 |
| Stage 5 | 输出申请、审批、预览、审计防篡改 | 已完成 |
| Stage 6 | 输出包落盘、输出文件记录、审计链校验 | 已完成 |
| Stage 7 | 规则包验签与结论声明审核 | 已完成 |
| Stage 8 | RSA 公私钥验签、归档封存、归档复核 | 已完成 |
| Stage 9 | 规则包中心、修订快照、编辑治理 | 已完成 |
| Stage 10 | 修订差异对比、历史引用回溯 | 已完成 |
| Stage 11 | 模板复用、组合规则编排、治理看板、蓝白主题 | 已完成 |

## 本地启动

### 后端

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
.\.venv\Scripts\uvicorn app.main:app --host 127.0.0.1 --port 8000
```

或使用脚本：

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

### 前端

```powershell
cd frontend
npm install
npm run dev
```

或使用脚本：

```powershell
.\scripts\start-frontend.ps1
```

访问地址：

```text
http://127.0.0.1:5173
```

### 停止本地服务

```powershell
.\scripts\stop-local.ps1
```

## 本地检查

当前推荐执行 `Stage 11` 检查脚本：

```powershell
.\scripts\run-stage11-checks.ps1
```

该脚本会执行：

- 后端编译检查
- 后端单元测试
- 前端 TypeScript 类型检查
- 前端生产构建

## 当前完成度

如果以“是否具备演示和验收基础”为标准，当前项目已经达到较高完成度：

- 业务主链已打通
- 本地安全边界已落地
- 审计与归档机制已成体系
- 规则包治理链路已成型
- 规则资产已支持模板化复用
- 任务与输出治理信息已可看板化审阅

下一步仍可继续扩展的方向主要包括：

- 规则模板参数化实例化
- 更强的规则包创建器与可视化编辑体验
- 更细的治理审批流配置
- 更强的批量规则包管理能力

## 文档导航

- [项目介绍与成果进度说明](docs/项目介绍与成果进度说明.md)
- [Stage10-工作完成报告](docs/Stage10-工作完成报告.md)
- [Stage10-规则包差异对比与引用回溯说明](docs/Stage10-规则包差异对比与引用回溯说明.md)
- [Stage11-工作完成报告](docs/Stage11-工作完成报告.md)
- [Stage11-规则模板复用与组合规则编排说明](docs/Stage11-规则模板复用与组合规则编排说明.md)
- [Stage9-实际规则包样例](docs/Stage9-实际规则包样例.md)
