# Proxmox MCP

Read-only MCP server and command-line MCP client for Proxmox VE (PVE) and Proxmox Backup Server (PBS).
Configure one PVE node to query its cluster. Configure each independent PBS server as another target.
The server only permits explicit monitoring routes and HTTP GET requests. It has no arbitrary API, shell, or write tool.

The CLI and local stdio server are implemented. Desktop assistant integration requires separate host configuration.
See [CONTRIBUTING.md](CONTRIBUTING.md) for development and validation coverage,
[SECURITY.md](SECURITY.md) for security boundaries, and [AGENTS.md](AGENTS.md) for agent instructions.

## Install and configure

Requires Python 3.11 or newer and [uv](https://docs.astral.sh/uv/).

```sh
uv sync --locked
cp examples/proxmox.json proxmox.json
```

Edit `proxmox.json` with your endpoints and token identifiers. Secrets come from environment variables, never tool arguments.
Use PVE port 8006 and PBS port 8007 unless your deployment uses another port.
You can remove either example target or add more named targets.

Create a dedicated monitoring user and API token through each Proxmox interface.
Assign **PVEAuditor** on `/` with propagation to the PVE user and privilege-separated token.
Assign **Audit** on `/` with propagation to the PBS user and token.
Narrow these paths if only part of the system should be visible. A token cannot exceed its user's permissions.
Do not use root credentials. Missing permissions can cause incomplete lists as well as HTTP 403 errors.

In a Bash terminal, enter the secrets without shell history or terminal echo:

```bash
read -r -s -p 'PVE token secret: ' PVE_TOKEN_SECRET; echo
export PVE_TOKEN_SECRET
read -r -s -p 'PBS token secret: ' PBS_TOKEN_SECRET; echo
export PBS_TOKEN_SECRET
```

TLS verification is always enabled. For a private CA, add `"ca_file": "/absolute/path/to/ca.pem"` to its target.
The endpoint hostname must match its certificate. There is no insecure TLS switch.
An optional `timeout` sets the request timeout in seconds (default 15, range 1–120).

For zsh, use these secret prompts instead of the Bash prompts:

```zsh
read -rs 'PVE_TOKEN_SECRET?PVE token secret: '; echo
export PVE_TOKEN_SECRET
read -rs 'PBS_TOKEN_SECRET?PBS token secret: '; echo
export PBS_TOKEN_SECRET
```

Set only the variables required by your configured targets. These exports last for the terminal session and its child processes.
The application does not load `.env` automatically.
Both commands accept `--config /absolute/path/proxmox.json`, or use the `PROXMOX_CONFIG` environment variable.
The default configuration path is `proxmox.json` in the current directory.

## Command-line client

The client starts the MCP server as a subprocess by default. It speaks MCP rather than calling Proxmox directly.

```sh
uv run proxmox-mcp-client targets
uv run proxmox-mcp-client tools
uv run proxmox-mcp-client call poll_proxmox --arguments '{"target":"lab","query":"resources"}'
uv run proxmox-mcp-client call poll_proxmox --arguments '{"target":"backups","query":"datastores"}'
uv run proxmox-mcp-client --count 10 --interval 30 call poll_proxmox --arguments '{"target":"lab","query":"cluster_status"}'
```

Each call result is one MCP JSON envelope on stdout. `tools` prints formatted JSON. Diagnostic logs use stderr.
Read `content` text blocks for the payload and check `isError`. Structured content can also appear when provided by the SDK.
The interval starts after the previous request completes. `--count` accepts 1–10000 samples, and `--interval` accepts 1–86400 seconds.
Tool errors produce a nonzero exit status. Ctrl-C stops polling. This client does not call an LLM or require an LLM API key.

## Tools

`list_targets` returns configured names and product types, without credentials.
`poll_proxmox` takes a target and one query:

| Query | Product | Additional arguments |
| --- | --- | --- |
| `version`, `nodes` | Both | None |
| `node_status` | Both | `node` (PBS default: `localhost`) |
| `tasks` | Both | `node`, optional `limit` and `start` |
| `cluster_status`, `resources` | PVE | None |
| `guest_status` | PVE | `node`, `vmid`, `guest_type` (`qemu` or `lxc`) |
| `storage` | PVE | `node` |
| `datastores` | PBS | None |
| `datastore_status`, `snapshots` | PBS | `store`, optional snapshot `namespace` |

Call `nodes` first to find PVE node names. Tasks accept `limit` 1–500 and a zero-based `start` offset.
Snapshots return the complete selected namespace. Other list queries return the upstream list without client pagination.
Each response includes the product type, query, UTC observation time, and original Proxmox data.
Values retain Proxmox units. No health score is invented. Check task exit statuses and snapshot verification fields explicitly.
PBS has no PVE-style cluster quorum. Multiple PBS servers remain separate targets.

## Claude Desktop and local MCP hosts

Merge this entry into your host's MCP configuration. Replace both `/absolute/path/ProxmoxMCP` paths.

```json
{
  "mcpServers": {
    "proxmox": {
      "command": "/absolute/path/ProxmoxMCP/.venv/bin/proxmox-mcp",
      "args": ["--config", "/absolute/path/ProxmoxMCP/proxmox.json"],
      "env": {
        "PVE_TOKEN_SECRET": "REPLACE_LOCALLY",
        "PBS_TOKEN_SECRET": "REPLACE_LOCALLY"
      }
    }
  }
}
```

Use the host's secret storage when available. Otherwise protect the local configuration containing secrets.
GUI applications do not necessarily inherit terminal environment variables. Restart the MCP host after configuration changes.
Ask: “Use Proxmox to show cluster quorum, stopped guests, and storage usage.”
Ask: “List PBS datastores and inspect recent backup tasks for failures.”
An assistant tool call takes one sample. Continuous monitoring needs the CLI repeat options or an external scheduler.

## Local desktop access

This project uses stdio only. Your desktop MCP host starts the server as a local subprocess.
It opens no inbound network listener. It connects outbound to the configured Proxmox HTTPS APIs.
Your computer must be running and able to reach those APIs.
The assistant provider still receives tool results as conversation context. Local transport does not mean offline AI.

For Codex, merge the following into its MCP configuration. Use absolute paths and provide the token secrets through the host environment.

```toml
[mcp_servers.proxmox]
command = "/absolute/path/ProxmoxMCP/.venv/bin/proxmox-mcp"
args = ["--config", "/absolute/path/ProxmoxMCP/proxmox.json"]
env_vars = ["PVE_TOKEN_SECRET", "PBS_TOKEN_SECRET"]
```

The JSON example above supports Claude Desktop. Installing this package does not register it with an assistant host.

## Live checks and troubleshooting

After configuring credentials, check both authentication and resource visibility:

```sh
uv run proxmox-mcp-client call poll_proxmox --arguments '{"target":"lab","query":"version"}'
uv run proxmox-mcp-client call poll_proxmox --arguments '{"target":"lab","query":"resources"}'
uv run proxmox-mcp-client call poll_proxmox --arguments '{"target":"backups","query":"version"}'
uv run proxmox-mcp-client call poll_proxmox --arguments '{"target":"backups","query":"datastores"}'
```

A successful version query does not prove monitoring permissions.

| Symptom | Check |
| --- | --- |
| Empty datastore list or only basic PVE node entries | Audit ACLs on both the user and token, with propagation |
| HTTP 401 | Token ID, secret, realm, expiry, and reverse proxy authentication |
| HTTP 403 | User and token ACLs for the requested resource |
| Connection failure | DNS, HTTPS port, certificate hostname, CA trust, and timeout |
| CLI works but desktop host fails | Absolute executable/configuration paths and the desktop process environment |

Reverse proxies must preserve the Authorization header and permit `/api2/json` requests.
Do not replace an empty response with invented resources or a healthy status.

## Verification

```sh
uv run python -m unittest discover -s tests -v
```

Tests cover product-specific authorization, route restrictions, error sanitization, and stdio MCP.
Mock HTTP responses do not establish compatibility with a live deployment. Test each configured target with `version` before monitoring it.

API references: [PVE API](https://pve.proxmox.com/pve-docs/api-viewer/),
[PBS API](https://pbs.proxmox.com/docs/api-viewer/),
[PBS permissions](https://pbs.proxmox.com/docs/user-management.html),
[MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk/tree/v1.x).
