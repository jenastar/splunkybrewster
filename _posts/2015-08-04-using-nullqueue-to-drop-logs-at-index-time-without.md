---
layout: post
title: Using nullQueue to Drop Logs at Index Time Without Touching the Source
date: '2015-08-04T08:00:00-07:00'
tags:
- splunk
- nullQueue
- index-time routing
- transforms.conf
permalink: /2015/08/using-nullqueue-to-drop-logs-at-index.html
---

At some point, you realize Splunk doesn’t need *everything*. Maybe it’s verbose debug logs, noisy health checks, or irrelevant metadata cluttering your indexes and costing you license. The good news? You can tell Splunk to drop data *before* it ever hits disk—without modifying the source or touching the forwarder.

This is where routing to `nullQueue` comes in.

## What Is `nullQueue`?

It’s a built-in queue in Splunk that acts like a black hole. If you route events to it, they’re never indexed. No disk, no license, no nothing.

## Where Does This Happen?

This is **index-time** logic, so the config belongs on the **indexer** (or heavy forwarder, if you use one). Universal forwarders won’t do anything with it.

## The 3-Step Setup

You’ll need two files:  
- `props.conf` to match the event  
- `transforms.conf` to define the routing

## Example 1: Drop Events by Keyword

Let’s say you want to drop any event that contains `"DEBUG"`.

### props.conf

```ini
[sourcetype::my_logs]
TRANSFORMS-null = drop_debug
```

### transforms.conf

```ini
[drop_debug]
REGEX = DEBUG
DEST_KEY = queue
FORMAT = nullQueue
```

Now any event matching that regex will be discarded before indexing.

## Example 2: Drop Events by Source Path

Say you don’t want to index anything from `/var/log/test_env/*`.

### props.conf

```ini
[source::/var/log/test_env/*]
TRANSFORMS-null = drop_test_logs
```

### transforms.conf

```ini
[drop_test_logs]
REGEX = .
DEST_KEY = queue
FORMAT = nullQueue
```

Match everything from that path and send it to the void.

## Caveats

- The event still makes it through parsing. You’re saving license, not network bandwidth.
- If your regex isn’t precise, you could drop valid data—test it first.
- Don’t forget to reload or restart the indexer for changes to take effect.

## Real-World Use Case

We once onboarded a third-party app that logged health checks every 5 seconds. After indexing 3GB of “app is fine” messages in a day, we decided enough was enough. We routed anything with `"health_check=true"` to `nullQueue` and immediately cut our license usage for that app by 80%.

## TL;DR

- Use `nullQueue` to drop noisy or useless events
- Match them in `props.conf`, route them in `transforms.conf`
- It’s one of the most powerful (and underused) Splunk tricks in the toolbox
