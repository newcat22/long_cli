export interface Message {
  role: "user" | "assistant";
  content: string;
  timestamp: number;
}

export interface Session {
  id: string;
  messages: Message[];
  createdAt: number;
  usage: Usage;
}

export interface Usage {
  inputTokens: number;
  outputTokens: number;
}

export type QueryEvent =
  | { type: "text_delta"; text: string }
  | { type: "message_complete"; message: Message }
  | { type: "error"; error: Error };

export interface ClientConfig {
  apiKey: string;
  baseURL: string;
  model: string;
  maxTokens?: number;
}
