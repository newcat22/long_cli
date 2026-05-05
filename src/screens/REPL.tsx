import React, { useState, useCallback, useRef, useEffect } from "react";
import { Box, Text, useApp, useInput } from "ink";
import { QueryEngine } from "../engine/QueryEngine.js";
import type { Message, QueryEvent } from "../types/index.js";

interface REPLProps {
  engine: QueryEngine;
}

export function REPL({ engine }: REPLProps) {
  const { exit } = useApp();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isProcessing, setIsProcessing] = useState(false);
  const [streamingText, setStreamingText] = useState("");
  const [error, setError] = useState<string | null>(null);
  const abortRef = useState<(() => void) | null>(null);

  useInput((ch, key) => {
    if (key.ctrl && ch === "c" && !isProcessing) {
      exit();
      return;
    }

    if (isProcessing) return;

    if (key.return) {
      const trimmed = input.trim();
      if (!trimmed) return;

      if (trimmed === "exit" || trimmed === "quit") {
        exit();
        return;
      }

      handleSubmit(trimmed);
      setInput("");
      return;
    }

    if (key.backspace || key.delete) {
      setInput((prev) => prev.slice(0, -1));
      return;
    }

    if (ch && !key.ctrl && !key.meta) {
      setInput((prev) => prev + ch);
    }
  });

  const handleSubmit = useCallback(
    async (text: string) => {
      setIsProcessing(true);
      setStreamingText("");
      setError(null);

      try {
        const generator = engine.submitMessage(text);

        for await (const event of generator as AsyncIterable<QueryEvent>) {
          switch (event.type) {
            case "message_complete":
              setMessages((prev) => [...prev, event.message]);
              setStreamingText("");
              break;
            case "text_delta":
              setStreamingText((prev) => prev + event.text);
              break;
            case "error":
              setError(event.error.message);
              break;
          }
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      } finally {
        setIsProcessing(false);
      }
    },
    [engine],
  );

  return (
    <Box flexDirection="column" paddingX={1}>
      <Box marginBottom={1}>
        <Text color="cyan" bold>
          long-cli
        </Text>
        <Text dimColor> — AI 编程助手（输入 exit 退出）</Text>
      </Box>

      {messages.map((msg, i) => (
        <MessageRow key={i} message={msg} />
      ))}

      {streamingText && (
        <Box marginLeft={2} flexDirection="column">
          <Text color="green">{streamingText}</Text>
        </Box>
      )}

      {error && (
        <Box marginLeft={2}>
          <Text color="red">错误: {error}</Text>
        </Box>
      )}

      <Box marginTop={1}>
        <Text color="yellow" bold>
          {isProcessing ? "●" : "›"}{" "}
        </Text>
        {isProcessing ? (
          <Text dimColor>思考中...</Text>
        ) : (
          <Text>{input}</Text>
        )}
      </Box>
    </Box>
  );
}

function MessageRow({ message }: { message: Message }) {
  if (message.role === "user") {
    return (
      <Box marginBottom={0}>
        <Text color="yellow" bold>
          ›{" "}
        </Text>
        <Text>{message.content}</Text>
      </Box>
    );
  }

  return (
    <Box marginLeft={2} marginBottom={1} flexDirection="column">
      <Text>{message.content}</Text>
    </Box>
  );
}
