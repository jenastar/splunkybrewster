---
layout: post
title: 'Migrating Splunk to SmartStore with GCP: A Field Guide'
date: '2026-02-04T08:00:00-07:00'
tags:
- splunk
- smartstore
- performance
- gcp
permalink: /2026/02/migrating-splunk-to-smartstore-with-gcp.html
---


# Migrating Splunk to SmartStore with GCP: A Field Guide

After spending way too long troubleshooting a SmartStore migration that "should have been working," I figured I'd document what actually happened and the commands that saved us.

## The Setup

We needed to migrate a standalone Splunk indexer from local storage (10TB disk) to SmartStore backed by Google Cloud Storage. The goal was to reduce local disk to 2.5TB by offloading warm/cold buckets to GCS while keeping a 1.8TB local cache.

## GCP Configuration

### Create the Bucket

The bucket needs to be in the same region as your Compute Engine VM to avoid egress costs and latency:

```bash
gsutil mb -l US-CENTRAL1 gs://your-splunk-smartstore/
```

### IAM Permissions

SmartStore needs these permissions on the bucket:
- `storage.objects.create`
- `storage.objects.get`
- `storage.objects.delete`
- `storage.objects.list`
- `storage.buckets.get`

You can use a predefined role like `roles/storage.objectAdmin` or create a custom role with least privilege. We created `splunkStorageObjectUser` with just those permissions.

Grant it to your service account:

```bash
gsutil iam ch serviceAccount:YOUR-SA@developer.gserviceaccount.com:projects/YOUR-PROJECT/roles/splunkStorageObjectUser gs://your-splunk-smartstore
```

### VM OAuth Scopes (The Thing Everyone Forgets)

GCP has three layers of access control:
1. **Service Account** - the identity
2. **OAuth Scope** - the API gate (what APIs the VM can call)
3. **IAM Role** - actual permissions

Even with the right IAM role, if your VM has `devstorage.read_only` scope, writes will fail. Check your scopes:

```bash
gcloud compute instances describe YOUR-VM --zone=YOUR-ZONE --format="yaml(serviceAccounts)"
```

To change scopes, you must stop the VM:

```bash
gcloud compute instances stop YOUR-VM --zone=YOUR-ZONE
gcloud compute instances set-service-account YOUR-VM \
    --zone=YOUR-ZONE \
    --scopes=storage-full,logging-write,monitoring-write,service-management,service-control,trace
gcloud compute instances start YOUR-VM --zone=YOUR-ZONE
```

## Splunk Configuration

### indexes.conf - Add the Volume

In `$SPLUNK_HOME/etc/system/local/indexes.conf`, add:

```ini
[volume:remote_store]
storageType = remote
path = gs://your-splunk-smartstore
```

### indexes.conf - Add remotePath to Each Index

Every index you want migrated needs `remotePath`. Add this line to each index stanza:

```ini
remotePath = volume:remote_store/$_index_name
```

Important: Check ALL indexes.conf files. We had indexes defined in:
- `system/local/indexes.conf`
- `apps/search/local/indexes.conf`
- `apps/TA-crowdstrike-falcon-event-streams/local/indexes.conf`
- `apps/duo_splunkapp/local/indexes.conf`
- `apps/Splunk_TA_Google_Workspace/local/indexes.conf`

Use this to find them all:

```bash
find /opt/splunk/etc -name "indexes.conf" -exec grep -l "coldPath" {} \;
```

### server.conf - The Critical Part We Missed

This is what cost us 10 days. Without the `[cachemanager]` stanza, SmartStore uploads data but **never evicts it locally**.

In `$SPLUNK_HOME/etc/system/local/server.conf`:

```ini
[cachemanager]
max_cache_size = 1800000
hotlist_recency_secs = 86400
hotlist_bloom_filter_recency_hours = 360
```

- `max_cache_size` - Maximum local cache in MB (1800000 = 1.8TB)
- `hotlist_recency_secs` - Buckets accessed within this time won't be evicted (86400 = 24 hours)
- `hotlist_bloom_filter_recency_hours` - Buckets with data this recent won't be evicted (360 = 15 days)

**If you skip this, your data uploads to GCS but local disk never shrinks.**

## Verification Commands

### Test GCS Connectivity

```bash
/opt/splunk/bin/splunk cmd splunkd rfs -- ls volume:remote_store
```

No output + no error = working. Errors mean auth/permission issues.

### Check if Config is Applied

```bash
# Check volume
/opt/splunk/bin/splunk btool indexes list volume:remote_store --debug

# Check specific index has remotePath
/opt/splunk/bin/splunk btool indexes list YOUR_INDEX --debug | grep remotePath

# Check cachemanager settings
/opt/splunk/bin/splunk btool server list cachemanager --debug
```

If `btool server list cachemanager` returns nothing, your cache settings aren't applied.

