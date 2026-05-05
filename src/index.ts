import "dotenv/config";
import React from "react";
import { render } from "ink";
import { createClient } from "./api/client.js";
import { QueryEngine } from "./engine/QueryEngine.js";
import { REPL } from "./screens/REPL.js";

const API_KEY_ENV = "OPENAI_API_KEY";
const BASE_URL_ENV = "OPENAI_BASE_URL";
const MODEL_ENV = "CHAT_MODEL";

const DEFAULT_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1";
const DEFAULT_MODEL = "qwen-plus";

function main() {
  const apiKey = process.env[API_KEY_ENV];
  if (!apiKey) {
    console.error(
      `错误: 未设置 ${API_KEY_ENV}。\n` +
        `请在项目根目录 .env 文件中配置，或设置环境变量。`,
    );
    process.exit(1);
  }

  const baseURL = process.env[BASE_URL_ENV] ?? DEFAULT_BASE_URL;
  const model = process.env[MODEL_ENV] ?? DEFAULT_MODEL;

  const client = createClient({ apiKey, baseURL, model });
  const engine = new QueryEngine(client);

  render(React.createElement(REPL, { engine }));
}

main();
