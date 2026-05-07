# Claude Code 深度分析结论

> 对话中得出的关键结论，持续更新。

---

## 1. 子 Agent 的实现机制（2026-05-05，修订 2026-05-06）

Claude Code 的子 Agent 是**主进程内的子图（in-process sub-graph）**，不是子进程，也不是 A2A 独立进程。

### 核心抽象

所有子 Agent（无论内置、自定义还是 Fork）都统一使用 `AgentDefinition` 类型抽象。区别只在于**定义来源和上下文来源**：
- 内置 Agent：`BuiltInAgentDefinition`，代码中硬编码
- 自定义 Agent：`CustomAgentDefinition`，从 `.claude/agents/*.md` 加载
- 插件 Agent：`PluginAgentDefinition`，从插件加载
- Fork：不是独立的 Agent 类型，而是一种**动作模式**——复用 `FORK_AGENT` 这个定义，但触发方式不同

### 两种运行模式

| 模式 | 触发方式 | 上下文来源 | 模型 | 典型场景 |
|------|---------|----------|------|---------|
| Typed Agent | `subagent_type=Explore/Plan/自定义名` | 空白，只接收 prompt 参数 | 各 Agent 定义的 model 字段 | 专业化任务 |
| Fork | 省略 `subagent_type` | 继承父代完整对话历史 | `inherit`（必须一致） | 并行处理已知上下文的任务 |

**Fork 的本质是上下文复用**：主 Agent 已有完整对话上下文，直接派生子 Agent 去并行干活，不需要在 prompt 中重述背景。通过 `buildForkedMessages()` 构建字节一致的消息前缀，使多个并行 Fork 共享 prompt cache，只有最后的 directive 文本块不同。

### 自定义 Agent 能力（纠正：不只是 prompt）

用户在 `.claude/agents/*.md` 中可定义的字段远不止 prompt（Markdown body），frontmatter 支持完整的配置：

```yaml
---
name: my-agent
description: "何时使用此 Agent"
tools: [Glob, Grep, Read, Bash]          # 工具白名单
disallowedTools: [Write, Edit]            # 工具黑名单
model: inherit                            # 模型选择
effort: high                              # 推理深度
permissionMode: dontAsk                   # 权限模式
maxTurns: 50                              # 最大轮次
background: true                          # 后台运行
isolation: worktree                       # Git worktree 隔离
memory: project                           # 持久化记忆范围
skills: [simplify]                        # 预加载 Skill
mcpServers: [github, {name: lint, command: node, args: [...]}]  # Agent 专属 MCP
hooks: { PreToolUse: [...] }              # 会话级钩子
color: blue                               # UI 颜色
---
Agent 的系统提示词写在这里（Markdown body）
```

工具挂载方式：
- `tools` 字段指定白名单（`['*']` 表示继承父级全部可用工具）
- `disallowedTools` 字段指定黑名单
- 实际可用工具经过多层过滤：全局禁止列表 → 自定义 Agent 额外禁止列表 → tools 白名单 → disallowedTools 黑名单
- MCP 工具通过 `mcpServers` 字段声明，支持引用已有服务器名或内联定义新服务器
- 启用 memory 时自动注入 Read/Edit/Write 工具

### Fork 的完整细节

**Fork 的 prompt 和工具集**：Fork 子代直接复用父代的一切，没有自己的独立配置：
- **系统提示词**：通过 `override.systemPrompt` 传递父代 `renderedSystemPrompt`（字节级复制），`FORK_AGENT.getSystemPrompt = () => ''` 永远不会被调用
- **工具集**：直接用 `toolUseContext.options.tools`（父代当前工具列表），配合 `useExactTools: true` 跳过 `resolveAgentTools()` 过滤
- **模型**：`inherit`（必须一致，否则 prompt cache 失效）
- **对话上下文**：`buildForkedMessages()` 构建父代历史 + 占位 tool_result + directive
- **约束**：`<fork-boilerplate>` 强制子代结构化输出（Scope/Result/Key files/Issues），禁止对话、提问、元评论

