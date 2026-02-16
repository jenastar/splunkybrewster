---
layout: post
title: Consolidating a Multisite Splunk Cluster into a Single Site
date: '2015-03-22T09:00:00-07:00'
tags:
- splunk
- indexer-clustering
- infrastructure
- consolidation
permalink: /2015/03/consolidating-multisite-splunk-cluster.html
---

By 2021, we reached a point where our original multisite Splunk indexer cluster architecture no longer matched our operational reality. What began as a strategy for high availability and geo-redundancy turned into an operational burden: excess replication, prolonged bucket fix-ups, and over-provisioned infrastructure.

This post walks through how we collapsed a multisite Splunk cluster into a single-site design—safely, deliberately, and with minimal disruption.

## Why Consolidate?

- Latency between sites introduced search inconsistencies and replication lag
- Site-based replication policies (site_replication_factor and site_search_factor) added unnecessary complexity for our SLA
- Regional staffing was no longer a constraint; our teams had centralized
- Lower total volume meant we could meet availability targets with a simpler design

## Before: Multisite Architecture

- 2 sites: `site1`, `site2`
- `site_replication_factor = origin:2, total:3`
- `site_search_factor = origin:1, total:2`
- Search head cluster with members in both sites
- Indexers unevenly loaded due to ingest locality

## Transition Plan

1. **Snapshot the Existing Cluster Configs**
   - `indexes.conf`, `server.conf`, `distsearch.conf`, `clustering`
   - Confirm cluster master health (`splunk show cluster-status`)

2. **Set Replication/Search Factor Globally**
   Update `server.conf` on all indexers:

```ini
[clustering]
mode = indexer
site = site1
multisite = false
replication_factor = 3
search_factor = 2
```

Update on cluster master:

```ini
[clustering]
multisite = false
available_sites = site1
site_replication_factor = <remove>
site_search_factor = <remove>
replication_factor = 3
search_factor = 2
```

3. **Reboot the Cluster Carefully**
   - Restart cluster master first
   - Then rolling restarts of indexers

4. **Monitor Bucket Fix-Ups**
   - Use `splunk show cluster-bundle-status` and `splunk show cluster-status`
   - Watch for buckets stuck in “fixup” state

5. **Update SH Cluster & Deployment Configs**
   - Remove site designations from `distsearch.conf` and any DS serverclasses
   - Validate search affinity and replication behavior with new topology

## Gotchas

- **Search head captain election** can behave unpredictably if old site references persist
- **Peers may register incorrectly** if `multisite` setting is partially removed
- Don’t forget to purge `site2` settings from `server.conf` *and* `indexes.conf`

## Results

- Simplified troubleshooting (single replication path)
- Reduced infrastructure (6 indexers instead of 10)
- Improved consistency in search results
- Less disk waste from extra replicated buckets

## When You Shouldn't Do This

- If you're running regionally-isolated ingestion and need data locality guarantees
- If you're using multisite for strict regulatory controls or DR zones
- If your ingest exceeds 15–20TB/day and cross-zone balancing is still necessary

## Final Thoughts

This was the right move for us at the time—but only after validating our ingest profile, cluster health, and search latency. If you're inheriting a multisite setup and it's constantly creating support friction, take a step back and reassess. Complexity should serve a purpose. If it doesn't, remove it.
