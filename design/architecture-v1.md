# 软件架构 v1

## 1. 模块架构图

MVP 只需四个核心模块，职责清晰，依赖单向：

```
┌─────────────────────────────────────────────────┐
│                    CLI 入口                      │
│              (bin/long-cli.ts)                   │
│  解析命令行参数，校验环境，启动 REPL              │
└──────────────┬──────────────────────────────────┘
               │ 启动
               ▼
┌─────────────────────────────────────────────────┐
│                    REPL 模块                     │
│            (src/screens/REPL.tsx)                │
│  终端交互循环：渲染消息列表 + 读取用户输入        │
│  管理 React/Ink 组件生命周期                      │
└──────────────┬──────────────────────────────────┘
               │ 调用
               ▼
┌─────────────────────────────────────────────────┐
│                  查询引擎模块                     │
│           (src/engine/QueryEngine.ts)            │
│  管理会话状态，驱动 LLM 请求-响应循环             │
│  维护对话历史，追踪 token 用量                    │
└──────────────┬──────────────────────────────────┘
               │ 调用
               ▼
┌─────────────────────────────────────────────────┐
│                  API 客户端模块                   │
│            (src/api/client.ts)                   │
│  封装 Anthropic Messages API 调用                │
│  处理流式响应，错误重试，认证                     │
└─────────────────────────────────────────────────┘
```

**模块依赖规则**：CLI → REPL → 查询引擎 → API 客户端，严格单向，无循环依赖。

---

## 2. 技术架构图

```
┌──────────────────────────────────────────────────────────┐
│                        应用层                             │
│                                                          │
│  React + Ink ─────────── 终端 UI 渲染                    │
│  │                                                       │
│  ├── <App>          根组件，管理全局状态                  │
│  ├── <REPL>         主界面：消息列表 + 输入框             │
│  ├── <MessageList>  对话消息渲染                         │
│  └── <PromptInput>  用户输入框                           │
│                                                          │
├──────────────────────────────────────────────────────────┤
│                        引擎层                             │
│                                                          │
│  QueryEngine ─────────── 会话生命周期管理                 │
│  │                                                       │
│  ├── submitMessage()  提交用户消息，返回 AsyncGenerator   │
│  ├── messages[]       对话历史（可变状态）                │
│  └── abortController  请求取消控制                       │
│                                                          │
├──────────────────────────────────────────────────────────┤
│                        传输层                             │
│                                                          │
│  API Client ──────────── Anthropic Messages API           │
│  │                                                       │
│  ├── sendMessage()    发送消息，返回流式 AsyncIterable    │
│  ├── 认证             Bearer Token（环境变量）            │
│  └── 错误处理         网络重试 + API 错误映射             │
│                                                          │
├──────────────────────────────────────────────────────────┤
│                        基础设施层                          │
│                                                          │
│  Node.js ≥ 18  │  TypeScript  │  npm 分发                │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

---

## 3. 数据流架构图

### 3.1 整体数据流

```
用户键入 "你好"
      │
      ▼
┌──────────┐    userInput     ┌──────────────┐
│ PromptInput│ ──────────────► │ QueryEngine   │
│ (用户输入) │                 │              │
└──────────┘                  │ messages.push │
                              │ (userMessage) │
                                    │
                                    ▼  构建 API 请求
                              ┌──────────────┐
                              │  API Client   │
                              │              │
                              │ POST /messages│
                              │ stream: true │
                              └──────┬───────┘
                                     │
                                     ▼  流式 SSE 响应
                              ┌──────────────┐
                              │ QueryEngine   │
                              │              │
                              │ 逐 token 收集 │
                              │ yield 事件    │
                              │ messages.push │
                              │ (assistantMsg)│
                              └──────┬───────┘
                                     │
                                     ▼  yield 事件流
                              ┌──────────────┐
                              │   REPL 组件   │
                              │              │
                              │ 实时渲染回复  │
                              └──────────────┘
```

### 3.2 事件类型定义

查询引擎通过 AsyncGenerator yield 以下事件，REPL 据此更新 UI：

```
QueryEvent = TextDelta        // 模型输出一个文本片段
           | MessageComplete   // 一条消息完成（用户消息或助手消息）
           | Error             // 发生错误
```

### 3.3 数据结构

```
Message {
  role: "user" | "assistant"
  content: string
  timestamp: number
}

