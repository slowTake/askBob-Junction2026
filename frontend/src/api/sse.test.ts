import { describe, expect, it } from "vitest";
import { parseSSE } from "./sse";

describe("parseSSE", () => {
  it("parses complete events and keeps the incomplete tail", () => {
    const { messages, rest } = parseSSE('event: step\ndata: {"a":1}\n\nevent: answer\ndata: {"b"');
    expect(messages).toEqual([{ event: "step", data: '{"a":1}' }]);
    expect(rest).toBe('event: answer\ndata: {"b"');
  });

  it("ignores comments and keepalives", () => {
    const { messages } = parseSSE(": keepalive\n\nevent: done\ndata: {}\n\n");
    expect(messages).toEqual([{ event: "done", data: "{}" }]);
  });

  it("handles CRLF line endings and multi-line data", () => {
    // Per the SSE spec, multiple data lines join with "\n".
    const { messages } = parseSSE("data: one\r\ndata: two\r\n\r\n");
    expect(messages).toEqual([{ event: "message", data: "one\ntwo" }]);
  });
});
