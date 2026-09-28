# Contributing

## Development

Use Python 3.11 or newer and uv. From the repository root:

```sh
uv sync --locked
uv run python -m unittest discover -s tests -v
uv run proxmox-mcp-client --config examples/proxmox.json targets
uv run proxmox-mcp-client --config examples/proxmox.json tools
```

The last two commands exercise MCP discovery without credentials or network requests to Proxmox.
The example endpoints are fictional. Do not use them for live polling.

## Request flow

The desktop host or CLI starts `proxmox-mcp` as a subprocess.
The server loads named targets from a JSON file and registers two MCP tools.
`list_targets` returns target names and product types.
`poll_proxmox` selects an explicit route through `api.route`, then calls `api.poll`.
The API layer reads the selected token from the environment and sends one HTTPS GET request.
PVE uses `PVEAPIToken=ID=SECRET`. PBS uses `PBSAPIToken=ID:SECRET`.
The response retains upstream data and adds the product type, query, and UTC observation time.

## Changes

Keep PVE and PBS behavior separate where their APIs differ.
For a new query, verify the upstream endpoint, permission requirements, parameters, and response shape.
Update the query type, route selection, MCP tool description, README query table, and relevant tests together.
Use the standard library and existing dependencies before adding a dependency.
Commit `uv.lock` with intentional dependency changes.

## Validation limits

The offline suite checks authentication headers, routing, input validation, upstream errors, CLI output, and the stdio protocol.
It does not validate TLS against a live deployment, all upstream endpoint versions, or desktop host configuration.
During initial development, the user verified PVE version `9.2.20` and PBS version `4.2` through the CLI.
The user also verified populated PVE resources and a PBS datastore list after correcting ACLs.
These results are observations, not a compatibility guarantee for every query or release.
Guest status, task lists, snapshot lists, and desktop assistant integration still require live verification.

## Review

Run the offline suite from the repository root. Check `git diff --check` before committing.
Keep deployment configuration, credentials, virtual environments, and raw live inventories out of commits.
Describe the behavior change and the tests performed in each review request.
The repository currently has no license grant. The owner must choose a license before distribution under one.
