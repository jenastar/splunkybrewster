---
layout: post
title: 'Heavy Forwarders vs Indexers: Where Should Parsing Happen?'
date: '2015-11-01T08:00:00-07:00'
tags:
- splunk
- heavy forwarder
- indexer
- architecture
permalink: /2015/11/heavy-forwarders-vs-indexers-where.html
---

In Splunk architecture, parsing happens at index time—but *where* that parsing takes place can make or break performance. The key decision: heavy forwarder vs indexer.

## What Is Parsing?

Parsing includes:
- Line breaking
- Timestamp extraction
- Event boundaries
- Application of `props.conf` and `transforms.conf`

## Option 1: Let Indexers Parse

The default approach. Universal forwarders just send raw data, indexers do the heavy lifting.

✅ Simpler  
✅ Easier to scale  
❌ Can bottleneck indexers if volume is high

## Option 2: Heavy Forwarder Does Parsing

The heavy forwarder parses and routes events (especially useful for `nullQueue`, routing, or early transforms).

✅ Offloads indexers  
✅ Needed for some use cases  
❌ Adds complexity  
❌ More places to troubleshoot

## Our Rule of Thumb

- Use indexers unless you *need* routing or transforms
- Use HF for edge cases, but document clearly
- Never mix parsing configs across UF and HF without strict boundaries

## TL;DR

Push parsing to indexers unless there’s a reason not to. If you need `nullQueue`, field rewrites, or selective routing, then a heavy forwarder makes sense.