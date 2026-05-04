# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 语言要求

所有输出必须使用中文，包括对话、注释、提交信息、文档等。

## 项目目标

构建一个类似 Claude Code 的 AI 编程助手 CLI，使用 Node.js/TypeScript，npm 公开发布。项目处于早期设计阶段，暂无应用代码。

## 参考文档

`docs/` 目录包含 27 章的 Claude Code 源码深度解析，来源：https://sawzhang.github.io/deep-dive-claude-code/ 。实现时重点参考以下章节：

- `ch01-全景概览.md` — 五层架构总览（CLI → 查询引擎 → 工具系统 → Agent 系统 → 协议层）
- `ch04-查询引擎.md` — AsyncGenerator 驱动的查询循环，Agent 的核心
- `ch07-工具架构.md` — Tool<I,O,P> 泛型接口与工具注册
- `ch10-Agent模型.md` — 通过 Markdown frontmatter 定义 Agent + TypeScript 运行时
- `ch13-权限模型.md` — 六层权限模型
- `ch19-React-Ink终端UI.md` — React/Ink 终端渲染
- `ch20-REPL实现.md` — 交互式终端循环

`docs/full-book.md` 是完整单文件版本（412K 字符）。原始 PDF 也在仓库根目录。

## 设计文档

- `design/memory.md` — **跨会话记忆窗口**，持久化记录问题与结论，所有会话开始时先读取此文件了解上下文，每次得出新结论后更新此文件

## 工具链

- Python 环境：`conda activate kg-rag`（运行任何 Python 脚本时必须先激活）
- `convert_web.py` — 从网页抓取书籍内容并分章节转为 markdown，如需更新文档可重新运行
- MinerU 已安装在 kg-rag conda 环境中，但其 pipeline 后端存在依赖冲突，建议使用网页方式转换

## 架构决策（已规划）

- **运行时**：Node.js/TypeScript（非 Bun，构建更简单，npm 生态便于分发）
- **TUI**：React + Ink 终端渲染
- **CLI 框架**：Commander.js
- **类型验证**：Zod
- **分发方式**：npm 公开发布
- **核心模式**：AsyncGenerator 管道实现流式 query→tool→result 流转（参考 ch04/ch06）
