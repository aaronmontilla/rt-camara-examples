"""
camara/flat.py
──────────────
Publishes each tool's input model as top-level arguments.

MCP builds a tool's input schema from the function signature. With the
signature `async def tool(params: SomeInput)` the schema has one property,
`params`, and every real argument sits one level down inside it:

    {"params": {"networkId": "...", "response_format": "json"}}

Models then sometimes send `{"networkId": "..."}` and get a "params: Field
required" error back, and have to call again. `flat_arguments` keeps the
input models (descriptions, constraints and the CreateNetworkInput oneOf
check all still apply) but exposes their fields as the tool's own
arguments:

    {"networkId": "...", "response_format": "json"}

Usage (decorator order matters: flat_arguments goes below mcp.tool):

    @mcp.tool(name="camara_get_network", ...)
    @flat_arguments
    async def camara_get_network(params: GetNetworkInput) -> str:
        ...

The tool body is unchanged: it still receives one validated `params` model.
If building that model fails, the reason is returned as a tool error.

MCP ignores arguments its schema does not list. The input models used to
reject unknown fields (extra="forbid"), so a misspelled argument was an error
the model could correct; `forbid_unknown_arguments` restores that for the
flattened tools and states it in the schema (additionalProperties: false).
"""

import copy
import functools
import inspect
import typing
from typing import Annotated, Any, Awaitable, Callable, Iterable

from mcp.server.mcpserver.exceptions import ToolError
from pydantic import BaseModel, ConfigDict, ValidationError
from pydantic_core import PydanticUndefined

FLAT_ATTRIBUTE = "__camara_flat_model__"


def flat_arguments(fn: Callable[[Any], Awaitable[str]]) -> Callable[..., Awaitable[str]]:
    """Expose the fields of fn's single `params` model as top-level arguments."""
    model = typing.get_type_hints(fn).get("params")
    if not (isinstance(model, type) and issubclass(model, BaseModel)):
        raise TypeError(f"{fn.__name__}: flat_arguments needs a 'params: <BaseModel>' parameter")

    parameters = []
    for name, field in model.model_fields.items():
        # The default goes on the parameter; pydantic does not accept it inside Annotated too.
        info = copy.copy(field)
        info.default = PydanticUndefined
        info.default_factory = None
        default = inspect.Parameter.empty if field.is_required() else field.get_default(call_default_factory=True)
        parameters.append(
            inspect.Parameter(
                name,
                inspect.Parameter.KEYWORD_ONLY,
                default=default,
                annotation=Annotated[field.annotation, info],
            )
        )

    @functools.wraps(fn)
    async def wrapper(**arguments: Any) -> str:
        try:
            params = model(**arguments)
        except ValidationError as exc:
            # Checks that span several fields (e.g. the CreateNetworkInput oneOf) run here, after MCP has
            # validated each argument. Report them the way MCP reports argument errors, so the model sees the
            # reason instead of a bare "Error executing tool".
            raise ToolError(f"Error executing tool {fn.__name__}: {exc}") from exc
        return await fn(params)

    wrapper.__signature__ = inspect.Signature(parameters, return_annotation=str)
    # functools.wraps copied fn's annotations (params: model); the signature above replaces them.
    wrapper.__annotations__ = {p.name: p.annotation for p in parameters} | {"return": str}
    setattr(wrapper, FLAT_ATTRIBUTE, model)
    return wrapper


def forbid_unknown_arguments(tools: Iterable[Any]) -> None:
    """Reject arguments a flattened tool does not declare, and say so in its schema."""
    for tool in tools:
        if getattr(tool.fn, FLAT_ATTRIBUTE, None) is None:
            continue
        metadata = tool.fn_metadata
        strict = type(
            metadata.arg_model.__name__,
            (metadata.arg_model,),
            {"model_config": ConfigDict(arbitrary_types_allowed=True, extra="forbid")},
        )
        metadata.arg_model = strict
        tool.parameters = strict.model_json_schema(by_alias=True)
