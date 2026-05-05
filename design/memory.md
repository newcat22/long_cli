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
| PRD v1 | `design/prd-v1.md` — MVP 范围：CLI启动、用户输入、模型流式回复、会话管理、退出、API Key配置 |
| 架构 v1 | `design/architecture-v1.md` — 四模块架构（CLI→REPL→查询引擎→API客户端），含模块图/技术图/数据流图/流程图/文件规划 |

## 已确定的架构决策

| 决策项 | 选择 | 原因 |
|--------|------|------|
| MVP 范围 | 最简 REPL：启动→输入→流式回复→退出 | 先跑通核心循环，再迭代加工具/Agent |
| 模块划分 | 四模块：CLI入口、REPL界面、查询引擎、API客户端 | 职责清晰，依赖单向 |
| 核心模式 | AsyncGenerator 事件流 | query→yield→render，后续加工具调用无需重构 |
| 会话模型 | 每次启动=新会话，内存中维护 messages[] | MVP 不做持久化 |
| 串行执行 | 一次只有一个请求 | 先串行，AsyncGenerator 接口已为并行留空间 |

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

- 具体实现：初始化项目、安装依赖、编写代码
- 各模块详细架构（后续迭代）
- 工具系统设计（v2）
- Agent 系统设计（v3）
