"""Claude's strict tools use omitted filters rather than required nullable fields.

The shared definitions retain the required/nullable form used by Verda. Claude
counts unions across tools and the answer schema together, with a limit of 16.
The tool handlers already default missing filters to None.

Claude also compiles every strict tool and the answer schema into one grammar, and
rejects the request when that grows too large ("compiled grammar is too large"). The
plan tools only draw on the plan, and the server validates their inputs, so for Claude
they are not strict; the search and counting tools stay strict.
"""

from copy import deepcopy
from typing import Any

from app.qa.plan_tools import PLAN_TOOL_NAMES


def claude_tools(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = deepcopy(tools)
    for tool in result:
        if tool.get("name") in PLAN_TOOL_NAMES:
            tool["strict"] = False
        schema = tool["input_schema"]
        required = list(schema.get("required", []))
        for name, value in schema.get("properties", {}).items():
            branches = value.get("anyOf", [])
            non_null = [branch for branch in branches if branch != {"type": "null"}]
            if len(branches) != 2 or len(non_null) != 1:
                continue
            schema["properties"][name] = {
                **{key: item for key, item in value.items() if key != "anyOf"},
                **non_null[0],
            }
            required = [key for key in required if key != name]
        schema["required"] = required
    return result
