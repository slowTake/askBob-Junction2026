/** Server-sent events over fetch (EventSource can't POST, and /api/ask is a POST). */

export interface SSEMessage {
  event: string;
  data: string;
}

/**
 * Split a buffer into complete SSE messages. Whatever follows the last blank line is
 * returned as `rest` and must be prepended to the next chunk.
 */
export function parseSSE(buffer: string): { messages: SSEMessage[]; rest: string } {
  const normalized = buffer.replace(/\r\n?/g, "\n");
  const blocks = normalized.split("\n\n");
  const rest = blocks.pop() ?? "";
  const messages: SSEMessage[] = [];
  for (const block of blocks) {
    let event = "message";
    const data: string[] = [];
    for (const line of block.split("\n")) {
      if (line.startsWith(":")) continue; // comment / keepalive
      const colon = line.indexOf(":");
      const field = colon === -1 ? line : line.slice(0, colon);
      const value = colon === -1 ? "" : line.slice(colon + 1).replace(/^ /, "");
      if (field === "event") event = value;
      else if (field === "data") data.push(value);
    }
    if (data.length > 0) messages.push({ event, data: data.join("\n") });
  }
  return { messages, rest };
}

export async function readSSE(
  stream: ReadableStream<Uint8Array>,
  onMessage: (message: SSEMessage) => void,
): Promise<void> {
  const reader = stream.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parsed = parseSSE(buffer);
    buffer = parsed.rest;
    parsed.messages.forEach(onMessage);
  }
  parseSSE(buffer + "\n\n").messages.forEach(onMessage);
}
