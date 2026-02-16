---
layout: post
title: Standard Deviation of Volume Ingestion for Alerting
date: '2025-07-23T09:00:00-07:00'
tags:
- splunk
- inputs
- search
permalink: /2025/07/standard-deviation-of-volume-ingestion_23.html
---

# Splunk License Usage Anomaly Report (Z-Score Method) — **Full Detailed Breakdown**

## Purpose
You asked for the *very detailed* explanation of what the SPL does, plus tuning guidance to cut false positives. This Markdown file is ready to upload to Blogger (all code blocks fenced).

---

## The SPL Search (as given)

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

## Ultra-Detailed, Pipe-by-Pipe Breakdown

Below, every stage shows: **what it does**, **why it's done**, and **what fields/rows look like afterwards**.

### 1. Initial event search  
```splunk
index=_internal host=*.splunkcloud.com source=*license_usage.log* type="Usage" earliest=-15m@m
```
**What it does:**  
- Pulls events from Splunk’s internal index (`_internal`) where the source is the license usage log (`*license_usage.log*`) and the event `type` is `"Usage"`.  
- Limits time to the last 15 minutes (`earliest=-15m@m`) rounded to the minute boundary.  
- `host=*.splunkcloud.com` narrows results to Splunk Cloud license hosts.  

**Why:** These events include per-index byte counts (`b`) that Splunk uses to track license usage. You want to know how many bytes each index ingested in the last 15 minutes.

**Key fields coming out of this stage (per event):** `_time`, `host`, `source`, `type`, `idx` (index name), `b` (bytes indexed), plus internal metadata.

---

### 2. Bucket times into 15‑minute bins  
```splunk
| bin _time span=15m
```
**What it does:** Rounds `_time` down to the nearest 15-minute boundary so multiple events in the same period share the same timestamp.  

**Why:** Prepares data for grouping by a consistent time bucket; ensures one row per index per 15-minute window after aggregation.  

**Output change:** `_time` values become aligned (e.g. `2025-07-23 14:00:00`).

---

### 3. Aggregate bytes by index and time  
```splunk
| stats sum(b) AS byte_sum by idx, _time
```
**What it does:** For each (`idx`, `_time`) pair, sums all `b` values to produce `byte_sum`.  

**Why:** You need one consolidated metric: total bytes an index ingested during that 15-minute window.  

**Output fields now:** `_time`, `idx`, `byte_sum` (one row per index per bin). All other original fields are dropped unless included in `by` or aggregated.

---

### 4. Join with historical baseline lookup  
```splunk
| join type=inner idx [| inputlookup avg_index_bytes_15m.csv]
```
**What it does:**  
- Loads a CSV lookup (`avg_index_bytes_15m.csv`) that (presumably) contains historical stats **per index**: e.g. `idx`, `average`, `std`.  
- Performs an **inner join** on `idx`. Only indexes present in both the live data and the lookup survive.

**Why:** To compare the current 15‑minute volume against a precomputed baseline mean (`average`) and standard deviation (`std`) for that same index.

**After join you typically have:** `_time`, `idx`, `byte_sum`, `average`, `std` (and any extra fields in the lookup).

> **Tip:** You could swap `join` for `lookup` for efficiency:  
> ```splunk
> | lookup avg_index_bytes_15m.csv idx OUTPUT average std
> ```
> Functionally the same if `idx` is unique in the lookup.

---

### 5. Compute the z-score  
```splunk
| eval z_score=(byte_sum - average)/std
```
**What it does:** Calculates how far (in standard deviations) today’s 15‑minute byte total deviates from the historical mean.  

**Why:** A z-score is a quick anomaly metric. Negative means below average; a large negative (e.g. < -3) is *statistically rare* under normal distribution assumptions.

**Math refresher:**  
- `z = (current - mean) / std_dev`  
- Example: `(0.768 GB - 5.905 GB) / 1.315 GB ≈ -3.91`

**Output fields now include:** `z_score`.

---

### 6. Convert bytes to GB for readability  
```splunk
| eval currentGB=round((byte_sum/1024/1024/1024), 3)
| eval averageGB=round((average/1024/1024/1024), 3)
| eval stdGB=round((std/1024/1024/1024), 3)
```
**What it does:** Creates human-friendly gigabyte versions of the raw byte metrics, rounded to three decimals.

**Why:** Easier for humans to interpret and include in alerts/reports.

**Output now has:** `currentGB`, `averageGB`, `stdGB` in addition to the raw byte fields.

---

### 7. Keep only the fields you care about  
```splunk
| table _time, idx, currentGB, averageGB, z_score, stdGB
```
**What it does:** Drops everything but the main fields you plan to show or alert on.

**Why:** Clean, tidy output (also reduces later processing overhead).

---

### 8. Filter to “significant” negative anomalies  
```splunk
| where z_score < -3
```
**What it does:** Keeps rows where the current volume is more than 3 standard deviations **below** the mean. (Nothing above average or slight dips.)

**Why:** A common statistical threshold: ~0.13% of a normal distribution lies below -3σ, so it signals “rare” events.

**Effect:** All normal or mild drops are removed; only “big” drops remain.

---

### 9. Sort by z-score (descending)  
```splunk
| sort 0 - z_score
```
**What it does:** Sorts results by `z_score` descending. Since all are negative, the least negative (closest to zero) appears first.

**Why:** Presentation choice. If you want most extreme at top, use `sort 0 z_score` instead (ascending).

---

### 10. Rename columns for final presentation  
```splunk
| rename idx AS Index, currentGB AS "GB Indexed over Past 15 Minutes", averageGB AS "Average GB Indexed per 15 Minutes", stdGB AS "Standard Deviation", z_score AS "Z-Score"
```
**What it does:** Makes headers human-readable (nice for dashboards/emails).

