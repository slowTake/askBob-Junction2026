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
    case "sum_room_areas":
      return typeof input.unit === "string" && input.unit
        ? `Adding up the room areas of apartment ${input.unit}`
        : "Adding up the room areas";
    case "count_elements": {
      const filter = [input.subtype, input.category, input.name].find(
        (v): v is string => typeof v === "string" && v !== "",
      );
      const where = typeof input.storey === "string" && input.storey ? ` on ${input.storey}` : page;
      return `Counting ${kind}${filter ? ` “${filter}”` : ""}${where}`;
    }
    case "highlight": {
      const n = Array.isArray(input.element_ids) ? input.element_ids.length : 0;
      return `Showing ${n} element${n === 1 ? "" : "s"} on the plan`;
    }
    case "measure_between":
      return "Measuring between two elements";
    default:
      return tool;
  }
}
