"""MCP client with tool discovery, invocation, and repeated polling."""

import argparse
import asyncio
import json
import os
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def run(args: argparse.Namespace) -> int:
    params = StdioServerParameters(command=sys.executable,
        args=["-m", "proxmox_mcp.server", "--config", args.config], env=dict(os.environ))
    async with stdio_client(params) as (reader, writer):
        async with ClientSession(reader, writer) as session:
            await session.initialize()
            if args.command == "tools":
                print((await session.list_tools()).model_dump_json(indent=2))
                return 0
            tool = "list_targets" if args.command == "targets" else args.tool
            arguments = {} if args.command == "targets" else json.loads(args.arguments)
            if not isinstance(arguments, dict):
                raise ValueError("--arguments must be a JSON object")
            for index in range(args.count):
                result = await session.call_tool(tool, arguments)
                print(result.model_dump_json(), flush=True)
                if result.isError:
                    return 1
                if index + 1 < args.count:
                    await asyncio.sleep(args.interval)
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=os.environ.get("PROXMOX_CONFIG", "proxmox.json"))
    parser.add_argument("--count", type=int, default=1, help="Number of samples")
    parser.add_argument("--interval", type=float, default=30, help="Seconds between completed samples")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("tools")
    sub.add_parser("targets")
    call = sub.add_parser("call")
    call.add_argument("tool")
    call.add_argument("--arguments", default="{}")
    args = parser.parse_args()
    if not 1 <= args.count <= 10000 or not 1 <= args.interval <= 86400:
        parser.error("count must be 1..10000 and interval must be 1..86400 seconds")
    try:
        raise SystemExit(asyncio.run(run(args)))
    except KeyboardInterrupt:
        raise SystemExit(130) from None


if __name__ == "__main__":
    main()
