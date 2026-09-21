---
layout: post
title: Triaging 9,877 Unread Emails with a Typed-Judgment Model
date: '2026-09-21T14:30:00-07:00'
tags:
- ai
- automation
- security
permalink: /2026/09/triaging-inbox-with-typesafe-jev.html
---

Two inboxes had grown to 9,877 unread emails between them. Manual triage does not scale at that volume, and neither does the naive approach of looping an LLM over each email one at a time in free-text chat completions. That burns tokens fast and does not parallelize cleanly.

Instead I used TypeSafe's Jev model, a System One model that returns typed, calibrated judgments instead of generated prose, as the classification backend behind an orchestration script.

## What Jev actually returns

A Jev call takes a state (the content to judge) and a map of typed questions, and returns one typed answer per question. Never free text:

```json
POST https://api.typesafe.ai/v1/systemone
{
  "state": {"from": "...", "subject": "..."},
  "model": "jev-latest",
  "questions": {
    "promotional": {"type": "noul", "instructions": "Is this a marketing email?"}
  }
}
```

A noul question returns a probability 0-1. No parsing free text out of a completion. Every answer is constrained to the shape you asked for, which made it possible to build clean numeric thresholds in code afterward (promotional >= 0.8, needs_action <= 0.2) instead of regexing prose.

## Cost architecture: chunk the emails, not just the questions

What I measured, empirically, before committing to an approach:

| Approach | Tokens/email (avg) |
|---|---|
| 1 email per call, 3 questions each | 422.4 |
| 10 emails per call, 30 questions total | 210.2 |

Chunking multiple emails into a single call, not just multiple questions about one email, was roughly 2x cheaper per email, because per-call fixed overhead gets amortized across more items. Production run used chunks of 25, concurrency 8.

## Real numbers

- 9,877 emails classified
- 3,110,893 tokens total
- roughly $0.13 for the entire inbox pass at TypeSafe's published rate
- Five noul questions per email: promotional, real_person, needs_action, is_event, would_attend

None of those 3.1M tokens touched the orchestrating agent's own context window. Every call was an isolated API round-trip. That is the real structural win over doing it by hand in a chat loop: the volume never has to live in context.

## Mistakes worth writing up

**Question wording drives false positives:** first pass at needs_action scored high on obvious retail spam because urgency language reads as a call-to-action even when the content is junk. Rewriting the question to explicitly exclude marketing framing fixed it immediately.

**Topical match is not the same as a future event:** 30 emails scored high on would want to attend. Checking actual dates in the bodies killed all but one. Most were expired event marketing. The model correctly judged topical fit; it never had the actual date in its state to judge timing.

**Never chain a destructive step after an unverified one:** a bulk-unsubscribe script tried to copy flagged spam to a Bulk folder via IMAP, hit a rate limit, and proceeded to delete the originals anyway without checking the copy succeeded. Check success before the next irreversible step, always.

## Pipeline shape

```
IMAP fetch headers (chunked, 200/req)
  -> build state arrays (25 emails/chunk)
  -> Jev classify (concurrent, 8 workers, 5 noul questions/email)
  -> results.jsonl
  -> threshold-based bucketing in plain code
  -> bulk unsubscribe (List-Unsubscribe header, HTTP GET)
  -> event date verification (separate pass, full body fetch)
  -> calendar write for confirmed future events only
```
