---
layout: post
title: 'The First Time I Broke All the Dashboards: Lessons in Field Normalization'
date: '2015-12-18T08:00:00-07:00'
tags:
- splunk
- field normalization
- dashboards
- data hygiene
permalink: /2015/12/the-first-time-i-broke-all-dashboards.html
---

Back in 2015, I broke every dashboard in production. The cause? A single field name change.

We were cleaning up sourcetypes and decided to rename `src_ip` to `source_ip` for consistency. It seemed harmless—until half the dashboards threw errors and users lost their minds.

## What I Learned

- Dashboards don’t auto-adjust to new field names
- Changing field names at search time is better than at ingest
- Normalization layers (e.g., CIM) help but must be planned from day one

## Mitigation Tips

- Use `alias` and `rename` in saved searches  
- Standardize field names in one place—don’t wing it  
- Test dashboards before and after every change

## TL;DR

Field name changes break dashboards. Normalize early, and never change a field name without understanding who depends on it.