Session {
  id: string               // UUID
  messages: Message[]       // 对话历史，追加写入
  createdAt: number
  usage: {                  // token 用量统计
    inputTokens: number
    outputTokens: number
  }
}
```

---

## 4. 功能流程图

### 4.1 启动流程

```
开始
  │
  ▼
解析命令行参数 (Commander.js)
  │
  ▼
检查 LONG_CLI_API_KEY 环境变量 ───── 未设置 ──► 打印错误提示 ──► 退出(1)
  │                                                    │
  │ 已设置                                             │
  ▼                                                    │
创建 QueryEngine 实例 ◄────────────────────────────────┘
  │
  ▼
启动 Ink 渲染 <REPL> 组件
  │
  ▼
显示欢迎信息 + 输入提示
  │
  ▼
等待用户输入
```

### 4.2 单轮对话流程

```
用户输入文本 + 回车
  │
  ▼
PromptInput 组件捕获输入
  │
  ▼
调用 queryEngine.submitMessage(input)
  │                                      返回 AsyncGenerator
  ▼
┌─────────────────────────────────────────────────────┐
│ for await (const event of generator) {              │
│   switch (event.type) {                             │
│     case "text_delta":  追加文本到当前助手消息      │
│     case "message_complete": 消息完成，加入历史     │
│     case "error": 显示错误信息                      │
│   }                                                 │
│ }                                                   │
└─────────────────────────────────────────────────────┘
  │
  ▼
Ink 自动 re-render，用户看到流式输出
  │
  ▼
generator 结束，输入框重新可用
  │
  ▼
等待下一轮输入
```

### 4.3 退出流程

```
用户输入 "exit" / "quit" / Ctrl+C
  │
  ▼
queryEngine.abort()  (如果正在请求中)
  │
  ▼
Ink unmount
  │
  ▼
进程退出(0)
```

---

## 5. 代码文件规划

```
long-cli/
├── package.json                    # 项目配置、依赖、bin 入口
├── tsconfig.json                   # TypeScript 配置
├── src/
│   ├── index.ts                    # CLI 入口：Commander.js 解析参数，启动 REPL
│   │
│   ├── api/
│   │   └── client.ts              # Anthropic Messages API 客户端
│   │       ├── createClient(config)    创建客户端实例
│   │       ├── sendMessage(params)     发送消息，返回 AsyncIterable<StreamEvent>
│   │       └── 错误处理 & 重试逻辑
│   │
│   ├── engine/
│   │   └── QueryEngine.ts         # 查询引擎
│   │       ├── submitMessage(input)    核心：AsyncGenerator 驱动的查询循环
│   │       ├── messages                对话历史
│   │       ├── abort()                 取消当前请求
│   │       └── getUsage()              获取 token 用量
│   │
│   ├── screens/
│   │   └── REPL.tsx               # REPL 主界面（React/Ink 组件）
│   │       ├── 用户输入处理
│   │       ├── 消息列表渲染
│   │       └── 查询引擎调用与事件处理
│   │
│   └── types/
│       └── index.ts               # 共享类型定义
│           ├── Message
│           ├── Session
│           ├── QueryEvent
│           └── ClientConfig
│
├── bin/
│   └── long-cli.ts                # 可执行入口（#!/usr/bin/env node）
│
└── design/                        # 设计文档（已有）
    ├── prd-v1.md
    ├── architecture-v1.md
    └── memory.md
```

### 5.1 文件职责速查

| 文件 | 行数估算 | 核心职责 |
|------|----------|----------|
| `src/index.ts` | ~30 | 参数解析、环境校验、启动 Ink |
| `src/api/client.ts` | ~80 | API 调用、流式解析、错误处理 |
| `src/engine/QueryEngine.ts` | ~100 | 会话状态、查询循环、事件生成 |
| `src/screens/REPL.tsx` | ~120 | UI 渲染、输入处理、事件消费 |
| `src/types/index.ts` | ~40 | 类型定义 |
| **合计** | **~370** | |

---

## 设计原则

1. **AsyncGenerator 管道**：查询引擎的核心循环是 `for await` 驱动的 AsyncGenerator，这是后续扩展工具调用的基础——工具执行结果可以自然地 yield 回主循环
2. **单向数据流**：用户输入 → 引擎处理 → 事件流 → UI 渲染，没有反向传导
3. **可变状态集中**：QueryEngine 是唯一持有 `messages[]` 的地方，REPL 组件只消费事件，不修改消息
4. **先串行后并行**：MVP 严格串行（一次只有一个请求），但引擎接口设计为 AsyncGenerator，后续加并发无需重构
