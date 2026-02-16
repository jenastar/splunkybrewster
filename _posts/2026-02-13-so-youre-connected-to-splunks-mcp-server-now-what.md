---
layout: post
title: So You're Connected to Splunk's MCP Server - Now What?
date: '2026-02-13T09:00:00-08:00'
tags:
- splunk
- ai
- mcp
- workflow
- security
permalink: /2026/02/so-youre-connected-to-splunks-mcp_0454109778.html
---

You got the proxy running. The green checkmark appeared. `splunk_get_info` came back with your instance version and a healthy status. Now you're staring at a blinking cursor wondering what exactly you're supposed to do with this thing.

The setup guides all end at "you're connected." Here's what happens after that, and honestly, some of it caught me off guard.

## The Toolbox

Here's what you get once the MCP server is connected. I'm running v1.0.0 with Claude Code as the client.

| Tool | What It Does | Status |
|------|-------------|--------|
| `run_splunk_query` | Execute SPL and get results | Working |
| `get_indexes` | List all indexes | Working |
| `get_index_info` | Details on a specific index | Working |
| `get_metadata` | Pull hosts, sources, or sourcetypes | Working |
| `get_knowledge_objects` | Saved searches, macros, data models, lookups | Working |
| `get_kv_store_collections` | KV store collection stats | Working |
| `get_user_info` | Current user details and roles | Working |
| `splunk_get_info` | Instance version, server name, health | Working |
| `saia_generate_spl` | Generate SPL from natural language | Not returning results* |
| `saia_optimize_spl` | Optimize a query for performance | Not returning results* |
| `saia_explain_spl` | Explain SPL in plain English | Not returning results* |
| `saia_ask_splunk_question` | Ask Splunk questions in natural language | Not returning results* |

*The `saia_` tools come from the Splunk AI Assistant for SPL app. As of this writing, all four return empty results through MCP despite the app being installed and the tools being visible. Waiting on Splunk to sort this out. The core tools more than carry their weight in the meantime.

## Map Your Entire SIEM in 60 Seconds

This is the thing that made me sit up straight the first time.

I asked my AI tool to show me what data I had. Behind the scenes it called `get_indexes`, then ran a `tstats` query to get event counts. In about ten seconds I was looking at this:

| Index | Events/sec | 24h Volume |
|-------|-----------|------------|
| network-firewall | 7,699 | 665M |
| linux | 4,457 | 385M |
| network-fw-secondary | 2,749 | 237M |
| endpoint-wineventlog-security | 1,334 | 115M |
| dns | 1,334 | 115M |
| cloud-saas-activity | 1,264 | 109M |
| cloud-azure | 1,261 | 108M |
| endpoint-casb | 950 | 82M |
| cloud-aws-cloudtrail | 438 | 37M |

That's a complete picture of an enterprise SIEM's ingestion. Every index, ranked by volume, with events-per-second math. And I didn't open a browser. I didn't click Settings > Indexes. I didn't write any SPL. I asked a question in English and got the answer.

From there I asked "drill into the CloudTrail index" and `get_metadata` came back with 42 million events spanning back to 2018, all flowing through a single sourcetype. Five seconds of work that would have been two minutes of clicking in the web UI. Not life-changing on its own, but when you do this fifty times a day, it adds up fast.

## Talking to Your Data

This is where it gets genuinely fun.

### The Iterative Pattern

In the Splunk search bar, the workflow is: write query, run it, squint at results, edit the query, run it again. It works. It's also slow when you're exploring.

With MCP, you just... talk. I started with:

> "What are the top CloudTrail API calls in the last 24 hours?"

Back came the results. AssumeRole at 7 million, followed by DescribeInstances, GetSecretValue, ListClusters. Normal stuff. Then I asked:

> "Now show me which of those had errors."

It pivoted the query, kept the context. AccessDenied on AssumeRole: 1.9 million. That's a lot. So:

> "Who's getting all those AccessDenied errors?"

