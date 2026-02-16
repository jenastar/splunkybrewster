---
layout: post
title: Modular Inputs That Don’t Make a Mess
date: '2014-07-15T09:00:00-07:00'
tags:
- splunk
- inputs
- apps
- design-patterns
permalink: /2014/07/modular-inputs-that-dont-make-mess.html
---

When I started building forwarder configurations for more than a handful of servers, I realized the default approach—stuffing `inputs.conf` into `system/local`—doesn’t scale. You get drift, conflicts, and no clear way to track ownership.

This post covers how we started modularizing inputs early in our Splunk journey, well before we had full deployment server automation. The goal was simple: isolate, name, and deploy clean inputs that didn’t overlap or clobber each other.

## Why system/local Shouldn’t Be Default

Putting all your configs in `system/local` is fine until someone else needs to touch it. Or until you have to roll back. Or explain why three apps are all monitoring the same folder differently.

If you're working in a shared environment, or one that might be audited or scaled, local configs become technical debt quickly.

## App-Level Inputs

We moved toward app-scoped inputs by creating one app per logical set of sources. For example:

- `TA_win_evtlogs`
- `TA_linux_syslog`
- `TA_iis_logs`

Each of these had its own directory structure and lived in `$SPLUNK_HOME/etc/apps/`.

Within each, only relevant files existed. No copied default files. No globals unless required.

```plaintext
TA_win_evtlogs/
├── default/
│   └── inputs.conf
TA_linux_syslog/
├── default/
│   └── inputs.conf
```

This let us:

- Know what team owned each input
- Quickly disable or reassign an app without editing shared files
- Make deployment atomic and testable

## Input Naming Discipline

We also adopted a standard for input stanza formatting:

```ini
[monitor:///var/log/httpd/access.log]
disabled = false
index = web_logs
sourcetype = apache_access
```

Inputs were never generic (`monitor:///logs/*`) unless we were prepared for wildcard ingestion and the mess that comes with it. Explicit is safer.

## Lessons Learned

- Build modular apps even before DS is enforced
- Every input should have a documented owner
- Avoid overlap—both in path coverage and stanza naming
- Use app naming to reflect purpose, not just project code names

---

This setup helped us transition smoothly to deployment server later—and made migrations, audits, and triage a lot faster.

If you’re just starting out with more than a dozen forwarders, don’t wait. Clean it up now. Future you will thank you.
