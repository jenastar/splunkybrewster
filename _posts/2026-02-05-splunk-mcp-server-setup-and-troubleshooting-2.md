---
layout: post
title: Splunk MCP Server Setup and Troubleshooting
date: '2026-02-05T09:00:00-07:00'
tags:
- splunk
- ai
- mcp
- saia
permalink: /2026/02/splunk-mcp-server-setup-and.html
---

Splunk's MCP Server exposes your instance to AI tooling over port 8089. Run SPL, pull metadata, query indexes, interact with the AI Assistant—all through the management API via Model Context Protocol. The app went GA on Feb 4, 2026. The architecture is client-agnostic—any MCP-capable AI tool works. Claude, Cursor, your own homebrew agent. Doesn't matter.

Consider this your mission briefing.

## Splunk Side

### 1. Install the Apps

[Splunk MCP Server v1.0.0](https://splunkbase.splunk.com/app/7931) and [Splunk AI Assistant for SPL v1.5.0](https://splunkbase.splunk.com/app/7145) from Splunkbase. The MCP Server handles the protocol and core tools. The AI Assistant provides the SPL generation, optimization, and explanation tools—without it, those endpoints don't exist. If you're still running a beta MCP build, stop. The GA release introduced encrypted tokens and admin-controlled tool visibility. Your old tokens are dead. Don't panic—just regenerate.

### 2. RBAC and Token

Create a role named `mcp_user`. The name matters—the app looks for it. Assign two capabilities:

- `mcp_tool_execute` — grants access to use MCP tools
- `mcp_tool_admin` — grants admin access for tool management and token creation

Note: Splunk's [setup video](https://www.youtube.com/watch?v=sIhjHAKM7Os) says the role doesn't need capabilities. That was true pre-GA. As of v1.0.0, the capabilities are required.

Assign the role to a user, then generate a token **from within the MCP Server app itself**. As of v1.0.0, tokens generated outside the app—via Settings > Tokens or the REST API—will not work. The app handles its own token lifecycle now, including encryption. Go through the app or don't go at all.

<!-- screenshot: token generation in MCP Server app -->

The token audience is `mcp`. Not `search`. Not empty. Not your app name. Just `mcp`. Miss this and you'll get `insufficient permission` errors with no further explanation. The universe is rarely so lazy, but Splunk's error handling here is.

### 3. IP Allow List (Splunk Cloud)

Your client's outbound IP needs to be on the `search-api` allow list. Port 8089 is the management API—`/services/mcp` lives there. If the IP isn't allowed, the connection dies silently. No error. No log entry. Just the void staring back.

Find your actual outbound IP from wherever your MCP client runs:

```bash
curl ifconfig.me
```

If you're in WSL, on a VPN, behind a proxy, or on a corporate network with split tunneling—this IP is almost certainly different from what your browser reports. I learned this the fun way. Add it via the admin UI or the ACS API:

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

The connection uses `mcp-remote` (npm package) to proxy the remote Splunk endpoint to local stdio. Prerequisite: Node.js (`which npx`—if nothing, `sudo apt install nodejs npm`).

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

**WSL trap:** If you're running your AI tool inside WSL, the command is `npx` directly. Do not wrap it with `wsl`. That wrapper exists for Windows-native apps calling into WSL. If you're already in WSL, you're double-hopping and the proxy won't start. There is no rest for the wicked when you're debugging a problem that doesn't exist.

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

### Layer 2: MCP Proxy (proves token + protocol handshake)

Now test the actual MCP transport:

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

If Layer 1 passed but this fails, your token is the problem—wrong audience, generated outside the app, or mangled by line breaks.

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

Your token has line breaks from terminal wrapping. The GA encrypted tokens are long—copy-paste from a terminal will wrap them across lines and inject invisible characters. Edit the `.mcp.json` directly in your editor.

### `insufficient permission to access the resource`

Three suspects. Line them up:
1. User has a role with `mcp_tool_execute` and `mcp_tool_admin`
2. Token audience is `mcp`
3. You copied the correct token (not the token ID, the actual token value)

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

### Tools return empty results

v1.0.0 lets admins enable/disable individual MCP tools from the app's management UI. If you're getting `{"results":[],"total_rows":0}`, check the tool visibility settings on the Splunk side.

## Quick Reference

| Symptom | Cause | Fix |
|---------|-------|-----|
| Silent failure, no error | IP not on allow list | `curl ifconfig.me` → add to `search-api` allow list |
| `ignoring invalid header` | Token line breaks | Paste in editor, not terminal |
| `insufficient permission` | Wrong audience or missing caps | Token audience = `mcp`, role has both capabilities |
| `spawn` errors | Missing npx | Install Node.js |
| 500 localhost mismatch | No base_url | Set `base_url` in `mcp.conf` |
| SSL cert errors | Self-signed cert | `NODE_TLS_REJECT_UNAUTHORIZED=0` |
| Empty tool results | Tool disabled server-side | Check MCP Server tool management UI |

Splunk's [troubleshooting video](https://www.youtube.com/watch?v=sIhjHAKM7Os) covers the common Enterprise setup failures if you want the visual walkthrough.

## Resources

- [Splunk MCP Server - Splunkbase](https://splunkbase.splunk.com/app/7931)
- [MCP Server Docs](https://help.splunk.com/en/splunk-cloud-platform/mcp-server-for-splunk-platform/about-mcp-server-for-splunk-platform)
- [Troubleshooting Video](https://www.youtube.com/watch?v=sIhjHAKM7Os)
- [IP Allow List Configuration](https://help.splunk.com/en/splunk-cloud-platform/administer/admin-config-service-manual/10.2.2510/administer-splunk-cloud-platform-using-the-admin-config-service-acs-api/configure-ip-allow-lists-for-splunk-cloud-platform)
- [Splunk MCP + AI - Lantern](https://lantern.splunk.com/Platform_Data_Management/Analysis_with_AI/Leveraging_Splunk_MCP_and_AI_for_enhanced_IT_operations_and_security_investigations)

---

*Splunk MCP Server v1.0.0 | Splunk AI Assistant for SPL v1.5.0 | Splunk Cloud v9.3.2411.123 | mcp-remote via npx | WSL2*
