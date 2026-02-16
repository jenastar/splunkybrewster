---
layout: post
title: Routing Logs to Multiple Indexes with props.conf and transforms.conf
date: '2015-06-12T08:00:00-07:00'
tags:
- splunk
- props.conf
- transforms.conf
- index-routing
permalink: /2015/06/routing-logs-to-multiple-indexes-with.html
---

By 2015, our Splunk deployment had grown out of its “default everything” phase. We had multiple teams asking for different log sources in different indexes—some wanted structured JSON, others were slinging ancient flat files. We couldn’t just let everything pile into `main`.

This post outlines how we used `props.conf` and `transforms.conf` to route logs to multiple indexes from a single universal forwarder (UF), based on file path, sourcetype, or even content inside the log.

## The Problem

You’ve got one UF on a shared box. It’s picking up logs for both your app team and your security team. They want their logs separated into `app_index` and `security_index`, but you don’t want to stand up a second UF or duplicate data. You need routing.

## Tools You Need

- `props.conf` to match log characteristics (source, sourcetype, etc.)
- `transforms.conf` to decide what to do when a match happens

## Example 1: Route by Source Path

### props.conf

```ini
[source::/var/log/app_logs/*]
TRANSFORMS-routing = app_index

[source::/var/log/security_logs/*]
TRANSFORMS-routing = security_index
```

### transforms.conf

```ini
[app_index]
REGEX = .
DEST_KEY = _MetaData:Index
FORMAT = app_index

[security_index]
REGEX = .
DEST_KEY = _MetaData:Index
FORMAT = security_index
```

We’re using `REGEX = .` here to match anything—we’ve already scoped it in `props.conf` by source path.

## Example 2: Route by Content Inside the Log

Maybe your app team dumps all logs into a single folder, but security events are tagged inside the message body.

### props.conf

```ini
[source::/var/log/shared_logs/*]
TRANSFORMS-routing = security_match
```

### transforms.conf

```ini
[security_match]
REGEX = SECURITY_EVENT
DEST_KEY = _MetaData:Index
FORMAT = security_index
```

Now only lines containing `SECURITY_EVENT` are routed to `security_index`. The rest go to your default index.

## Example 3: Mixed Inputs, Clean Routing

We had to support a Frankenstein box with Windows Event Logs, IIS logs, and some legacy `.csv` input. Here’s a basic example of combining methods:

### props.conf

```ini
[sourcetype::WinEventLog:Security]
TRANSFORMS-routing = winsec_index

[host::iis-web*]
TRANSFORMS-routing = web_index
```

### transforms.conf

```ini
[winsec_index]
REGEX = .
DEST_KEY = _MetaData:Index
FORMAT = windows_security

[web_index]
REGEX = .
DEST_KEY = _MetaData:Index
FORMAT = iis_logs
```

## Important Notes

- You must define the destination indexes in `indexes.conf` beforehand, or events will silently drop.
- These configurations go on **indexers**, not forwarders.
- Always test with `btool` and review `_internal` logs to make sure routing is working.

## Debugging Tips

- Use a temporary index like `test_routing` during setup
- Drop test files into watched paths and `index=* sourcetype=* host=*` them
- If routing isn’t working, check:
  - `props.conf` and `transforms.conf` spelling/case
  - File path matching (e.g., are slashes correct?)
  - Indexers were restarted after config change

## TL;DR

Routing is about scope and specificity.  
`props.conf` sets the condition → `transforms.conf` sets the action.  
Once you get the pattern down, you’ll never look at default indexing the same way again.
