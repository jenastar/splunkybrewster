---
layout: post
title: 'Boots on the Ground: End-to-End MCP Discovery with Shodan and Python'
date: '2025-07-22T10:00:00-07:00'
tags:
- python
- shodan
- mcp
- security
- automation
permalink: /2025/07/boots-on-ground-end-to-end-mcp.html
---

## Introduction

In modern cybersecurity operations, blind spots can be catastrophic. If your organization relies on Model Context Protocol (MCP) services—whether for AI-driven decisioning, context-aware microservices, or proprietary pipelines—you need full visibility into every exposed endpoint. This post walks through an automated, two-step MCP discovery workflow using Shodan and Python, so you can pinpoint, verify, and inventory MCP servers before adversaries do. Consider this your reconnaissance mission briefing: boots on the ground, eyes on target.

## Why Perform MCP Discovery?

- **Attack Surface Reduction**  
  Exposed MCP endpoints can be leveraged for unauthorized data access, lateral movement, or even remote execution if misconfigured.  
- **Compliance & Audit**  
  Regularly auditing MCP hosts helps you demonstrate due diligence and maintain compliance with frameworks like SOC 2 or ISO 27001.  
- **Operational Awareness**  
  Discovering and cataloging live MCP instances feeds into SIEM alerts, asset inventories, and incident response playbooks.

## Fingerprinting Methods

In any field operation, knowing what you’re up against is half the battle. We use a Shodan-powered fingerprinting sweep to collate a list of candidate hosts:

1. **Pre-Flight Check**  
   - Store your `SHODAN_API_KEY` in a `.env`.  
   - Validate with `api.info()` and a quick `api.search('http.title:"test"')` to ensure credentials and search capability are good to go.

2. **Targeted Query Patterns**  
   Based on common MCP footprints and server types, we probe for:  
   - **HTML text fingerprints:**  
     - `http.html:"mcp"`  
     - `http.html:"Model Context"`  
     - `http.html:"jsonrpc"`  
   - **Endpoint indicators:**  
     - `http.html:"/mcp"`  
     - `http.html:"/api/mcp"`  
   - **ASGI server headers:**  
     - `http.headers.server:"uvicorn"`  
     - `http.headers.server:"fastapi"`  

3. **Result Aggregation**  
   Each query runs through `tqdm` for progress feedback. We collect unique IPs into `potential_mcp_hosts.json`—your dossier of suspects for the next phase.

_For the full reconnaissance script and environment setup, see the repo: [github.com/your-org/shodan_mcp_discovery](https://github.com/your-org/shodan_mcp_discovery)._

## MCP Handshake Verification

With suspects in hand, it’s time to confirm who’s actually running MCP. Our `mcp_func_checker.py` script:

- Iterates through `potential_mcp_hosts.json` with a `tqdm` progress bar.  
- Attempts a JSON-RPC `initialize` handshake against several endpoints (`/`, `/mcp`, `/api/mcp`, `/sse`, `/v1/messages`).  
- Validates a `200 OK` response containing the expected `{"jsonrpc":"2.0","id":1,"result":{…}}` structure.  
- Logs confirmed hosts to `confirmed_mcp_servers.json`.

Here’s the live-fire output you’ll see when the script locks on active MCP servers:

<pre><code class="language-bash">
(venv) jenastar@magrathea:/mnt/c/Users/jenas/dev/shodan_mcp_discovery$ python3 mcp_func_checker.py
Verifying MCP servers:   38%|█████████████████████████▍                          | 339/881 [46:55<1:01:44,  7.78s/it]
Verifying MCP servers:  100%|██████████████████████████████████████████████████| 881/881 [1:54:17<00:00,  7.78s/it]
→ Confirmed 3 MCP servers.
→ confirmed_mcp_servers.json written.
</code></pre>

Think of this as your “all clear” report before bringing in the heavy armor.

## Outcome & Next Steps

- **Confirmed Servers:** You now have a concise list of live MCP endpoints to review.  
- **Alerting & Monitoring:** Ingest `confirmed_mcp_servers.json` into your SIEM or monitoring platform for continuous watch.  
- **Remediation:** Validate configurations, rotate credentials, or apply network ACLs to lock down unauthorized instances.  
- **Automation:** Schedule this workflow via cron, CI/CD pipelines, or Splunk Orchestration to keep your MCP inventory fresh.

This end-to-end approach—from Shodan fingerprinting to JSON-RPC handshake verification—gives you the situational awareness you need to stay ahead of the threat. Carry on.  
