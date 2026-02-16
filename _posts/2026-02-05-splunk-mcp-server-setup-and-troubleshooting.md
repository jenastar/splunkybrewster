---
layout: post
title: Splunk MCP Server Setup and Troubleshooting
date: '2026-02-05T09:00:00-07:00'
tags:
- splunk
- ai
- mcp
- saia
permalink: /2026/02/splunk-mcp-server-setup-and_01057448918.html
---

Splunk's MCP Server exposes your instance to AI tooling over port 8089. Run SPL, pull metadata, query indexes, interact with the AI Assistant, all through the management API via Model Context Protocol. The app went GA on Feb 4, 2026. The architecture is client-agnostic. Any MCP-capable AI tool works: Claude, Cursor, your own homebrew agent.

Consider this your mission briefing.

## Before You Start

Read these first. Every one of them will cost you an hour if you miss it.

> **Token generation moved.** As of v1.0.0, tokens must be generated from within the MCP Server app. Tokens created via Settings > Tokens or the REST API will not work. If you upgraded from the beta, your old tokens are dead. Regenerate from inside the app. The app sets the audience automatically.

> **The role must be named `mcp_user`.** The app looks for this specific name. An arbitrary role with the right capabilities won't cut it.

> **Your CLI IP is not your browser IP.** If you're in WSL, on a VPN, or behind split tunneling, `curl ifconfig.me` will return a different IP than your browser. The `search-api` allow list needs the CLI IP. Miss this and the connection dies silently. No error, no log, nothing.

> **Don't wrap `npx` with `wsl`.** If you're already running inside WSL, the `wsl` wrapper double-hops and the proxy won't start. There is no rest for the wicked when you're debugging a problem that doesn't exist.

## Splunk Side

### 1. Install the Apps

Two apps from Splunkbase:

