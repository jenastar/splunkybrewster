---
layout: post
title: 'Managing Precedence in Splunk: Input Routing When Multiple Teams Share Ownership'
date: '2018-04-09T08:00:00-07:00'
tags:
- splunk
- tcp-routing
- deployment
- inputs
permalink: /2018/04/managing-precedence-in-splunk-input.html
---

In environments where multiple teams share management of a Universal Forwarder, configuration precedence becomes critical. This post documents a routing setup that supports inputs required by both Team1 and our internal Splunk operations team, using Splunk’s native TCP routing and configuration layering.

This isn’t a walkthrough of Splunk’s documentation. It’s a pattern that works under pressure, where config overlap and unclear ownership can create race conditions and missed logs.

## Background

Team1 manages their own application stack and needs logs shipped to their Splunk Cloud. At the same time, we need access to those same logs through our Cribl pipeline for enrichment and correlation. Both groups require overlapping sources but control different pieces of the pipeline.

We used a combination of:
- `_TCP_ROUTING` at the stanza level in `inputs.conf`
- Deployment server-managed outputs
- Deliberate app naming to control config precedence

## Configuration: Inputs

Here’s a basic input definition with explicit routing to both destinations:

```ini
[monitor://D:\logs\IIS]
sourcetype = iis
index = web_servers
_TCP_ROUTING = splunkcloud_1, cribl_pipeline
```

Each `_TCP_ROUTING` target must be defined in `outputs.conf`:

```ini
[tcpout:splunkcloud_1]
server = team1-ingest1.cloud.splunk.com:9997

[tcpout:cribl_pipeline]
server = internal-cribl01.company.com:9997
```

## Configuration: App Structure

To manage precedence, we split config responsibility between two apps:

- `Z_team1_input_bundle`: Team1-owned, unmanaged input definitions
- `Y_security_routing_core`: DS-managed, includes default routing and outputs

App names are intentionally prefixed (`Z_`, `Y_`) to ensure loading order. Splunk applies configuration based on this precedence:

1. `$SPLUNK_HOME/etc/system/local`
2. `$SPLUNK_HOME/etc/apps/[app]/local`
3. `$SPLUNK_HOME/etc/apps/[app]/default`
4. `$SPLUNK_HOME/etc/system/default`

Team1’s configs live in `/local/`, and ours are managed via `/default/`. This lets them define their own monitors while we maintain global output routing and fail-safe defaults.

## Deployment Details

- Team1’s inputs are deployed manually or through their config management
- We use the deployment server to push our output definitions and any overrides
- Both teams are responsible for avoiding path collisions and coordinate source definitions

## Key Points

- Always isolate team-specific inputs into their own app directory
- Use `_TCP_ROUTING` only when multiple destinations are required—don’t default to system-wide dual output unless intentional
- Control app load order through naming. It’s basic, but effective.
- Validate by running `btool` with `--debug` to confirm final active configs

This setup has been stable across multiple forwarders. It also scaled well once we integrated Cribl inline between UF and our core indexers.