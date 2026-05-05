import type { ChatCompletionMessageParam } from "openai/resources/chat/completions.js";
import type { ApiClient } from "../api/client.js";
import type { Message, QueryEvent, Usage } from "../types/index.js";

export class QueryEngine {
  private messages: Message[] = [];
  private abortController: AbortController | null = null;
  private usage: Usage = { inputTokens: 0, outputTokens: 0 };

  constructor(private readonly client: ApiClient) {}

  async *submitMessage(input: string): AsyncGenerator<QueryEvent> {
    const userMessage: Message = {
      role: "user",
      content: input,
      timestamp: Date.now(),
    };
    this.messages.push(userMessage);
    yield { type: "message_complete", message: userMessage };

    this.abortController = new AbortController();

    let assistantContent = "";
    const startTime = Date.now();

    try {
      const apiMessages = this.toApiMessages();
      const stream = this.client.sendMessage({
        messages: apiMessages,
        signal: this.abortController.signal,
      });

      for await (const event of stream) {
        if (event.type === "text_delta") {
          assistantContent += event.text;
          yield { type: "text_delta", text: event.text };
        } else if (event.type === "done") {
          this.usage.inputTokens += event.inputTokens;
          this.usage.outputTokens += event.outputTokens;
        }
      }
    } catch (err) {
      yield {
        type: "error",
        error: err instanceof Error ? err : new Error(String(err)),
      };
      return;
    } finally {
      this.abortController = null;
    }

    const assistantMessage: Message = {
      role: "assistant",
      content: assistantContent,
      timestamp: Date.now(),
    };
    this.messages.push(assistantMessage);
    yield { type: "message_complete", message: assistantMessage };
  }

  abort(): void {
    this.abortController?.abort();
  }

  getMessages(): readonly Message[] {
    return this.messages;
  }

  getUsage(): Usage {
    return { ...this.usage };
  }

  private toApiMessages(): ChatCompletionMessageParam[] {
    return this.messages.map((m) => ({
      role: m.role,
      content: m.content,
    }));
  }
}