## Verifying Local vs Remote Data

### What's Using Local Disk

```bash
# Top consumers
du -sh /opt/splunk/var/lib/splunk/*/ 2>/dev/null | sort -rh | head -20

# Specific index
du -sh /opt/splunk/var/lib/splunk/YOUR_INDEX/
```

### What's in the Remote Bucket

```bash
# Total size
gsutil du -sh gs://your-splunk-smartstore/

# Specific index
gsutil du -sh gs://your-splunk-smartstore/YOUR_INDEX/

# List bucket contents
gsutil ls gs://your-splunk-smartstore/YOUR_INDEX/db/ | head -10
```

### Verify a Specific Bucket Exists in Both Places

List local buckets and get the oldest one:

```bash
ls /opt/splunk/var/lib/splunk/YOUR_INDEX/db/ | grep "^db_" | sort -t'_' -k3 -n | head -5
```

Bucket names are formatted: `db_<latest_epoch>_<earliest_epoch>_<id>_<guid>`

Convert timestamp to human readable:

```bash
date -d @1755734703
```

Search for that bucket in GCS:

```bash
gsutil ls -r gs://your-splunk-smartstore/YOUR_INDEX/db/** 2>/dev/null | grep "BUCKET_ID~"
```

### Check Bucket Upload Status

Inside each bucket directory, `cachemanager_local.json` shows what's cached:

```bash
cat /opt/splunk/var/lib/splunk/YOUR_INDEX/db/BUCKET_DIR/cachemanager_local.json
```

If `journal_gz` is NOT in the file_types list, rawdata was evicted. If it's there, rawdata is still local.

### Count Buckets Still Holding Rawdata

```bash
find /opt/splunk/var/lib/splunk/YOUR_INDEX/db/*/rawdata -type d 2>/dev/null | wc -l
```

### Size of Rawdata Still Local

```bash
du -shc /opt/splunk/var/lib/splunk/YOUR_INDEX/db/*/rawdata 2>/dev/null
```

## Troubleshooting Eviction

### Check if Eviction is Running

```bash
grep -i "evict" /opt/splunk/var/log/splunk/splunkd.log | tail -20
```

Good output shows `bytes_evicted` > 0:
```
Eviction results: count=310, test_count=321, bytes_evicted=2680505613
```

Bad output shows eviction failing:
```
Unable to evict enough data. Evicted size=0 instead of size=1473368064
```

### Why Eviction Fails

1. **No cachemanager config** - Most common. Check btool.

2. **Buckets not uploaded yet** - Can't evict what's not in remote storage. Check if buckets exist in GCS.

3. **Hotlist protection** - Recent data is protected. Buckets with data newer than `hotlist_bloom_filter_recency_hours` won't evict.

4. **Active searches** - Searches keep buckets in cache. If you have searches running every 11 minutes hitting 60 days of data, those buckets stay cached.

### Check Tracking File

Each index has a tracking file for synced buckets:

```bash
cat /opt/splunk/var/lib/splunk/YOUR_INDEX/db/.buckets_synced_to_remote_storage | wc -l
```

If this is empty but data is in GCS, there's a metadata sync issue. Restart Splunk:

```bash
/opt/splunk/bin/splunk restart
```

### Fix File Ownership

If Splunk runs as `splunk` user but files are owned by root:

```bash
chown -R splunk:splunk /opt/splunk/var/lib/splunk/
```

## Understanding What Gets Evicted

SmartStore eviction removes data in stages:

1. **Rawdata (journal.gz)** - Evicted first, bulk of the data
2. **tsidx, bloomfilter** - Kept longer for search performance
3. **Metadata files** - Kept locally

After eviction, a bucket directory still exists but contains only search metadata (~500MB tsidx + ~18MB bloomfilter per bucket). This adds up across hundreds of buckets.

## Reducing Internal Index Retention

The `_internal` index can get huge. To reduce retention:

```ini
[_internal]
frozenTimePeriodInSecs = 604800
```

Common values:
- 7 days = 604800
- 14 days = 1209600
- 30 days = 2592000
- 90 days = 7776000

## Monitoring Progress

Watch disk usage over time:

```bash
watch -n 60 'df -h / | grep -v Filesystem'
```

Check eviction activity:

```bash
tail -f /opt/splunk/var/log/splunk/splunkd.log | grep -i evict
```

## Lessons Learned

1. **Always add the cachemanager stanza** - Without it, nothing evicts
2. **Check ALL indexes.conf files** - Apps create their own
3. **VM scopes matter** - IAM roles aren't enough on GCP
4. **Eviction takes time** - Don't panic if disk doesn't shrink immediately
5. **Searches keep data cached** - Frequent searches on old data prevent eviction
6. **The UI shows logical size** - Use `du` for actual local disk usage