And now I'm looking at a ranked list of IAM roles generating access denied errors. The top offenders were Karpenter nodes and Datadog integration roles. Noisy but expected. But I spotted it in thirty seconds because I didn't have to retype the base query three times.

Each prompt builds on the last. The AI tool remembers what index you're in, what filters you applied, what fields you care about. You're having a conversation with your data instead of editing a search string. It's a different experience.

### Catching Things You Weren't Looking For

I asked to see high-risk CloudTrail API calls: `RunInstances`, `TerminateInstances`, `DeleteBucket`, `CreateUser`. Expected to see a mix of routine automation.

What came back was an autoscaler churning through 575+ `RunInstances` calls per session, spinning up new instances every few seconds across a single region. That's not suspicious. It's Karpenter doing its job in an EKS cluster. But it's the kind of pattern you notice when you can pivot quickly. If that had been an IAM user instead of a service role? Different conversation entirely.

The point is: I wasn't hunting for autoscaler behavior. I was doing a quick audit of destructive API calls. But because the iteration loop is so fast, I could follow the thread in real time instead of noting it down and coming back later.

### Console Login Audit in One Sentence

I asked: "Show me everyone who logged into the AWS console in the last 7 days."

Ten seconds later I had every ConsoleLogin event with the user's ARN, source IP, and whether it succeeded or failed. Who's logging in, from where, and how often. That's a question that normally means opening CloudTrail in the AWS console or writing SPL from scratch. Here it was one English sentence.

## Knowledge Object Reconnaissance

This one snuck up on me.

`get_knowledge_objects` pulls saved searches, macros, data models, lookups. All the stuff that lives under Knowledge Manager in the web UI. I initially thought "when would I use this?" and then started using it constantly.

The environment I work in has over 1,000 saved searches and 1,000+ macros. There are pre-trained ML models for DGA detection, DNS exfiltration, and suspicious process names. There are VirusTotal correlation searches. There are coverage reporting searches that track which data sources are healthy.

I discovered all of this by asking questions like "what saved searches exist for authentication?" and "show me the data models." No clicking through Knowledge > Saved Searches and paginating through results. No guessing what someone named their macro.

When I'm about to build a new detection, the first thing I do now is ask what already exists. It's saved me from rebuilding things at least three times so far.

## The Stuff That Matters Day to Day

After a few weeks of daily use, these are the patterns I keep coming back to:

**Metadata first, queries second.** Before writing any SPL, I use `get_indexes`, `get_metadata`, and `get_knowledge_objects` to understand the landscape. Five minutes of reconnaissance saves thirty minutes of guessing at field names and sourcetypes.

**Let the AI write the first draft.** Describe what you want in conversation and let the AI tool build the SPL. It knows the syntax, it remembers your context, and you'll catch the logic errors during review instead of during authoring.

**Keep queries tight.** The MCP round trip has latency. A few seconds per call, more for heavy searches. Use aggregation commands (`stats`, `timechart`, `top`) and `| head` to keep results manageable. Build iteratively with focused queries rather than one monolithic search.

**Know when to switch to the web UI.** MCP is great for exploration, investigation, and ad-hoc queries. For building dashboards, managing alerts, exporting large datasets, or visual analysis with charts, the web UI is still the right tool. MCP doesn't replace Splunk. It makes the parts you do most often faster.

## What's Next

The MCP server is at v1.0.0 and the core tools already deliver real value. Once the AI Assistant tools start returning results, there'll be an even stronger story around SPL generation and optimization. For now, the combination of `run_splunk_query`, the metadata tools, and `get_knowledge_objects` has genuinely changed how I interact with Splunk day to day.

If you haven't set it up yet, the [setup guide](https://splunkbase.splunk.com/app/7931) covers installation and connectivity. If you're staring at a green checkmark wondering what to do next, ask it to map your indexes. Then follow the thread.

---

*Splunk MCP Server v1.0.0 | Claude Code | WSL2*
