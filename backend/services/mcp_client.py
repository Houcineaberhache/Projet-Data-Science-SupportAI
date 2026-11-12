"""Client for connecting to the MCP server over streamable-http."""
import asyncio
import concurrent.futures
import json
import logging
import os
from typing import Any

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

logger = logging.getLogger(__name__)

DEFAULT_MCP_URL = "http://mcp:8001/mcp"


def _get_mcp_url() -> str:
    return os.getenv("MCP_URL", DEFAULT_MCP_URL).strip() or DEFAULT_MCP_URL


def _run_async(coro):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, coro).result()
    return asyncio.run(coro)


async def _async_call_tool(name: str, arguments: dict[str, Any]) -> Any:
    url = _get_mcp_url()
    async with streamable_http_client(url) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            res = await session.call_tool(name, arguments)
            if getattr(res, "is_error", False):
                raise RuntimeError(f"MCP tool {name} returned error: {res}")
            if getattr(res, "structured_content", None) and "result" in res.structured_content:
                return res.structured_content["result"]
            items = []
            for content in getattr(res, "content", []):
                if getattr(content, "type", None) == "text" and hasattr(content, "text"):
                    try:
                        items.append(json.loads(content.text))
                    except Exception:
                        items.append(content.text)
            if len(items) == 1:
                return items[0]
            return items


def search_documents(query: str) -> list[dict]:
    """Search documents via MCP server over streamable-http."""
    result = _run_async(_async_call_tool("search_documents", {"query": query}))
    if isinstance(result, list):
        return result
    if isinstance(result, dict):
        return [result]
    return []


def get_order_status(order_id: str) -> dict:
    """Get order status via MCP server over streamable-http."""
    result = _run_async(_async_call_tool("get_order_status", {"order_id": order_id}))
    if isinstance(result, dict):
        return result
    return {"status": "not found", "message": f"Order {order_id} not found."}
