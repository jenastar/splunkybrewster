---
layout: post
title: Formatting LDAP Identity Data for Splunk Enterprise Security
date: '2016-10-24T08:00:00-07:00'
tags:
- splunk
- enterprise-security
- ldap
- assets-identities
- data-onboarding
permalink: /2016/10/formatting-ldap-identity-data-for.html
---

# Formatting LDAP Identity Data for Splunk Enterprise Security

Back when I first started configuring Splunk ES in a production environment, the identity lookup files were more than a checkbox—they were the heart of a good investigation workflow. LDAP is a common source for these identities, but it’s not plug-and-play. You’ve got to shape that data like a blacksmith if you want it to be useful in correlation searches and dashboards.

## Step One: Export From LDAP

You can pull data via a script or a tool like `ldapsearch`. Here’s a quick example of an export that gives us just what we need:

```bash
ldapsearch -x -LLL -H ldap://ldap.mycompany.local -b "ou=Users,dc=mycompany,dc=local" \
"(objectClass=person)" sAMAccountName displayName mail title department
```

This will pull out a good set of attributes, but we’re not done. You’ve got to normalize it.

## Step Two: Normalize and Rename Columns

Splunk ES expects a very specific format in your identities.csv file. You’ll want to map LDAP fields to the following ES-required and optional fields:

| Splunk Field         | LDAP Field        | Required |
|----------------------|-------------------|----------|
| `identity`           | `sAMAccountName`  | Yes      |
| `email`              | `mail`            | No       |
| `full_name`          | `displayName`     | No       |
| `start_date`         | (custom/manual)   | No       |
| `end_date`           | (custom/manual)   | No       |
| `watchlist`          | (tagged manually) | No       |
| `priority`           | (tagged manually) | No       |

Output it as a properly formatted CSV. Here’s a tiny example of what your output might look like:

```csv
identity,full_name,email,title,department,watchlist,priority
jsmith,John Smith,jsmith@company.com,Security Engineer,InfoSec,executive,high
adoe,Alice Doe,adoe@company.com,Analyst,Operations,,
```

## Step Three: Deploy the File

Once the CSV is prepped:

1. Place it into `$SPLUNK_HOME/etc/apps/Splunk_SA_CIM/lookups/`  
2. Or use a custom app, like `TA-identities`, to keep your configs separate and clean.
3. Make sure your `transforms.conf` references the lookup:
```ini
[identity_lookup]
filename = identities.csv
```

4. And confirm the `inputs.conf` or a scheduled script keeps it fresh.

## Bonus: Priority and Watchlists

You don’t need to wait for LDAP to tell you who’s important. Tag users manually by adding columns like `priority=high` or `watchlist=executive`. These fields can drive severity modifiers and notables in correlation searches.

## Lessons Learned

- Always **sanitize and trim** the data—LDAP fields can be messy.
- Use **lowercase usernames** for consistency with other data sources.
- Think about **how the data is used downstream**—your dashboards, correlation searches, and incident review queues will all thank you.

A well-tuned identities dataset is like having a company org chart baked into your SIEM. Don’t skip it.
