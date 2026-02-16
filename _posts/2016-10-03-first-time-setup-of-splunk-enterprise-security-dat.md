---
layout: post
title: 'First-Time Setup of Splunk Enterprise Security: Data Models, CIM, and Taming
  the Noise'
date: '2016-10-03T08:00:00-07:00'
tags:
- splunk
- enterprise-security
- cim
- correlation
- security
permalink: /2016/10/first-time-setup-of-splunk-enterprise.html
---

# First-Time Setup of Splunk Enterprise Security: Data Models, CIM, and Taming the Noise

After installing Splunk Enterprise Security (ES) for the first time, it becomes immediately clear: this isn’t just another app. It’s a full-blown framework layered on top of Splunk—and if you don’t get your data in order, you’ll be buried in noise.

This post documents my initial setup of ES 4.1 on top of Splunk Enterprise 6.4.2. It focuses on the *early critical steps*: controlling data model acceleration, prepping CIM-compliant data, and tagging for correlation searches.

---

## Step 1: Turn Off the Firehose

Out of the box, every data model is **accelerated by default**. If you're standing up ES for the first time, this will:

- Hammer your indexers
- Consume disk space for summaries you may not use
- Populate dashboards with empty visualizations

### First move: disable all data model accelerations.

You can do this from:

> **Enterprise Security → Configuration → Data Models**

Click into each model (e.g. `Authentication`, `Endpoint`, `Network_Traffic`) and uncheck “Accelerate”. Once that’s done, you can selectively re-enable acceleration later once the associated data is known-good and mapped.

---

## Step 2: Normalize Your Inputs with CIM

Enterprise Security assumes **Common Information Model (CIM)** compliance.

This means your logs aren’t useful until they’ve been:

- Parsed into normalized field names (e.g. `src`, `dest`, `user`)
- Tagged correctly (e.g. `tag=authentication`, `tag=network`)

Most of this normalization comes from **Splunk Technology Add-ons (TAs)**—you’ll want the right TA installed and deployed to your forwarders for each data source.

For example:

| Data Source       | TA Used                  | CIM Data Model        |
|-------------------|--------------------------|------------------------|
| Windows logs      | `Splunk_TA_windows`      | `Authentication`      |
| Syslog (Linux)    | `Splunk_TA_nix`          | `Endpoint`            |
| Palo Alto Firewalls | `Splunk_TA_paloalto`   | `Network_Traffic`     |

---

## Step 3: Tags and Event Types Are Your Lifeline

A lot of people miss this: ES correlation searches don’t match on raw sourcetype or index.

They match on:

- **Tags** (e.g. `tag=authentication`)
- **Event types** that apply the right tags
- **CIM-compliant fields**

So if your logs are indexed and parsed but don’t show up in dashboards or correlation searches? It’s probably a tag issue.

Use `| tstats` with `tag=*` to check what’s being picked up.

Example:

```spl
| tstats count where tag=authentication by sourcetype
```

If that returns nothing, it means your data isn’t mapped correctly into ES’s world.

---

## Step 4: Asset and Identity Lookups

Correlation in ES is contextual—it’s not just IPs and usernames, it’s *who they belong to*.

At this stage I created simple CSV files for:

- **Asset inventory** (mapping IPs to hosts and priorities)
- **Identity mapping** (linking usernames to email, dept, location)

These were imported via **Lookup Editor** or dropped into `$SPLUNK_HOME/etc/apps/SA-IdentityManagement/lookups`.

Start simple. You can script the refreshes later.

---

## The First Useful Correlation

Once I had basic Windows and Linux logs coming in and properly tagged, the following correlation search fired:

> “Multiple Failed Logins Across Hosts”

It wasn’t noise. It was legit. I had a test account with bad creds—and the system caught it. That moment confirmed ES wasn’t just visual candy—it worked when fed the right data.

---

## Takeaways

- **Disable all DM accelerations** until you verify log quality
- **Tags and field names** matter more than indexes and sourcetypes
- **CIM normalization is mandatory** for anything in ES to work as expected
- **Start lean**—don’t onboard 15 data sources until 1 is working right

Getting ES running isn’t hard, but getting it *useful* takes discipline. It’s not plug-and-play—it’s map-and-verify.
