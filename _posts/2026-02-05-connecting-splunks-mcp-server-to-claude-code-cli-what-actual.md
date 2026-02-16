---
layout: post
title: "Connecting Splunk's MCP Server to Claude Code CLI: What Actually Worked (and What Didn't)"
date: '2026-02-05T16:00:00-07:00'
tags:
- splunk
- ai
- mcp
- saia
permalink: /2026/02/connecting-splunks-mcp-server-to-claude_01087247959.html
---

# Setting Up Splunk's MCP Server: A Practical Guide to Getting Connected

I recently set up Splunk's MCP server so I could interact with our Splunk environment directly from AI tools like Claude Code and Cursor. Here's what I learned - including the gotchas that cost me a couple hours.

## Why Use Splunk MCP?

We manage a CI/CD pipeline for Splunk detection rules - about 200+ YAML files, each containing an SPL search. Being able to query Splunk data, check indexes, pull metadata, and run searches without leaving my editor is a real workflow improvement. No more context-switching to the Splunk web UI every time I need to validate something.

The Splunk MCP Server exposes a bunch of useful tools:

  * **`run_splunk_query`** \- Execute SPL queries and get results back
  * **`get_indexes`** / **`get_index_info`** \- List and inspect indexes
  * **`get_metadata`** \- Retrieve hosts, sources, and sourcetypes
  * **`get_knowledge_objects`** \- Access saved searches, macros, data models, etc.
  * **`get_user_info`** \- Check your authenticated user details
  * **AI Assistant tools** \- `generate_spl`, `optimize_spl`, `explain_spl`, `ask_splunk_question` (requires the Splunk AI Assistant for SPL app)

## Prerequisites

