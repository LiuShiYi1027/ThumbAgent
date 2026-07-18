"""Start the Mobile Agent MCP stdio adapter."""

from __future__ import annotations

import argparse
import os
import sys

from mobile_agent.mcp.api_client import RuntimeApiClient
from mobile_agent.mcp.server import McpServer, run_stdio


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Mobile Agent MCP over stdio")
    parser.add_argument(
        "--base-url",
        default=os.environ.get("MOBILE_AGENT_MCP_BASE_URL", "http://127.0.0.1:8765"),
    )
    args = parser.parse_args(argv)
    token = os.environ.get("MOBILE_AGENT_API_TOKEN", "")
    try:
        client = RuntimeApiClient(args.base_url, token)
    except ValueError as error:
        print(f"Mobile Agent MCP 启动失败：{error}", file=sys.stderr)
        return 2
    run_stdio(McpServer(client), sys.stdin, sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
