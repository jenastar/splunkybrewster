---
layout: post
title: Tuning Assets and Identities in Enterprise Security
date: '2016-10-19T00:00:00-07:00'
permalink: /2016/10/tuning-assets-and-identities-in.html
---

# Tuning Assets and Identities in Enterprise Security

After getting Splunk Enterprise Security up and running, one of the most critical steps for meaningful correlation is getting your **assets and identities** data right. If ES doesn’t know *who* or *what* it's looking at, your notables won't carry much weight—and worse, they might lead to wild goose chases.

---

## The Setup: Initial Confusion

The first time I configured Enterprise Security, I assumed the default asset and identity setup would “just work.” It doesn’t. You need to:

- Load your own asset and identity data
- Normalize it to CIM standards
- Configure priority fields
- Understand how correlation searches actually *use* those fields

---

## CSV Is King (For Now)

Most orgs I worked with back in 2016 didn’t have a clean, queryable CMDB or authoritative identity store. That meant falling back to CSV files, which thankfully Splunk makes easy to manage:

- `/opt/splunk/etc/apps/SA-IdentityManagement/lookups/assets.csv`
- `/opt/splunk/etc/apps/SA-IdentityManagement/lookups/identities.csv`

Once loaded, those files populate lookup definitions like `assets_lookup_by_str` and `identity_lookup_expanded`.

You can view the configuration under:

```
Settings → Lookups → Lookup definitions
```

---

## Key Fields That Matter

Assets:
- `ip`
- `mac`
- `nt_host`
- `dns`
- `asset_tag`
- `category`
- `priority`

Identities:
- `identity`
- `email`
- `endDate`
- `watchlist`
- `category`
- `priority`

The `priority` field, in particular, drives notable event urgency if configured.

---

## Correlation Relevance

Many correlation searches rely on tags like `privileged`, `contractor`, or `critical_asset` to properly fire or suppress alerts. Those tags come from your asset/identity data—so if your data is missing or misclassified, alerts either won’t fire, or you’ll get flooded with noise.

Also, if you *don’t* have meaningful context around a machine or user, it's hard to tell if that login from China was normal or not.

---

## Pro Tip: CIM Normalization is Required

Enterprise Security doesn’t work out-of-the-box unless your data is CIM-compliant. That means:

- Your fields have to match CIM expectations (e.g., `src`, `user`, `action`)
- Your data models must be **populated** and **accelerated** properly

By default, *all* data model accelerations are turned on. This will hurt performance if you don’t tune them.

Go to:

```
Settings → Data Models → Edit Acceleration
```

...and turn off everything you’re not using. Then selectively enable accelerations as needed.

---

## Wrap-Up

You can’t skip assets and identities. If your correlation searches are throwing weak or irrelevant notables, chances are your context is off—or missing completely. Getting this tuned was a turning point in my early ES work, and it immediately boosted both fidelity and trust in alerts.

The faster you tune your context, the faster you get value from ES.