Before you start, make sure you have:

  1. **Node.js and NPX installed** on the machine making the MCP calls `bash which npx` If nothing comes back, install Node.js. In WSL: `sudo apt update && sudo apt install nodejs npm`

  2. **Splunk MCP Server app installed** on your Splunk instance ([Splunkbase link](https://splunkbase.splunk.com/app/7931))

  3. **A Splunk user with the MCP role** and a bearer token configured (more on this below)

  4. **Your IP on the allow list** if you're on Splunk Cloud (this is the big one - more on this below)

## Splunk-Side Configuration

### Create the MCP Role, User, and Token

This is where most people trip up. You need to get all of these right or you'll see "insufficient permission to access the resource" errors.

  1. **Create an MCP role** in Splunk with the appropriate MCP capabilities
  2. **Assign that role to a Splunk user**
  3. **Create a token** for that user:
  4. Go to **Settings > Tokens** in Splunk Web
  5. Select the correct user
  6. Set the audience to **`mcp`** \- this is the one people miss. It must say `mcp`, not `search`, not blank.
  7. **Copy the token** \- carefully. Long tokens and terminals don't mix. If your terminal wraps the token across multiple lines, the MCP proxy will silently reject it with a `Warning: ignoring invalid header argument` that's easy to miss. Paste it directly into your config file in an editor instead.

### The IP Allow List (Splunk Cloud)

This is the one that had me stuck the longest. Splunk Cloud uses IP allow lists to control who can hit the management API on port 8089 - which is exactly the port the MCP server lives on (`/services/mcp`). If your IP isn't on the allow list, the connection just fails silently or you get cryptic errors.

Here's the thing - **your CLI's public IP is not necessarily the same as your browser's IP**. If you're making MCP calls from WSL, a remote server, or even just a terminal on the same machine, your outbound traffic might route through a completely different path than your browser. VPNs, split tunneling, corporate proxies - all of these can give you different public IPs depending on which app is making the request.

I kept trying to connect and getting nowhere. The MCP proxy would fail, I'd double-check my token, try again - nothing. Meanwhile the Splunk web UI worked fine in my browser. The issue was that my CLI's outbound IP wasn't on the Splunk Cloud IP allow list.

I didn't get a successful connection until I ran `curl ifconfig.me` and added that IP to the search head API allow list.

#### How to fix it

First, find your actual CLI public IP:

    
    curl ifconfig.me


That one command saved me. Whatever IP it returns is what Splunk Cloud sees when your MCP connection comes in. Compare that to what you see when you google "what's my IP" in your browser - if they're different, that's your problem.

Then add that IP to the **search-api** allow list in Splunk Cloud. You can do this through the Splunk Cloud admin UI, or via the ACS (Admin Config Service) API:

    
    # View current search-api allow list
    curl https://admin.splunk.com/YOUR-STACK/adminconfig/v2/access/search-api/ipallowlists \
      --header "Authorization: Bearer YOUR_ACS_TOKEN"

    # Add your CLI IP (use /32 for a single IP)
    curl -X POST https://admin.splunk.com/YOUR-STACK/adminconfig/v2/access/search-api/ipallowlists \
      --header "Content-Type: application/json" \
      --header "Authorization: Bearer YOUR_ACS_TOKEN" \
      --data '{"subnets": ["YOUR.CLI.IP.ADDRESS/32"]}'


Give it a few minutes to propagate, then try the MCP connection again. The `search-api` feature controls access to port 8089, which is what the MCP endpoint uses.

**Pro tip:** If you're on a corporate VPN that rotates IPs or uses a pool, you might need to add a broader CIDR range. Check with your network team for the right subnet.

### Localhost Error (Splunk Enterprise)

If you get a 500 error about "hostname localhost doesn't match," this is a known issue. When Splunk MCP receives a call, it makes an internal REST call back to itself - and if it doesn't know its own hostname, you get this error.

Fix it by adding a `base_url` config:

  1. Navigate to `$SPLUNK_HOME/etc/apps/Splunk_MCP_Server/local/`
  2. Create or edit `mcp.conf`
  3. Add:


    
    [server]
    base_url = https://YOUR-SPLUNK-HOST:8089/


This is a Splunk Enterprise issue - Splunk Cloud handles this differently.

### SSL Certificate Issues (Splunk Enterprise)

If you see "self-signed cert in chain" errors, your Splunk instance is using the default self-signed certificate on port 8089. There's a two-part call chain: your client calls Splunk over 8089, and then Splunk calls itself over 8089 to service the request. Both can fail on SSL.

**The right way:** Install a trusted certificate on port 8089 (see Splunk docs).

**The quick workaround:** Tell your MCP client to ignore SSL errors with the `NODE_TLS_REJECT_UNAUTHORIZED=0` environment variable (see client config section below). On the Splunk side, you may also need:

    
    export PYTHONHTTPSVERIFY=0 && splunk restart


As of MCP Server v0.2.4+, the Splunk-to-Splunk internal call handles self-signed certs via an `ssl_verify` setting in `mcp.conf`, so you should only need the client-side fix.

## Client-Side Configuration

The MCP server uses `mcp-remote` (an npm package) to bridge the remote Splunk endpoint to a local stdio connection that your AI tool can talk to. Most MCP-compatible tools support a `.mcp.json` config file, and some have their own CLI for managing servers.

### The `.mcp.json` File

Drop this in your project root or wherever your tool reads it from:

    
    {
        "mcpServers": {
          "splunk-mcp-server": {
            "command": "npx",
            "args": [
              "-y",
              "mcp-remote",
              "https://YOUR-INSTANCE.splunkcloud.com:8089/services/mcp",
              "--header",
              "Authorization: Bearer YOUR_TOKEN_HERE",
              "--timeout",
              "120000"
            ]
          }
        }
    }


Key settings:

  * **`--timeout 120000`** \- Set this to 2 minutes. The default is too short, especially for AI Assistant tools which can take 30+ seconds to respond.
  * **If you need to bypass SSL** (Splunk Enterprise with self-signed certs), add an `env` block: `json "env": { "NODE_TLS_REJECT_UNAUTHORIZED": "0" }`

#### WSL Gotcha

If you're running your AI tool inside WSL, the command should be `npx` directly. Do NOT wrap it with `wsl`. The `wsl` wrapper is only needed when running from Windows-native apps like Claude Desktop. I copied my Claude Desktop config over and it wouldn't connect until I removed the `wsl` wrapper.

    
    // WRONG (if already in WSL):
    { "command": "wsl", "args": ["npx", "-y", "mcp-remote", ...] }

    // RIGHT (if already in WSL):
    { "command": "npx", "args": ["-y", "mcp-remote", ...] }


### Claude Code CLI Method

Claude Code also has built-in MCP management:

    
    # Add the server
    claude mcp add splunk-mcp-server -- npx -y mcp-remote https://YOUR-INSTANCE.splunkcloud.com:8089/services/mcp --header "Authorization: Bearer YOUR_TOKEN_HERE" --timeout 120000

    # Scope options: local (default), user (cross-project), project (git-tracked)
    claude mcp add splunk-mcp-server --scope user -- npx -y mcp-remote ...

    # Import from Claude Desktop
    claude mcp add-from-claude-desktop

    # Manage servers
    claude mcp list
    claude mcp get splunk-mcp-server
    claude mcp remove splunk-mcp-server


## Testing Connectivity

### Step 1: Test the Proxy Directly

Before involving any AI tool, test the raw MCP connection:

    
    npx -y mcp-remote https://YOUR-INSTANCE.splunkcloud.com:8089/services/mcp \
      --header "Authorization: Bearer YOUR_TOKEN_HERE" \
      --timeout 120000


If it connects, you'll see:

    
    Connecting to remote server: https://YOUR-INSTANCE.splunkcloud.com:8089/services/mcp
    Using transport strategy: http-first
    Connected to remote server using StreamableHTTPClientTransport
    Local STDIO server running
    Proxy established successfully between local STDIO and remote StreamableHTTPClientTransport
    Press Ctrl+C to exit


If you see `Connected` and `Proxy established` \- the Splunk side is good. Hit Ctrl+C and move on. If this step fails, the problem is on the Splunk side (token, IP allow list, SSL) - don't bother troubleshooting your AI tool config until this works.

### Step 2: Test From Your AI Tool

In Claude Code, check server status:

    
    claude mcp list


You should see a green checkmark:

    
    splunk-mcp-server: npx -y mcp-remote ... - Connected


Inside a session, use `/mcp` to see connected servers and available tools.

### Step 3: Run a Simple Query

Ask your AI tool to call `splunk_get_info`. It's the lightest-weight call and will confirm the full pipeline works end-to-end. You should get back your instance version, server name, and health status.

## Troubleshooting Cheat Sheet

Symptom | Likely Cause | Fix  
---|---|---  
"spawn" errors, nothing launches | NPX not installed | `which npx` \- install Node.js if missing  
"insufficient permission" | RBAC misconfiguration | Check role, user, token audience (`mcp`)  
500 "hostname localhost doesn't match" | Missing base_url config | Add `base_url` to `mcp.conf` (Enterprise)  
"self-signed cert in chain" | Default SSL cert on 8089 | Install trusted cert or set `NODE_TLS_REJECT_UNAUTHORIZED=0`  
Silent failure, proxy won't connect | IP not on allow list | `curl ifconfig.me` and add to `search-api` allow list (Cloud)  
"Warning: ignoring invalid header" | Token has line breaks | Paste token in editor, ensure single line  
Tools return empty results | Tools disabled by admin | Check MCP Server tool visibility settings  
AI tools slow/empty | AI Assistant timeout | Increase `--timeout`, check AI Assistant app config  
Works in browser, fails in CLI | Different public IPs | Compare `curl ifconfig.me` vs browser IP  

Splunk also has a [troubleshooting video](https://www.youtube.com/watch?v=sIhjHAKM7Os) walking through the 4 most common setup failures in detail. Highly recommend watching it before you start.

## Version Notes

Splunk released **MCP Server v1.0.0** (GA) on Feb 4, 2026. Key changes from the beta versions:

  * **Encrypted tokens** \- Breaking change from beta. Old tokens won't work.
  * **Admin-controlled tool visibility** \- Admins can enable/disable individual MCP tools. If a tool returns empty or doesn't show up, this might be why.
  * **Tool name prefixes** \- Tools now include origin prefixes (e.g., `optimize_spl` became `saia_optimize_spl`).

Make sure you're on v1.0.0 and follow the [updated docs](https://help.splunk.com/en/splunk-cloud-platform/mcp-server-for-splunk-platform/about-mcp-server-for-splunk-platform).

## Resources

  * [Splunk MCP Server on Splunkbase](https://splunkbase.splunk.com/app/7931)
  * [Splunk MCP Troubleshooting Video](https://www.youtube.com/watch?v=sIhjHAKM7Os)
  * [MCP Server Documentation](https://help.splunk.com/en/splunk-cloud-platform/mcp-server-for-splunk-platform/about-mcp-server-for-splunk-platform)
  * [Leveraging Splunk MCP and AI - Splunk Lantern](https://lantern.splunk.com/Platform_Data_Management/Analysis_with_AI/Leveraging_Splunk_MCP_and_AI_for_enhanced_IT_operations_and_security_investigations)
  * [Claude Code MCP Configuration Docs](https://code.claude.com/docs/en/mcp)
  * [Splunk Cloud IP Allow List Configuration](https://help.splunk.com/en/splunk-cloud-platform/administer/admin-config-service-manual/10.2.2510/administer-splunk-cloud-platform-using-the-admin-config-service-acs-api/configure-ip-allow-lists-for-splunk-cloud-platform)

* * *

_Tools/Versions: Splunk Cloud v9.3.2411.123, Splunk MCP Server v1.0.0, Splunk AI Assistant for SPL v1.5.0, mcp-remote (latest via npx), WSL2 on Windows, Claude Code (Opus 4.6)_
