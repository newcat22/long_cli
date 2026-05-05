import OpenAI from "openai";
import type { ChatCompletionMessageParam } from "openai/resources/chat/completions.js";
import type { ClientConfig } from "../types/index.js";

const DEFAULT_MAX_TOKENS = 4096;

export interface SendMessageParams {
  messages: ChatCompletionMessageParam[];
  signal?: AbortSignal;
}

export interface StreamDelta {
  type: "text_delta";
  text: string;
}

export interface StreamDone {
  type: "done";
  inputTokens: number;
  outputTokens: number;
  stopReason: string | null;
}

export type StreamEvent = StreamDelta | StreamDone;

export function createClient(config: ClientConfig) {
  const client = new OpenAI({
    apiKey: config.apiKey,
    baseURL: config.baseURL,
  });
  const model = config.model;
  const maxTokens = config.maxTokens ?? DEFAULT_MAX_TOKENS;

  return {
    async *sendMessage(params: SendMessageParams): AsyncGenerator<StreamEvent> {
      const stream = await client.chat.completions.create(
        {
          model,
          max_tokens: maxTokens,
          messages: params.messages,
          stream: true,
          stream_options: { include_usage: true },
        },
        { signal: params.signal },
      );

      let inputTokens = 0;
      let outputTokens = 0;
      let stopReason: string | null = null;

      for await (const chunk of stream) {
        const choice = chunk.choices[0];
        if (choice?.delta?.content) {
          yield { type: "text_delta", text: choice.delta.content };
        }
        if (choice?.finish_reason) {
          stopReason = choice.finish_reason;
        }
        if (chunk.usage) {
          inputTokens = chunk.usage.prompt_tokens;
          outputTokens = chunk.usage.completion_tokens;
        }
      }

      yield { type: "done", inputTokens, outputTokens, stopReason };
    },
  };
}

export type ApiClient = ReturnType<typeof createClient>;
