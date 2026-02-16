---
layout: post
title: Managing Source Types Across Teams Without Losing Your Sanity
date: '2015-10-01T08:00:00-07:00'
tags:
- splunk
- sourcetypes
- team practices
- data onboarding
permalink: /2015/10/managing-source-types-across-teams.html
---

Sourcetypes are the lifeblood of a well-functioning Splunk deployment—but when multiple teams are onboarding data, things can get messy fast.

Here’s how we kept things sane when different groups were sending logs to shared infrastructure.

## Rule #1: One Format, One Sourcetype

If you have three apps sending logs that *look* the same, use one sourcetype. If one app changes the format—give it a new sourcetype.

Avoid generic types like `syslog`, `logfile`, or `json_input`.

## Rule #2: Prefixes for Ownership

We adopted a naming scheme like this:

```
teamx:appname:logtype
```

Example:

```
payments:stripe:api
auth:okta:web
```

This gave everyone clarity and avoided ownership collisions.

## Rule #3: Lock Down `props.conf`

Don’t let every team push their own sourcetype settings unless you trust them deeply. Centralize it or use deployment server scoping.

## Real-World Burn

We once had two teams using `sourcetype=syslog` with totally different log formats. One team’s field extractions started breaking the other’s dashboards. It took us a week to realize the problem was a shared sourcetype.

## TL;DR

- Unique sourcetypes per format
- Naming conventions reduce chaos
- Control access to shared configs