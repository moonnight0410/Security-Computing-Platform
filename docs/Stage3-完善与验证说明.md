# Stage 3 完善与验证说明

## 1. 当前阶段

当前阶段：Stage 3，完善与验证阶段。

本阶段目标是在 Stage 2 本域核心能力基础上补齐可运行性、可验证性、错误处理、日志审计和本地部署脚本。

## 2. 完成内容

| 类别 | 完成内容 |
| --- | --- |
| 错误处理 | 上传类型限制、空文件检查、CSV 编码错误提示、规则包审批人校验、执行失败审计 |
| 日志 | 新增 `workspace/logs/app.log` 滚动日志 |
| 审计 | 新增 `workspace/audit/audit-log.jsonl` 追加式审计文件 |
| 状态兼容 | 对旧 JSON 状态补默认字段，迁移旧规则包状态 |
| 测试 | 新增执行服务单元测试，覆盖真实联查数据形态、阈值抑制、泄露防护和失败关闭 |
| 部署脚本 | 新增后端启动、前端启动、停止服务、本地检查脚本，并显式检查外部命令退出码 |
| 文档 | 更新 README 并新增 Stage 3 完成报告 |

## 3. 新增脚本

| 脚本 | 用途 |
| --- | --- |
| `scripts/start-backend.ps1` | 启动后端服务并验证健康检查 |
| `scripts/start-frontend.ps1` | 启动前端开发服务 |
| `scripts/stop-local.ps1` | 停止本地 8000 和 5173 端口服务 |
| `scripts/run-stage3-checks.ps1` | 执行后端编译、后端测试和前端构建 |

## 4. 新增测试

| 文件 | 验证点 |
| --- | --- |
| `backend/tests/test_execution.py` | 验证聚合统计满足阈值时输出，低于阈值时抑制；验证结果不包含对象级原始值；验证结论草稿、执行回执、未映射分组和 CSV 表头异常 |
| `docs/Stage3-测试样例说明.md` | 说明真实样例数据结构、测试用例、预期结果和运行方式 |

## 5. 数据边界

Stage 3 没有放宽任何数据边界，仍然保持：

- 不输出原始数据。
- 不输出加密数据。
- 不输出哈希数据。
- 不输出去标识摘要。
- 不输出派生主键 / 子键。
- 不输出对象级明细。
- 不输出低于阈值的聚合分组。

## 6. 本地验证命令

```powershell
.\scripts\run-stage3-checks.ps1
```

也可以分开执行：

```powershell
python -m compileall backend\app
cd backend
.\.venv\Scripts\python.exe -m unittest discover -s tests
cd ..\frontend
npm run build
```

## 7. 当前限制

- 尚未切换 SQLite。
- 尚未实现 Excel 自动解析。
- 尚未实现规则表达式解析。
- 尚未实现完整结论声明审核流。
- 尚未实现正式导出审批。
- 审计文件为追加式 JSONL，尚未实现链式签名或防篡改。

## 8. 验证结果

已执行：

```powershell
.\scripts\run-stage3-checks.ps1
```

结果：通过。

检查内容：

- 后端编译检查通过。
- 后端单元测试通过，`9` 个测试用例成功。
- 前端生产构建通过。