- [Splunk MCP Server v1.0.0](https://splunkbase.splunk.com/app/7931) - the protocol layer and core tools
- [Splunk AI Assistant for SPL v1.5.0](https://splunkbase.splunk.com/app/7145) - SPL generation, optimization, and explanation tools

Without the AI Assistant, those endpoints don't exist. You need both.

### 2. Enable All MCP Endpoints

After installation, not all MCP endpoints are enabled by default. The app ships with some tools turned off, which means your AI client will only see a partial toolset and silently miss capabilities. Go into the MCP Server app's management UI and verify that every endpoint you need is toggled on.

<!-- screenshot: MCP Server endpoint/tool enable UI -->

If you skip this step, everything will *appear* to work. The proxy connects, the handshake completes, `splunk_get_info` returns data. But when you try to run SPL or use the AI Assistant tools, they simply won't exist on the client side. No error, no warning. The tools just aren't advertised because they're disabled server-side. Check this before you burn time debugging a connection that's already working fine.

### 3. RBAC and Token

Create a role named `mcp_user`. Assign two capabilities:

- `mcp_tool_execute` - grants access to use MCP tools
- `mcp_tool_admin` - grants admin access for tool management and token creation

Splunk's [setup video](https://www.youtube.com/watch?v=sIhjHAKM7Os) says the role doesn't need capabilities. That was true pre-GA. As of v1.0.0, the capabilities are required.

Assign the role to a user, then generate a token from within the MCP Server app.

<!-- screenshot: token generation in MCP Server app -->

### 4. IP Allow List (Splunk Cloud)

Your client's outbound IP needs to be on the `search-api` allow list. Port 8089 is the management API where `/services/mcp` lives. If the IP isn't allowed, the connection dies silently. No error. No log entry. Just the void staring back.

Find your actual outbound IP from wherever your MCP client runs:

```bash
curl ifconfig.me
```

If you're in WSL, on a VPN, behind a proxy, or on a corporate network with split tunneling, this IP is almost certainly different from what your browser reports. I learned this the fun way. Add it via the admin UI or the ACS API:

```bash
# Recon: check current allow list
curl https://admin.splunk.com/YOUR-STACK/adminconfig/v2/access/search-api/ipallowlists \
  --header "Authorization: Bearer YOUR_ACS_TOKEN"

# Add your IP
curl -X POST https://admin.splunk.com/YOUR-STACK/adminconfig/v2/access/search-api/ipallowlists \
  --header "Content-Type: application/json" \
  --header "Authorization: Bearer YOUR_ACS_TOKEN" \
  --data '{"subnets": ["YOUR.CLI.IP.ADDRESS/32"]}'
```

Propagation takes a few minutes. If you're on a VPN with rotating IPs, get the CIDR range from your network team.

## Client Side

The connection uses `mcp-remote` (npm package) to proxy the remote Splunk endpoint to local stdio. Prerequisite: Node.js. Check with `which npx`. If nothing, `sudo apt install nodejs npm`.

### From the CLI

Start the MCP proxy directly:

```bash
npx -y mcp-remote \
  https://YOUR-INSTANCE.splunkcloud.com:8089/services/mcp \
  --header "Authorization: Bearer YOUR_TOKEN_HERE"
```

<!-- screenshot: Claude Code MCP server setup -->

Or register it with Claude Code so it persists across sessions:

```bash
claude mcp add splunk-mcp-server -- npx -y mcp-remote \
  https://YOUR-INSTANCE.splunkcloud.com:8089/services/mcp \
  --header "Authorization: Bearer YOUR_TOKEN_HERE"
```

### Via .mcp.json

Same thing, file-based. Drop this in your project root:

```json
{
    "mcpServers": {
      "splunk-mcp-server": {
        "command": "npx",
        "args": [
          "-y",
          "mcp-remote",
          "https://YOUR-INSTANCE.splunkcloud.com:8089/services/mcp",
          "--header",
          "Authorization: Bearer YOUR_TOKEN_HERE"
        ]
      }
    }
}
```

All three get you to the same place.

## Testing Connectivity

Test in layers. Bottom up.

### Layer 1: Can You Reach the Endpoint?

Before you involve any tooling, just hit the endpoint with curl. This proves your IP is on the allow list and the network path is clear.

```bash
curl -s -o /dev/null -w "%{http_code}" \
  https://YOUR-INSTANCE.splunkcloud.com:8089/services/mcp \
  --header "Authorization: Bearer YOUR_TOKEN_HERE"
```

You're looking for a `200` or `405`. Either means the endpoint is alive and your IP is allowed through. If you get a timeout or connection refused, your IP isn't on the `search-api` allow list. Run `curl ifconfig.me`, compare it to what's listed, and fix it before going further. Everything else is built on this.

### Layer 2: MCP Proxy

Now test the actual MCP transport. This proves the token and protocol handshake:

```bash
npx -y mcp-remote \
  https://YOUR-INSTANCE.splunkcloud.com:8089/services/mcp \
  --header "Authorization: Bearer YOUR_TOKEN_HERE"
```

Success:

```
Connected to remote server using StreamableHTTPClientTransport
Local STDIO server running
Proxy established successfully between local STDIO and remote StreamableHTTPClientTransport
```

If Layer 1 passed but this fails, RBAC or your token is the problem. Generated outside the app, or mangled by line breaks.

### Layer 3: Claude Code MCP Status

```bash
claude mcp list
```

```
splunk-mcp-server: npx -y mcp-remote ... - Connected
```

The word you're looking for is `Connected`. Anything else means Layer 2 isn't solid.

### Layer 4: Live Tool Call

From inside a Claude Code session, call `splunk_get_info`. You should get back your instance version, server name, and health status. If you get data, the channel is open. Boots on the ground. You're operational.

<!-- screenshot: Claude Code splunk_get_info tool call -->

## Troubleshooting

### Silent connection failure (Splunk Cloud)

IP isn't on the `search-api` allow list. Run `curl ifconfig.me` from wherever your MCP client lives, compare it to your browser's IP (they will be different), and add the right one. This is the #1 issue because there's zero feedback when it fails. The void doesn't send error codes.

### `Warning: ignoring invalid header argument`

Your token has line breaks from terminal wrapping. The GA encrypted tokens are long. Copy-paste from a terminal will wrap them across lines and inject invisible characters. Edit the `.mcp.json` directly in your editor.

### `insufficient permission to access the resource`

Three suspects. Line them up:
1. User has a role named `mcp_user` with `mcp_tool_execute` and `mcp_tool_admin`
2. Token was generated from within the MCP Server app (not Settings > Tokens)
3. You copied the actual token value, not the token ID

### 500 `hostname localhost doesn't match` (Enterprise)

The MCP server calls back to itself via REST and can't resolve its own hostname. Set the base URL explicitly:

```ini
# $SPLUNK_HOME/etc/apps/Splunk_MCP_Server/local/mcp.conf
[server]
base_url = https://YOUR-SPLUNK-HOST:8089/
```

### `self-signed cert in chain` (Enterprise)

Default self-signed cert on 8089. Client-side workaround in your `.mcp.json`:

```json
"env": {
  "NODE_TLS_REJECT_UNAUTHORIZED": "0"
}
```

Production environments should use a real cert. This is a field expedient, not a permanent solution.

### Tools missing or return empty results

v1.0.0 ships with not all endpoints enabled by default. If tools are missing from your client entirely, or you're getting `{"results":[],"total_rows":0}`, the endpoints are disabled server-side. Open the MCP Server app's management UI and enable the tools you need (see Step 2). This is easy to miss because the connection itself works perfectly — `splunk_get_info` returns data, the proxy is green, but the AI Assistant tools and others just aren't there.

## Quick Reference

| Symptom | Cause | Fix |
|---------|-------|-----|
| Silent failure, no error | IP not on allow list | `curl ifconfig.me` then add to `search-api` allow list |
| `ignoring invalid header` | Token line breaks | Paste in editor, not terminal |
| `insufficient permission` | Token or role issue | Generate token in-app, role named `mcp_user` with both capabilities |
| `spawn` errors | Missing npx | Install Node.js |
| 500 localhost mismatch | No base_url | Set `base_url` in `mcp.conf` |
| SSL cert errors | Self-signed cert | `NODE_TLS_REJECT_UNAUTHORIZED=0` |
| Tools missing or empty results | Endpoints not enabled | Enable tools in MCP Server app management UI (Step 2) |

Splunk's [troubleshooting video](https://www.youtube.com/watch?v=sIhjHAKM7Os) covers the common Enterprise setup failures if you want the visual walkthrough.

## Resources

- [Splunk MCP Server - Splunkbase](https://splunkbase.splunk.com/app/7931)
- [Splunk AI Assistant for SPL - Splunkbase](https://splunkbase.splunk.com/app/7145)
- [MCP Server Docs](https://help.splunk.com/en/splunk-cloud-platform/mcp-server-for-splunk-platform/about-mcp-server-for-splunk-platform)
- [Troubleshooting Video](https://www.youtube.com/watch?v=sIhjHAKM7Os)
- [IP Allow List Configuration](https://help.splunk.com/en/splunk-cloud-platform/administer/admin-config-service-manual/10.2.2510/administer-splunk-cloud-platform-using-the-admin-config-service-acs-api/configure-ip-allow-lists-for-splunk-cloud-platform)
- [Splunk MCP + AI - Lantern](https://lantern.splunk.com/Platform_Data_Management/Analysis_with_AI/Leveraging_Splunk_MCP_and_AI_for_enhanced_IT_operations_and_security_investigations)

---

*Splunk MCP Server v1.0.0 | Splunk AI Assistant for SPL v1.5.0 | Splunk Cloud v9.3.2411.123 | mcp-remote via npx | WSL2*
