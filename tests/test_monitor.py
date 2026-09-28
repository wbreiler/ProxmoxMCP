import os
import subprocess
import sys
import unittest
from unittest.mock import patch

import httpx
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from proxmox_mcp.api import Target, poll, route


class MonitorTests(unittest.IsolatedAsyncioTestCase):
    def test_cli_targets(self):
        result = subprocess.run([sys.executable, "-m", "proxmox_mcp.client",
                                 "--config", "examples/proxmox.json", "targets"],
                                capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('"lab"', result.stdout)
        self.assertIn('"backups"', result.stdout)

    async def test_authentication_and_response(self):
        for kind, header in [("pve", "PVEAPIToken=user@realm!mcp=secret"),
                             ("pbs", "PBSAPIToken=user@realm!mcp:secret")]:
            target = Target(kind=kind, url="https://example.test:8006",
                            token_id="user@realm!mcp", token_secret_env="TEST_SECRET")

            def handler(request):
                self.assertEqual(request.method, "GET")
                self.assertEqual(request.url.path, "/api2/json/version")
                self.assertEqual(request.headers["Authorization"], header)
                return httpx.Response(200, json={"data": {"version": "test"}})

            with patch.dict(os.environ, TEST_SECRET="secret"):
                result = await poll(target, "version", transport=httpx.MockTransport(handler))
            self.assertEqual(result["data"], {"version": "test"})
            self.assertIn("observed_at", result)

    async def test_upstream_errors_do_not_leak_secrets(self):
        target = Target(kind="pbs", url="https://example.test",
                        token_id="user@realm!mcp", token_secret_env="TEST_SECRET")
        for status in (302, 401, 403, 500):
            with patch.dict(os.environ, TEST_SECRET="secret"):
                with self.assertRaisesRegex(ValueError, f"HTTP {status}") as error:
                    await poll(target, "version", transport=httpx.MockTransport(
                        lambda request: httpx.Response(status, text="secret")))
                self.assertNotIn("secret", str(error.exception))
        with patch.dict(os.environ, TEST_SECRET="secret"):
            with self.assertRaisesRegex(ValueError, "missing data"):
                await poll(target, "version", transport=httpx.MockTransport(
                    lambda request: httpx.Response(200, json={})))

    def test_routes_and_validation(self):
        def get(kind, query, **kw):
            return route(kind, query, kw.get("node", "pve1"), kw.get("store", "backup"),
                         kw.get("vmid", 101), "qemu", 50, 10, "team")
        self.assertEqual(get("pve", "resources"), ("/cluster/resources", {}))
        self.assertEqual(get("pve", "cluster_status"), ("/cluster/status", {}))
        self.assertEqual(get("pve", "guest_status")[0], "/nodes/pve1/qemu/101/status/current")
        self.assertEqual(get("pbs", "snapshots"), ("/admin/datastore/backup/snapshots", {"ns": "team"}))
        self.assertEqual(get("pbs", "tasks")[1], {"limit": 50, "start": 10})
        for kind, query, kw in [("pbs", "resources", {}), ("pve", "snapshots", {}),
                                ("pve", "node_status", {"node": "../access"}),
                                ("pbs", "snapshots", {"store": "%2e%2e"}),
                                ("pve", "guest_status", {"vmid": 1})]:
            with self.assertRaises(ValueError):
                get(kind, query, **kw)
        for url in ("http://example.test", "https://u:p@example.test", "https://example.test/path",
                    "https://example.test?redirect=elsewhere"):
            with self.assertRaises(ValueError):
                Target(kind="pve", url=url, token_id="user@pve!mcp", token_secret_env="TOKEN")

    async def test_real_stdio_protocol(self):
        params = StdioServerParameters(command=sys.executable,
            args=["-m", "proxmox_mcp.server", "--config", "examples/proxmox.json"])
        async with stdio_client(params) as (reader, writer):
            async with ClientSession(reader, writer) as session:
                await session.initialize()
                listed = await session.list_tools()
                self.assertEqual({tool.name for tool in listed.tools}, {"list_targets", "poll_proxmox"})
                self.assertTrue(all(tool.annotations.readOnlyHint for tool in listed.tools))
                result = await session.call_tool("list_targets", {})
                self.assertFalse(result.isError)
                self.assertNotIn("token", result.model_dump_json())
                failure = await session.call_tool("poll_proxmox", {"target": "unknown", "query": "version"})
                self.assertTrue(failure.isError)


if __name__ == "__main__":
    unittest.main()
