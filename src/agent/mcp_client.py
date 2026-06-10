# -*- coding: utf-8 -*-
"""
MCP (Model Context Protocol) 客户端

支持连接外部 MCP Server（如 Vibe-Trading），将其工具注册到 Agent 工具列表。
通过 .env 配置 MCP_SERVER_URLS（逗号分隔的 SSE 端点列表）。

来源：Vibe-Trading (https://github.com/HKUDS/Vibe-Trading)
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class MCPTool:
    """MCP 工具的轻量级表示。"""

    def __init__(self, name: str, description: str, input_schema: dict, server_url: str):
        self.name = name
        self.description = description
        self.input_schema = input_schema
        self.server_url = server_url

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.input_schema.get("properties", {}),
            "source": f"mcp:{self.server_url}",
        }


class MCPClient:
    """
    管理 MCP Server 连接和工具发现。

    通过 SSE 协议与 MCP Server 通信。
    配置方式：MCP_SERVER_URLS=http://localhost:3001/sse,http://...
    """

    def __init__(self):
        self._tools: Dict[str, MCPTool] = {}
        self._server_urls: List[str] = []
        self._initialized = False
        self._load_config()

    def _load_config(self):
        import os
        urls = os.getenv("MCP_SERVER_URLS", "")
        self._server_urls = [u.strip() for u in urls.split(",") if u.strip()]

    def discover_tools(self) -> List[MCPTool]:
        """从所有已配置的 MCP Server 发现工具。"""
        if self._initialized:
            return list(self._tools.values())

        for url in self._server_urls:
            try:
                tools = self._fetch_tools_from_server(url)
                for t in tools:
                    full_name = f"mcp_{t['name']}"
                    self._tools[full_name] = MCPTool(
                        name=full_name,
                        description=t.get("description", ""),
                        input_schema=t.get("inputSchema", {}),
                        server_url=url,
                    )
                logger.info("[MCP] 从 %s 发现 %d 个工具", url, len(tools))
            except Exception as exc:
                logger.warning("[MCP] 连接 %s 失败: %s", url, exc)

        self._initialized = True
        return list(self._tools.values())

    @staticmethod
    def _fetch_tools_from_server(url: str) -> List[dict]:
        """通过 JSON-RPC 从 MCP Server 获取工具列表。"""
        import requests
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/list",
            "params": {},
        }
        resp = requests.post(
            url.replace("/sse", "/message") if "/sse" in url else url,
            json=payload,
            timeout=10,
            headers={"Content-Type": "application/json"},
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("result", {}).get("tools", [])

    def call_tool(self, tool_name: str, arguments: dict) -> Optional[Any]:
        """调用 MCP 工具。"""
        tool = self._tools.get(tool_name)
        if not tool:
            return None

        import requests
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": tool.name.replace("mcp_", ""), "arguments": arguments},
        }
        try:
            resp = requests.post(
                tool.server_url.replace("/sse", "/message"),
                json=payload,
                timeout=30,
                headers={"Content-Type": "application/json"},
            )
            resp.raise_for_status()
            return resp.json().get("result")
        except Exception as exc:
            logger.error("[MCP] 调用 %s 失败: %s", tool_name, exc)
            return None


# 全局单例
_mcp_client: Optional[MCPClient] = None


def get_mcp_client() -> MCPClient:
    global _mcp_client
    if _mcp_client is None:
        _mcp_client = MCPClient()
    return _mcp_client


def discover_mcp_tools() -> List[dict]:
    """发现 MCP 工具并返回 Agent 工具列表格式。"""
    client = get_mcp_client()
    tools = client.discover_tools()
    return [t.to_dict() for t in tools]
