"""
The workflow prompts must name the parameters each tool actually accepts.

A prompt that lists "Use **`camara_create_network`** with: `profileId`"
steers the model to an argument the tool's input model rejects (unknown
fields are forbidden), so every parameter list in the prompts is checked
against the input model of the tool it introduces.
"""

import re
import typing

# "**`camara_xxx`** with:" followed by its bullet list
_PARAMETER_BLOCK = re.compile(r"\*\*`(camara_\w+)`\*\* with:\n((?:- .*\n|  .*\n)+)")
# First backticked name of a top-level bullet: "- `name`" or "- **`name`**"
_BULLET_NAME = re.compile(r"^- (?:\*\*)?`([A-Za-z_]\w*)`")


def _input_fields(tool) -> set:
    model = typing.get_type_hints(tool.fn)["params"]
    return set(model.model_fields)


def test_prompt_parameter_lists_match_tool_input_models():
    import server

    tools = {t.name: t for t in server.mcp._tool_manager.list_tools()}
    checked = 0
    for prompt in server.mcp._prompt_manager.list_prompts():
        for tool_name, block in _PARAMETER_BLOCK.findall(prompt.fn()):
            fields = _input_fields(tools[tool_name])
            for line in block.splitlines():
                match = _BULLET_NAME.match(line)
                if match:
                    checked += 1
                    name = match.group(1)
                    assert name in fields, (
                        f"prompt {prompt.name}: {tool_name} has no parameter {name!r}"
                    )
    assert checked > 0, "no parameter lists found in the prompts"
