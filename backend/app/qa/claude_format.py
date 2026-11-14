"""Claude's strict tools use omitted filters rather than required nullable fields.

The shared definitions retain the required/nullable form used by Verda. Claude
counts unions across tools and the answer schema together, with a limit of 16.
The tool handlers already default missing filters to None.
"""

from copy import deepcopy
from typing import Any


def claude_tools(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = deepcopy(tools)
    for tool in result:
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
