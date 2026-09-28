"""Explicit read-only API routes. Model input never supplies a URL or credential."""

import json
import os
import re
import ssl
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

import httpx
from pydantic import BaseModel, ConfigDict, Field, field_validator


class Target(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["pve", "pbs"]
    url: str
    token_id: str
    token_secret_env: str
    ca_file: str | None = None
    timeout: float = Field(default=15, ge=1, le=120)

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        parts = urlsplit(value)
        if (parts.scheme != "https" or not parts.hostname or parts.username
                or parts.password or parts.query or parts.fragment
                or parts.path not in ("", "/")):
            raise ValueError("Use an HTTPS origin, for example https://pve.example:8006")
        _ = parts.port
        return value.rstrip("/")

    @field_validator("token_id")
    @classmethod
    def validate_token(cls, value: str) -> str:
        if not re.fullmatch(r"[^\s:=!@]+@[^\s:=!@]+![^\s:=!@]+", value):
            raise ValueError("Expected user@realm!token")
        return value


def load_targets(path: str) -> dict[str, Target]:
    raw = json.loads(Path(path).read_text())
    if not isinstance(raw, dict) or not raw:
        raise ValueError("Configuration must contain at least one named target")
    return {name: Target.model_validate(value) for name, value in raw.items()}


def segment(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]*", value):
        raise ValueError("Invalid node or datastore name")
    return value


Query = Literal["version", "nodes", "node_status", "tasks", "cluster_status",
                "resources", "guest_status", "storage", "datastores",
                "datastore_status", "snapshots"]


def route(kind: str, query: Query, node: str, store: str,
          vmid: int | None, guest_type: Literal["qemu", "lxc"],
          limit: int, start: int, namespace: str) -> tuple[str, dict]:
    if not 1 <= limit <= 500 or start < 0:
        raise ValueError("limit must be 1..500 and start must be nonnegative")
    if query == "version":
        return "/version", {}
    if query == "nodes":
        return "/nodes", {}
    if query == "node_status":
        return f"/nodes/{segment(node)}/status", {}
    if query == "tasks":
        return f"/nodes/{segment(node)}/tasks", {"limit": limit, "start": start}
    if kind == "pve":
        if query in ("cluster_status", "resources"):
            return "/cluster/" + ("status" if query == "cluster_status" else "resources"), {}
        if query == "storage":
            return f"/nodes/{segment(node)}/storage", {}
        if query == "guest_status":
            if vmid is None or vmid < 100 or guest_type not in ("qemu", "lxc"):
                raise ValueError("Provide vmid >= 100 and guest_type qemu or lxc")
            return f"/nodes/{segment(node)}/{guest_type}/{vmid}/status/current", {}
    if kind == "pbs":
        if query == "datastores":
            return "/admin/datastore", {}
        if query in ("datastore_status", "snapshots"):
            suffix = "status" if query == "datastore_status" else "snapshots"
            params = {"ns": namespace} if namespace and query == "snapshots" else {}
            return f"/admin/datastore/{segment(store)}/{suffix}", params
    raise ValueError(f"Query {query!r} is not supported for {kind}")


async def poll(target: Target, query: Query, node: str = "localhost", store: str = "",
               vmid: int | None = None, guest_type: Literal["qemu", "lxc"] = "qemu",
               limit: int = 100, start: int = 0, namespace: str = "",
               transport: httpx.AsyncBaseTransport | None = None) -> dict:
    path, params = route(target.kind, query, node, store, vmid, guest_type, limit, start, namespace)
    secret = os.environ.get(target.token_secret_env, "")
    if not secret or any(c.isspace() for c in secret):
        raise ValueError(f"Set a nonempty token in {target.token_secret_env}")
    prefix, separator = ("PVEAPIToken", "=") if target.kind == "pve" else ("PBSAPIToken", ":")
    headers = {"Authorization": f"{prefix}={target.token_id}{separator}{secret}"}
    context = ssl.create_default_context(cafile=target.ca_file)
    try:
        async with httpx.AsyncClient(verify=context, timeout=target.timeout, headers=headers,
                                    follow_redirects=False, trust_env=False, transport=transport) as client:
            response = await client.get(target.url + "/api2/json" + path, params=params)
        if not 200 <= response.status_code < 300:
            raise ValueError(f"Proxmox returned HTTP {response.status_code}. Check token permissions and target availability.")
        body = response.json()
        if not isinstance(body, dict) or "data" not in body:
            raise ValueError("Invalid Proxmox response: missing data")
    except httpx.HTTPError:
        raise ValueError("Proxmox connection failed. Check connectivity, TLS trust, and timeout.") from None
    except json.JSONDecodeError:
        raise ValueError("Proxmox returned invalid JSON") from None
    return {"kind": target.kind, "query": query, "observed_at": datetime.now(timezone.utc).isoformat(),
            "data": body["data"], **({"total": body["total"]} if "total" in body else {})}