**Why:** Stakeholders don’t need to see cryptic field names.

---

### 11. Final filter on Std Dev (variance floor)  
```splunk
| search "Standard Deviation">1
```
**What it does:** After the `rename`, “Standard Deviation” refers to `stdGB`. This line keeps only rows where `stdGB` > 1 GB.

**Why:** Prevents noisy alerts from low-volume, low-variance indexes where even tiny dips produce a big z-score. You only care about big, variance-rich indexes.

---

## Example That Keeps Triggering (False Positive Case)

```
_time: 2025-07-23 14:00:00
Index: network-firewall-palo_alto
GB Indexed over Past 15 Minutes: 0.768
Average GB Indexed per 15 Minutes: 5.905
Z-Score: -3.906902640760295
Standard Deviation: 1.315
```

- It passed **all filters**: z < -3 and stdGB (~1.315) > 1.  
- But this drop could be perfectly normal (maintenance window, lull, delayed forwarder, weekend, etc.).

---

## Why You’re Seeing False Positives

1. **Seasonality ignored:** One global average for an index hides periodic patterns (night vs day, weekday vs weekend). Off-hours will *always* look “low” compared to the all-hours average.
2. **Baseline drift / stale lookup:** If ingestion patterns changed (new sources, retirements), the saved `average`/`std` might no longer represent current reality.
3. **Single-bucket sensitivity:** One late/dropped batch in a 15‑min window triggers an alert, even if the next bucket catches up.
4. **Statistical vs practical significance:** A -3.1 z-score could reflect a small absolute change that isn’t operationally important.

---

## Tuning Ideas to Cut Noise

### A. Add Time Context to the Baseline
- Recompute averages and stddev **per time slice**, e.g. by:  
  - `weekday/weekend` (boolean)  
  - `biz_hours` vs `off_hours`  
  - Even `hour_of_day` (0–23) or (0–95 for 15‑min buckets)  
- Store these keys in your lookup (`avg_index_bytes_15m.csv`) and add them to both your live search and lookup join.  
- Compare Wednesday 14:00 against historical Wednesday 14:00, not against 24/7 global average.

### B. Tighten the Threshold(s)
- Change `where z_score < -3` to `< -3.5`, `< -4`, etc.  
- Add an **absolute delta**: e.g. `currentGB < averageGB * 0.5` or `averageGB - currentGB > 2` GB.

### C. Minimum Baseline Requirements
- Already filtering on `stdGB > 1`. Consider also `averageGB > 1` (or a larger value) to ensure you only alert on high-volume indexes.
- If you see noise around std between 1–2 GB, bump that to >2 GB.

### D. Persistence Check (multi-bucket confirmation)
- Search a longer window (e.g. 45–60 min), compute z-scores per 15‑min bin, and alert only if **2+ consecutive bins** are anomalous.  
  *Example pattern:*
  ```splunk
  earliest=-60m@m latest=now
  | bin _time span=15m
  | stats sum(b) AS byte_sum by idx _time
  | lookup avg_index_bytes_15m.csv idx OUTPUT average std weekday weekend biz_hours
  | eval z=(byte_sum-average)/std
  | eval currentGB=round(byte_sum/1024/1024/1024,3), averageGB=round(average/1024/1024/1024,3), stdGB=round(std/1024/1024/1024,3)
  | where z < -3 AND stdGB>1 AND averageGB>1
  | streamstats count(eval(z < -3)) AS consecutive_low BY idx
  | where consecutive_low>=2
  ```
  (There are many ways to implement this; `streamstats`, `eventstats`, or even `transaction` can be used.)

### E. Keep the Baseline Fresh
- Schedule a daily job to rebuild `avg_index_bytes_15m.csv` from the last N days (30 is common).  
- Optionally, use **median & MAD** instead of mean & std for robustness to outliers.

### F. Performance/Clarity Tweaks
- Prefer `lookup` over `join` where possible.  
- Consider adding comments in your SPL (with `#` on a new line) to remind future-you what each stage does.

---

## “Hardened” Sample Query (Illustrative)

```splunk
index=_internal source=*license_usage.log* type="Usage" earliest=-60m@m
| bin _time span=15m
| stats sum(b) AS byte_sum by idx _time
| lookup avg_index_bytes_15m.csv idx OUTPUT average std weekday weekend biz_hours
| eval z_score=(byte_sum-average)/std
| eval currentGB=round(byte_sum/1024/1024/1024,3),
      averageGB=round(average/1024/1024/1024,3),
      stdGB=round(std/1024/1024/1024,3)
| where z_score < -3
      AND currentGB < averageGB*0.6
      AND stdGB > 1
      AND averageGB > 1
| streamstats count(eval(z_score < -3)) AS low_run BY idx
| where low_run >= 2
| table _time idx currentGB averageGB stdGB z_score
| rename idx AS Index currentGB AS "GB Indexed (15m)" averageGB AS "Avg GB (15m)" stdGB AS "Std Dev (GB)" z_score AS "Z-Score"
| sort 0 "Z-Score"
```

> **Note:** Adjust thresholds (`0.6`, `>1`, `>=2`, etc.) to match your tolerance for noise and business risk.

---

## Key Takeaways

- **Know the math:** z-score = (current − average) ÷ std. Big negative = big drop.  
- **Context beats raw stats:** Segment your baseline (time-of-day, weekday/weekend) to avoid “expected lows” being flagged.  
- **Multiple gates reduce noise:** z-score + absolute delta + std/avg floors + persistence check.  
- **Refresh baselines regularly:** Keep that CSV accurate and reflective of *current* behavior.  
- **Iterate:** Tune, observe alert volume, tweak thresholds again.

---

*Happy tuning and fewer false positives!*  
