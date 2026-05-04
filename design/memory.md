# 记忆窗口

> 跨会话持久化的问题与结论记录。仅记录决策结果，不含中间推导过程。

## 项目概况

- **目标**：构建一个类似 Claude Code 的 AI 编程助手 CLI
- **技术栈**：Node.js/TypeScript，npm 公开发布，纯本地操作
- **参考资料**：《深入理解 Claude Code 源码》（516页，27章），已转为 markdown 存放在 `docs/`
- **参考来源**：https://sawzhang.github.io/deep-dive-claude-code/

## 已确定的技术选型

| 决策项 | 选择 | 备注 |
|--------|------|------|
| 运行时 | Node.js/TypeScript | 非 Bun，构建更简单 |
| TUI 框架 | React + Ink | 参考 Claude Code 架构 |
| CLI 框架 | Commander.js | |
| 类型验证 | Zod | |
| 核心模式 | AsyncGenerator 管道 | 流式 query→tool→result |
| 分发方式 | npm 公开发布 | |

## 已完成事项

| 事项 | 结果 |
|------|------|
| PDF 转 markdown | 27章+1完整版已存入 `docs/`，使用网页版抓取（质量远优于 PDF 解析） |
| MinerU 安装 | 已安装在 kg-rag conda 环境，但 pipeline 后端依赖冲突严重，暂不可用 |
| CLAUDE.md | 已创建，含语言要求（必须中文）、项目目标、参考文档索引、架构决策 |
| 设计文档目录 | `design/` 目录已创建 |

## Claude Code 架构要点（从文档提取）

- **五层架构**：CLI/UI 层 → 查询引擎层 → 工具系统层 → Agent 系统层 → 协议与服务层
- **查询引擎**：QueryEngine 类管理对话生命周期，`submitMessage()` 返回 AsyncGenerator，核心 `query()` 函数是 API 调用+工具执行的交替循环
- **工具系统**：40+ 工具动态注册，Tool<I,O,P> 泛型接口，支持并发安全/串行执行分区
- **Agent 系统**：Markdown frontmatter 声明式定义 Agent，支持 Fork（继承父代上下文）和 SubAgent（空白上下文）
- **权限模型**：六层安全模式，Bash 命令语义分析，PermissionResult 判别联合类型
- **状态管理**：34 行 Store 撑起 450 行 AppState
- **性能优化**：并行预取、三层 Memoization、编译时 DCE（feature flag）
- **构建**：Bun `bun build --compile` 打包为单文件二进制

## 待讨论

- 产品功能范围：MVP 需要哪些功能？
- PRD 定义
- 软件总体架构设计
- 各模块详细架构
