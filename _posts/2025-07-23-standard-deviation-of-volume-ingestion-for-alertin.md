---
layout: post
title: Standard Deviation of Volume Ingestion for Alerting
date: '2025-07-23T09:00:00-07:00'
tags:
- splunk
- inputs
- search
permalink: /2025/07/standard-deviation-of-volume-ingestion.html
---

# Splunk License Usage Anomaly Report (Z-Score Method)

## Purpose
This report explains what your SPL search does, why it can generate false positives, and how to tune it so you only alert on *meaningful* ingestion drops.

---

## The SPL Search

```splunk
index=_internal host=*.splunkcloud.com source=*license_usage.log* type="Usage" earliest=-15m@m
| bin _time span=15m 
| stats sum(b) AS byte_sum by idx, _time
| join type=inner idx [| inputlookup avg_index_bytes_15m.csv]
| eval z_score=(byte_sum - average)/std
| eval currentGB=round((byte_sum/1024/1024/1024), 3)
| eval averageGB=round((average/1024/1024/1024), 3)
| eval stdGB=round((std/1024/1024/1024), 3)
| table _time, idx, currentGB, averageGB, z_score, stdGB
| where z_score < -3
| sort 0 - z_score
| rename idx AS Index, currentGB AS "GB Indexed over Past 15 Minutes", averageGB AS "Average GB Indexed per 15 Minutes", stdGB AS "Standard Deviation", z_score AS "Z-Score"
| search "Standard Deviation">1
```

---

## Step-by-Step Breakdown

1. **Pull last 15 minutes of license usage events**
   - `index=_internal ... type="Usage" earliest=-15m@m`
   - Grabs bytes indexed per event from Splunk's internal license logs for the most recent 15-minute window.

2. **Bucket events into a 15-minute slot**
   - `| bin _time span=15m`
   - Rounds `_time` so all events in that interval share the same timestamp.

3. **Sum bytes by index**
   - `| stats sum(b) AS byte_sum by idx, _time`
   - Produces the total bytes (`byte_sum`) each index ingested in that 15-minute period.

4. **Join with a baseline lookup**
   - `| join type=inner idx [| inputlookup avg_index_bytes_15m.csv]`
   - Adds `average` and `std` (standard deviation) for each index from a CSV of historical stats.

5. **Compute the z-score**
   - `| eval z_score=(byte_sum - average)/std`
   - Measures how many standard deviations the current value is below/above normal.

6. **Convert to GB for readability**
   - `currentGB`, `averageGB`, `stdGB` are rounded GB values of the current, average, and std.

7. **Restrict output to useful fields**
   - `| table ...`

8. **Alert only on large negative deviations**
   - `| where z_score < -3`
   - Flags “significant” drops (more than 3σ below the mean).

9. **Clean up and sort**
   - `| sort 0 - z_score` and `| rename ...`

10. **Filter out tiny/low-variance indexes**
    - `| search "Standard Deviation">1`
    - Ignore indexes with < 1 GB standard deviation to avoid noisy low-volume sources.

---

## Example False Positive

```
_time: 2025-07-23 14:00:00
Index: network-firewall-palo_alto
GB Indexed over Past 15 Minutes: 0.768
Average GB Indexed per 15 Minutes: 5.905
Z-Score: -3.9069
Standard Deviation: 1.315
```

Why it triggered:
- Current volume (~0.77 GB) is ~3.9 standard deviations below the typical 5.9 GB.
- Statistically “rare,” but it may be normal (e.g., scheduled maintenance, night/weekend lull, source hiccup that auto-recovers).

---

## Why False Positives Happen

- **Daily/weekly cycles ignored**: One global average doesn’t reflect predictable low periods (nights, weekends).
- **Baseline drift**: The lookup may be outdated or not segmented—behavior changed but baseline didn’t.
- **Short-lived blips**: One 15‑minute delay looks bad but recovers immediately after.
- **Low absolute impact**: Even with std > 1 GB, the actual drop might be trivial from a business standpoint.

---

## Tuning Strategies

### 1. Add Seasonality / Context
- Build separate baselines (and lookup columns) for:
  - Weekday vs weekend
  - Business hours vs off-hours (or even per-hour buckets)
- Join on these extra keys so you compare like-with-like (Wednesday 14:00 vs historical Wednesday 14:00).

### 2. Adjust Statistical Thresholds
- Raise the cut-off: `where z_score < -4` (or even `< -4.5`) to catch only extreme drops.
- Combine with **absolute drop** checks:
  ```splunk
  | where z_score < -3 AND currentGB < averageGB * 0.5
  ```
  or require a minimum delta in GB.

### 3. Enforce Minimum Averages / Std Dev
- Already using `"Standard Deviation">1`. Consider:
  - `averageGB > 1` (ignore tiny indexes)
  - `stdGB > 2` if smaller stds are still noisy

### 4. Require Persistence
- Look over a longer window and alert only if **2+ consecutive buckets** are anomalous:
  ```splunk
  earliest=-45m@m latest=now
  | bin _time span=15m
  | ... (same math) ...
  | eventstats count(eval(z_score < -3)) AS low_count BY idx
  | where low_count >= 2
  ```
  (One way—there are many streamstats/eventstats variants to implement persistence.)

### 5. Refresh the Baseline Regularly
- Recompute `avg_index_bytes_15m.csv` (e.g., nightly) over a rolling window (last 30 days).
- Consider storing per-time-slice stats (hour of day + weekday) in that file.

### 6. Simplify the Join
- Use `lookup` instead of `join` for performance:
  ```splunk
  | lookup avg_index_bytes_15m.csv idx OUTPUT average, std
  ```

---

## Quick “Hardened” Version (Illustrative)

```splunk
index=_internal source=*license_usage.log* type="Usage" earliest=-45m@m
| bin _time span=15m
| stats sum(b) AS byte_sum by idx _time
| lookup avg_index_bytes_15m.csv idx OUTPUT average std weekday weekend biz_hours
| eval z_score=(byte_sum-average)/std
| eval currentGB=round(byte_sum/1024/1024/1024,3), averageGB=round(average/1024/1024/1024,3), stdGB=round(std/1024/1024/1024,3)
| where z_score < -3 AND currentGB < averageGB*0.6 AND stdGB>1 AND averageGB>1
| eventstats count(eval(z_score < -3)) AS low_count BY idx
| where low_count>=2
| table _time idx currentGB averageGB stdGB z_score
| rename idx AS Index currentGB AS "GB Indexed (15m)" averageGB AS "Avg GB (15m)" stdGB AS "Std Dev (GB)" z_score AS "Z-Score"
| sort 0 - "Z-Score"
```

*(Adjust fields/keys to match your enhanced lookup.)*

---

## Takeaways

- **Understand the math**: z-score = (current - average) / std. Big negative ⇒ big drop.
- **Context is king**: segment baselines by time patterns to avoid “expected lows” raising alarms.
- **Multiple gates** (z-score, absolute delta, std/avg floors, persistence) = fewer false positives.
- **Keep baselines fresh**: recalc regularly so stats reflect current reality.

Make these tweaks incrementally and watch alert volume/quality. Fine-tune until only *actionable* anomalies get through.

---

*Happy tuning!*  