**Fork 不能再 Fork**：两层防护（AgentTool.tsx:332）：
1. 主检查：`querySource === 'agent:builtin:fork'`，设到 context.options 上，autocompact 压缩也不会丢失
2. 兜底检查：`isInForkChild()` 扫描消息历史中 `<fork-boilerplate>` 标签
3. 违规时抛出 `Error('Fork is not available inside a forked worker...')`

**Fork 完成后的流转**：
1. `finalizeAgentTool()` 提取子 Agent 最后一条 assistant 消息的文本内容
2. 可选地 `classifyHandoffIfNeeded()` 安全审查（仅 `auto` 权限模式），可疑操作追加 `SECURITY WARNING`
3. `enqueueAgentNotification()` 往全局消息队列推入 `task-notification`
4. 父 Agent 的 query 循环下一轮迭代从队列取出，转为 attachment 消息注入到父 Agent 对话
5. 父 Agent（LLM）自己判断结果是否可接受——**没有硬编码的验收逻辑**

### 用户请求到子 Agent 执行的完整链路

```
用户终端输入
    │
    ▼
REPL.tsx (React/Ink 终端 UI，用户按回车提交)
    │
    ▼
handlePromptSubmit() (输入路由入口)
    │
    ▼
processUserInput() (判断输入类型)
    ├─ /xxx → processSlashCommand
    ├─ !xxx → processBashCommand
    └─ 普通文本 → processTextPrompt  ← 大多数情况
    │
    │  (构造 UserMessage + AttachmentMessages)
    ▼
onQueryImpl() (构建 systemPrompt + userContext，调用 query())
    │
    ▼
query() → queryLoop()  (AsyncGenerator 驱动的循环)
    │
    │  每一轮：
    │  1. 消息发到 Anthropic API
    │  2. 拿到 LLM 响应
    │  3. 解析响应中的 tool_use 块
    │  4. 执行工具，拿 tool_result
    │  5. 追加到消息，回到第1步
    │
    │  LLM 决定调用 Agent 工具
    ▼
AgentTool.call() (路由逻辑，AgentTool.tsx:322)
    │
    ├─ subagent_type 有值 → 从 activeAgents 查找 → selectedAgent = found
    ├─ subagent_type 省略 + FORK_SUBAGENT 开启 → isForkPath → FORK_AGENT
    └─ subagent_type 省略 + FORK_SUBAGENT 关闭 → GENERAL_PURPOSE_AGENT
    │
    ├─ Fork 路径: 复用父代 systemPrompt + 父代 tools + 父代对话历史 + directive
    └─ Typed 路径: Agent 自己的 systemPrompt + workerTools + 空白上下文 + prompt
    │
    ▼
runAgent() → createSubagentContext() → 子 Agent 的 query() 循环
    │
    ├─ 同步模式: 结果直接返回给父 Agent
    └─ 异步模式: task-notification 入队 → 父 Agent 下一轮消费
```

**关键洞察：Agent 选择没有规则引擎，完全依赖 LLM 推理**。Agent 工具的描述（prompt.ts）会列出所有可用 Agent 及其 `whenToUse`，LLM 根据用户请求自行判断调用哪个 `subagent_type` 或走 Fork。Fork 开启时还有额外指导（"中间工具输出不值得保留在上下文中时 Fork 自己"）。

### 关键设计

- **Fork 的 prompt cache 共享**：固定占位文本 `"Fork started — processing in background"` 让所有并行 Fork 共享 API 请求前缀，只有 directive 不同
- **Sidechain transcript**：子 Agent 对话独立持久化，支持跨中断恢复（Resume 机制）
- **`buildForkedMessages()`**：字节精确构建消息，确保缓存前缀一致
- **防递归**：`isInForkChild()` 检测 `<fork-boilerplate>` 标签，禁止 Fork 子代再次 Fork
- **权限冒泡**：Fork 子代 `permissionMode: 'bubble'`，权限请求冒泡到父代终端
- **优先级覆盖**：built-in → plugin → user → project → flag → managed，后者同名覆盖前者
- **`createSubagentContext()`**：默认隔离（AbortController、文件缓存、内容替换状态），显式共享（`shareAbortController` 等选项）
- **信任但验证**：子 Agent 执行时不干预，完成后 `classifyHandoffIfNeeded()` 安全审计，最终判断交给父 Agent LLM 推理

