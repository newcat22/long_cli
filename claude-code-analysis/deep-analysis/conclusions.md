# Claude Code 深度分析结论

> 对话中得出的关键结论，持续更新。

---

## 1. 子 Agent 的实现机制（2026-05-05）

Claude Code 的子 Agent 是**主进程内的子图（in-process sub-graph）**，不是子进程，也不是 A2A 独立进程。

### 核心机制

- 所有子 Agent 运行在同一个 Node.js 进程内
- 通过 `createSubagentContext()` 创建隔离的执行上下文（独立的 AbortController、文件状态缓存、内容替换状态、拒绝追踪）
- `ToolUseContext` 子代和父代使用不同 Context 对象，但共享同一个 React 状态树根节点
- 双通道状态更新：`setAppState`（子代隔离）vs `setAppStateForTasks`（穿透到根存储）

### 两种子 Agent 模式


| 模式              | 触发方式                               | 上下文           | 模型              | 典型用途  |
| --------------- | ---------------------------------- | ------------- | --------------- | ----- |
| Typed Sub-Agent | `subagent_type=Explore/Plan/Guide` | 空白，只接收 prompt | 各 Agent 自定义     | 专业化任务 |
| Fork Sub-Agent  | 省略 `subagent_type`                 | 继承父代完整对话历史    | `inherit`（必须一致） | 并行处理  |


### 关键设计

- **Fork 的 prompt cache 共享**：固定占位文本 `"Fork started — processing in background"` 让所有并行 Fork 共享 API 请求前缀，只有 directive 不同
- **Sidechain transcript**：子 Agent 对话独立持久化，支持跨中断恢复（Resume 机制）
- `**buildForkedMessages()`**：字节精确构建消息，确保缓存前缀一致
- **防递归**：`isInForkChild()` 检测 `<fork-boilerplate>` 标签，禁止 Fork 子代再次 Fork
- **权限冒泡**：Fork 子代 `permissionMode: 'bubble'`，权限请求冒泡到父代终端

### 不是子进程的证据

- 无 `child_process.fork()` 或 `spawn()` 调用
- 子 Agent 共享主进程 React 状态树
- 通信通过内存通知（`task-notification`）和直接函数调用（`resumeAgentBackground`），无 HTTP/gRPC
- 唯一的跨进程边界是 MCP 服务器（stdio/SSE）和 Bash 工具（shell 命令），属于工具层面

### 与其他方案的对比


| 方案                     | 进程模型    | 通信方式           | 代表                        |
| ---------------------- | ------- | -------------- | ------------------------- |
| Claude Code            | 同进程子图   | 内存通知 + 函数调用    | `createSubagentContext()` |
| LangGraph 子图           | 同进程子图   | 内存状态传递         | `StateGraph`              |
| A2A                    | 独立进程    | HTTP/gRPC      | Google A2A 协议             |
| OpenClaw session_spawn | 独立进程/会话 | session 工具套件通信 | `session_spawn`           |


