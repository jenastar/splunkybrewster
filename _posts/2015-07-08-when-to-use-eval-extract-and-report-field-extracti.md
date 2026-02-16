---
layout: post
title: 'When to Use EVAL, EXTRACT, and REPORT: Field Extraction Demystified'
date: '2015-07-08T08:00:00-07:00'
tags:
- splunk
- field extraction
- props.conf
- transforms.conf
permalink: /2015/07/when-to-use-eval-extract-and-report.html
---

In the early days of tuning Splunk, one of the most confusing topics wasn’t about indexing or search—it was field extractions. You’d look at some app’s `props.conf`, see `EVAL-*`, `EXTRACT-*`, and `REPORT-*`, and just kind of hope for the best.

This post breaks down what these mean, when each one runs, and why understanding the difference matters for performance, accuracy, and long-term sanity.

## The Landscape

There are three common ways to get custom fields in Splunk at search time:

- `EVAL-`  
- `EXTRACT-`  
- `REPORT-`

Each one does something different, and knowing when to use each will save you a ton of trial-and-error.

## EVAL-: Create or Transform Fields Using Logic

Think of this as computed fields. You’re not extracting something from the raw event—you’re creating a new value based on logic.

```ini
EVAL-action = if(status=200, "success", "failure")
EVAL-source_ip = mvindex(split(src_field, ":"), 0)
```

- Good for: basic if-then logic, regex replacement, conditional labels
- Bad for: pulling values out of event text

## EXTRACT-: Inline Regex Field Extraction

This is a one-liner that applies a regular expression directly.

```ini
EXTRACT-userinfo = user=(?P<user>\w+) role=(?P<role>\w+)
```

- Good for: quick one-offs, self-contained regexes
- Bad for: anything complex, multiple sourcetypes using the same logic

## REPORT-: Use External Transforms for Complex Extractions

This points to a `[stanza]` in `transforms.conf` that contains your regex logic.

### props.conf

```ini
[my_sourcetype]
REPORT-userinfo = user_fields
```

### transforms.conf

```ini
[user_fields]
REGEX = user=(?P<user>\w+) role=(?P<role>\w+)
```

- Good for: reusability, shared transforms across sourcetypes, long regexes
- Bad for: debugging in the GUI (requires some inspection)

## When to Use Each

| You Want To...                           | Use...    |
|------------------------------------------|-----------|
| Create new values based on logic         | `EVAL-`   |
| Extract a few fields from short events   | `EXTRACT-`|
| Reuse complex regexes across sourcetypes | `REPORT-` |

## A Real Example

We were indexing syslog from 40+ network devices. Each vendor had their own slightly mutated log format. Trying to `EXTRACT-` everything inline turned into a maintenance nightmare.

Instead, we grouped the devices into sourcetypes and used `REPORT-` to apply vendor-specific regexes. That way, if someone updated a device firmware and changed a field, we just edited the corresponding transform.

## TL;DR

- `EVAL-` is logic-based  
- `EXTRACT-` is inline regex  
- `REPORT-` is pointer to external regex  

Get these wrong and your fields will be inconsistent, your dashboards will break, and your future self will curse your name.

Get them right and everything flows.
