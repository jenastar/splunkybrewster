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

I've spent the last two years hitting the same wall on every bulk-classification problem: point a frontier chat model at a few thousand items, watch the cost and latency scale linearly with volume, then spend an afternoon writing a parser for output that occasionally comes back malformed. TypeSafe's Jev model is the first thing I've used that removes that wall entirely, and I wanted to see exactly how far it would hold up against a real dataset with no cleanup beforehand: 9,877 unread emails across two inboxes, spam and phishing and real correspondence all mixed together.

Jev is a System One model. Instead of generating text you then have to parse, it takes a `state` (the content to judge) and a map of typed `questions`, and returns one typed answer per question. No prose. No formatting to recover.

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

A `noul` question returns a probability between 0 and 1. That constraint is the entire value proposition. Every answer is a float, not a string you hope matches an enum. That's what let me build clean numeric thresholds afterward: `promotional >= 0.8`, `needs_action <= 0.2`, no regex, no retry-on-malformed-JSON logic, no edge cases where the model wraps its answer in a sentence.

## The cost math: what batching actually buys you

Before committing to an architecture, I ran a controlled comparison: the same three questions, against real emails, at two different batch sizes.

| Approach | Tokens/email (avg) |
|---|---|
| 1 email per call, 3 questions each | 422.4 |
| 10 emails per call, 30 questions total | 210.2 |

That's roughly half the cost per email, and the reason is a fixed cost getting amortized, not a mysterious batching bonus. Every API call pays a flat overhead: the system instructions defining what a `noul` type means, the response-format schema, the request wrapper. That cost is the same whether the call carries one email or ten. What multiplies is the number of calls, and each call re-pays that flat tax.

The two data points let me solve for the actual overhead and the actual marginal cost per email:

```
overhead/1 + per_email = 422.4
overhead/10 + per_email = 210.2
```

Subtracting the second equation from the first: `overhead - overhead/10 = 212.2`, so `overhead * 0.9 = 212.2`, giving overhead is about 235.8 tokens per call. Substituting back: per_email is about 186.6 tokens.

Checking the model against the measured 10-per-call number: `235.8/10 + 186.6 = 210.18`, against a measured 210.2. That's a match to within rounding.

The model predicts the curve keeps improving as batch size grows, asymptoting toward the 186.6-token floor as the fixed overhead gets divided across more and more emails. That's exactly why the production run used chunks of 25, not 10: the benchmark told me where the marginal return was still worth taking.

## Production run

- 9,877 emails classified
- 3,110,893 tokens total
- roughly $0.13 for the entire inbox pass at TypeSafe's published rate
- five `noul` questions per email: promotional, real_person, needs_action, is_event, would_attend
- chunk size 25, concurrency 8

None of those 3.1 million tokens touched my own context window. Every call was an isolated round-trip: classify, write to disk, discard. That's the structural advantage that the cost number alone does not capture. A chat-loop approach does not just cost more per item, it also has to hold the running output somewhere, which means either a context budget that caps how much you can process in one session or a summarization step that throws away detail.

## Mistakes worth writing up

**Question wording drives false positives:** the first version of `needs_action` asked whether the email required the recipient to do something. It scored 0.6 to 0.9 on obvious retail spam, because urgency language ("Hours left! 25% off ends tonight") reads as a call-to-action even when the actual content is junk. Rewriting the question to explicitly exclude marketing framing, asking whether it required a genuine personal or business action as opposed to a promotional one, fixed it immediately. A `noul` question is only as good as how precisely it excludes the interpretation you do not want.

**Topical match is not the same as a future event:** 30 emails scored above 0.65 on would this person want to attend. Checking the actual dates in the email bodies eliminated all but one. Most were expired last-chance-to-register marketing for events that had already happened weeks earlier. The model was correctly judging topical fit. It never had the event date in its state, so it had no way to judge timing. If the output needs to drive a calendar write, date verification has to be a separate pass against the full body, not folded into the topical score.

**Never chain a destructive step after an unverified one:** a bulk-unsubscribe script tried to copy flagged spam into a Bulk folder over IMAP before deleting the originals. The copy hit a rate limit and failed. The script deleted the originals anyway, because it never checked the copy's return status before proceeding. Nothing valuable was lost here, everything deleted was already confirmed junk, but the pattern is the lesson: check success before the next irreversible step, every time, regardless of how low-stakes the specific run looks.

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