### 不是子进程的证据

- 无 `child_process.fork()` 或 `spawn()` 调用
- 子 Agent 共享主进程 React 状态树
- 通信通过内存通知（`task-notification`）和直接函数调用（`resumeAgentBackground`），无 HTTP/gRPC
- 唯一的跨进程边界是 MCP 服务器（stdio/SSE）和 Bash 工具（shell 命令），属于工具层面

### 与其他方案的对比

| 方案 | 进程模型 | 通信方式 | 代表 |
|------|---------|---------|------|
| Claude Code | 同进程子图 | 内存通知 + 函数调用 | `createSubagentContext()` |
| LangGraph 子图 | 同进程子图 | 内存状态传递 | `StateGraph` |
| A2A | 独立进程 | HTTP/gRPC | Google A2A 协议 |
| OpenClaw session_spawn | 独立进程/会话 | session 工具套件通信 | `session_spawn` |

---

## 2. 消息处理与执行模型（2026-05-07）

### 三种输入类型的处理差异

`processUserInput()` 根据输入前缀走不同路径，核心区分在于 **`shouldQuery`** 返回值：

| 输入类型 | 处理函数 | `shouldQuery` | 行为 |
|---------|---------|--------------|------|
| 普通文本 | `processTextPrompt` | `true` | 构造 UserMessage + AttachmentMessages → 进入 query 循环 |
| `!xxx` Bash 模式 | `processBashCommand` | `false` | 直接调用 `BashTool.call()` 执行命令，结果包 `<bash-stdout>/<bash-stderr>` 标签，**不进 query 循环** |
| `/xxx` 斜杠命令 | `processSlashCommand` | 视情况 | 本地 JSX 命令（`/help`）→ `false`；Skill 命令（`/commit`）→ `true`；Agent 命令（`/fork`）→ `true` |

**`shouldQuery: true` 才进 query 循环让 LLM 处理，`false` 在本地处理完直接返回**。Bash 模式本质是快捷方式——用户不想跟 LLM 对话，只想跑命令看结果。

### Query Loop 的执行模型

**核心模型：轮次串行 + 轮内并行 + Agent 递归 + Fork 禁止嵌套**

```
父 Agent query loop (轮次串行)
    │
    ├─ 第1轮: 所有消息 → API → LLM 返回 → 并行执行 [Grep, Glob, Read] → 收集结果
    ├─ 第2轮: 消息(含上轮结果) → API → LLM 返回 → 执行 [Agent(Explore), Agent(Plan)]
    │         └─ 两个 Agent 各自启动独立的 query loop，并行运行
    ├─ 第3轮: 等 task-notification 回来 → LLM 综合判断 → 可能再派 Agent
    └─ ...
```

**轮次串行**：每一轮必须等所有工具执行完毕、收集完 tool_result 后，才能构建下一轮消息发给 API。不存在"边执行工具边发下一轮请求"的情况。

**轮内并行**：由 `StreamingToolExecutor` 控制（StreamingToolExecutor.ts:129-134）：
- `isConcurrencySafe: true` 的工具（Glob、Grep、Read 等）→ **可并行执行**
- `isConcurrencySafe: false` 的工具（Bash、Write、Edit 等）→ **独占执行**
- 判断逻辑：当前无执行中工具，或执行中的工具全部是并发安全的，才启动新工具

**Agent 并行性取决于模式**：
- Fork 开启（`isForkSubagentEnabled()`）：**所有** Agent 调用强制异步（`forceAsync`），多个 Agent 在同一轮中发出后**全部并行**后台运行
- Fork 关闭：同步 Agent **阻塞**父 Agent 的 query 循环直到完成；只有 `run_in_background=true` 的 Agent 才并行

**Agent 递归**：子 Agent 的 `runAgent()` 内部调用的是同一个 `query()` 函数，拥有独立的消息历史、工具集、上下文，运行完全独立的循环。区别是子 Agent 有 `maxTurns` 限制，且 Fork 不能再 Fork。

### 一句话总结

> **轮次串行、轮内并行、Agent 递归、Fork 禁止嵌套**
