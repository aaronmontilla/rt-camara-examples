"""
tests/tool_results.py
─────────────────────
Tools return a CallToolResult (text plus telemetry in _meta, see
camara/telemetry.py). Tests that call a tool function directly use text_of to
get the text the model reads.
"""


def text_of(fn):
    """fn as a coroutine function that returns the result text, asserting it is not an error."""
    async def call(**kwargs):
        result = await fn(**kwargs)
        assert not result.is_error, result.content[0].text
        return result.content[0].text
    return call
