/** Human-readable labels for the agent's tool calls, shown while an answer streams in. */

export function describeStep(tool: string, input: Record<string, unknown>): string {
  const text = typeof input.text === "string" && input.text ? ` “${input.text}”` : "";
  const kind = typeof input.kind === "string" ? `${input.kind}s` : "elements";
  const page = typeof input.page_index === "number" ? ` on page ${input.page_index + 1}` : "";
  switch (tool) {
    case "find_elements":
      return `Searching ${kind}${text}${page}`;
    case "get_element":
      return "Reading element details";
    case "view_region":
      return "Looking at the drawing";
    case "measure_distance":
      return "Measuring on the drawing";
    default:
      return tool;
  }
}
