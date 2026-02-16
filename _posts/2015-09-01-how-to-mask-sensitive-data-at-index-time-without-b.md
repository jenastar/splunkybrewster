---
layout: post
title: How to Mask Sensitive Data at Index Time (Without Breaking Your Regexes)
date: '2015-09-01T08:00:00-07:00'
tags:
- splunk
- transforms.conf
- masking
- data privacy
permalink: /2015/09/how-to-mask-sensitive-data-at-index.html
---

Masking sensitive data in Splunk can be tricky—you need to remove or obfuscate values like passwords, account numbers, or PII before they’re indexed. The challenge? Doing it without breaking your field extractions or damaging legitimate log content.

This guide walks through the use of `props.conf` and `transforms.conf` to mask values at index time using regular expressions.

## Why Mask at Index Time?

- Prevent sensitive info from being stored or searched
- Maintain compliance with internal security policies
- Avoid post-ingest cleanup (which is painful)

## Basic Setup

This is a lot like routing to `nullQueue`, except instead of dropping the event, we rewrite part of it.

### props.conf

```ini
[sourcetype::secure_logs]
TRANSFORMS-mask = mask_passwords
```

### transforms.conf

```ini
[mask_passwords]
REGEX = (?i)(password=)[^&\s]+
FORMAT = $1********
DEST_KEY = _raw
```

This finds `password=whatever` and replaces the value with `********`.

## Use Case: API Keys in Debug Logs

Let’s say your logs occasionally include URLs with embedded API keys:

```
GET /api/data?apikey=1234567890abcdef
```

You can mask them like this:

```ini
REGEX = (?i)(apikey=)[^&\s]+
FORMAT = $1[REDACTED]
DEST_KEY = _raw
```

## Caution

- Make sure your regex is precise—don’t mask more than you meant to
- If field extractions depend on the masked value, update them too
- Always test on a dev indexer before promoting

## TL;DR

Masking at index time is a clean way to scrub sensitive content before it hits disk. Just be surgical with your regex and validate everything before rollout.