# Security

## Intended boundary

The server runs locally over stdio. It has no supported inbound HTTP listener or remote authentication service.
It polls configured PVE and PBS HTTPS origins using API tokens from environment variables.
The tool interface permits only explicit monitoring queries. It does not accept arbitrary URLs, paths, or HTTP methods.
TLS verification stays enabled, redirects are blocked, and ambient HTTP proxy settings are ignored.
Use `ca_file` for a private CA instead of disabling certificate verification.

## Credentials and data

Use dedicated monitoring users and audit-only API tokens. Both the user and token need appropriate ACLs.
The root `proxmox.json` is ignored by Git. The example configuration contains no secrets.
Environment variables are not a secret vault. Processes with sufficient local access can inspect them.
Protect desktop configuration files that contain tokens. Rotate any token exposed in chat, logs, or version control.
The application does not automatically load `.env` files.

Tool results can contain guest names, network details, resource usage, and backup metadata.
The selected assistant provider receives those results. Local transport does not provide offline AI processing.
Treat upstream text as untrusted data. Read-only annotations help clients but do not replace enforced route restrictions.

## Limits

Authorization can filter resource lists without returning an error. Empty or partial lists do not establish system health.
The server relies on the upstream API for resource access controls and response sizes.
Snapshot lists are not paginated by this client. Large namespaces can produce large tool responses.
This project has no hosted deployment, OAuth flow, uptime guarantee, or background alert service.

## Reporting

Do not post credentials, private inventories, or exploitable deployment details in a public issue.
Use a private maintainer channel if the repository owner provides one.
No private reporting address or supported-release policy has been established yet.
