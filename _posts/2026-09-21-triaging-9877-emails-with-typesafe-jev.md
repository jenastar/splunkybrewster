---
layout: post
title: Triaging 9,877 Unread Emails with TypeSafe's Jev Model
date: '2026-09-21T14:30:00-07:00'
tags:
- ai
- automation
- security
permalink: /2026/09/triaging-inbox-with-typesafe-jev.html
---

Every bulk-classification job I have thrown at a chat model has the same shape: cost and latency scale linearly with volume, and you end up writing a parser for output that occasionally comes back malformed. TypeSafe's Jev model breaks that shape. I ran it against 9,877 unread emails across two inboxes, no cleanup beforehand, spam and phishing and real correspondence all mixed together, to see how far it would actually hold up.

Jev is a System One model. Instead of generating text you then have to parse, it takes a `state` (the content to judge) and a map of typed `questions`, and returns one typed answer per question. Three question types: `noul` (a probability between 0 and 1), `choice` (a selection among options your own code enumerates), and `score` (a position on a defined scale). No free text, ever. If you need an open-ended value back, like a specific date, Jev is the wrong tool: it judges, your code extracts.

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

Every answer is a float, a selected option, or a scale position, never a string you hope matches an enum. That's what let me build clean numeric thresholds afterward: `promotional >= 0.8`, `needs_action <= 0.2`, no regex, no retry-on-malformed-JSON logic.

Each email was judged on its `from` and `subject` fields only, never the body. That scope choice is deliberate, not incidental, and the cost math below explains why.

## The cost math: what batching actually buys you, and where the model breaks

Before committing to an architecture, I ran a controlled comparison: the same three questions, against real emails, at two batch sizes.

| Approach | Questions/email | Tokens/email (avg) |
|---|---|---|
| 1 email per call | 3 | 422.4 |
| 10 emails per call | 3 | 210.2 |

Roughly half the cost per email, and the reason is a fixed cost getting amortized, not a mysterious batching bonus. Every API call pays a flat overhead: the system instructions defining what a `noul` type means, the response-format schema, the request wrapper. That cost is the same whether the call carries one email or ten. What multiplies is the number of calls, and each call re-pays that flat tax.

Two data points, two unknowns. Solving for the actual overhead and the actual marginal cost per email at 3 questions:

```
overhead/1 + per_email = 422.4
overhead/10 + per_email = 210.2
```

Subtracting: `overhead * 0.9 = 212.2`, so overhead is about 235.8 tokens per call, and per_email is about 186.6 tokens. Check: `235.8/10 + 186.6 = 210.18` against a measured 210.2. Close enough to trust the model, at 3 questions.

Production ran 25 emails per call at 5 questions per email (promotional, real_person, needs_action, is_event, would_attend), not 3. Plugging chunk size 25 into the 3-question model predicts 235.8/25 + 186.6, about 196.0 tokens/email. The actual production average, computed from the real run, is 3,110,893 tokens over 9,877 emails: 315.0 tokens/email. That is 60% higher than the model predicts, and the honest reason is that the two-point model was fit at a fixed question count and never isolated a per-question overhead term. Five questions cost more than three in ways the chunk-size-only model does not capture. The fixed-overhead-per-call finding is real and reproducible; treating it as the whole story would not be.

## Production run

- 9,877 emails classified
- 3,110,893 tokens total, 315.0 tokens/email measured
- roughly $0.13 for the entire inbox pass at TypeSafe's published rate
- five `noul` questions per email: promotional, real_person, needs_action, is_event, would_attend
- chunk size 25, concurrency 8

None of those 3.1 million tokens touched my own context window. Every call was an isolated round-trip: classify, write to disk, discard. A chat-loop approach does not just cost more per item, it also has to hold the running output somewhere, which means either a context budget that caps how much you can process in one session or a summarization step that throws away detail.

## Mistakes worth writing up

**Question wording drives false positives:** the first version of `needs_action` asked whether the email required the recipient to do something. It scored 0.6 to 0.9 on obvious retail spam, because urgency language ("Hours left! 25% off ends tonight") reads as a call-to-action even when the actual content is junk. Rewriting the question to explicitly exclude marketing framing, asking whether it required a genuine personal or business action as opposed to a promotional one, fixed it immediately.

**Topical match is not the same as a future event:** 30 emails scored above 0.65 on would this person want to attend. Checking the actual dates in the email bodies eliminated all but one. Most were expired last-chance-to-register marketing for events that had already happened weeks earlier. The model was correctly judging topical fit against subject and sender alone. It never saw the body, so it never saw the date, so it had no way to judge timing. If the output needs to drive a calendar write, date verification has to be a separate pass against the full body of only the flagged subset, not folded into the topical score.

**Never chain a destructive step after an unverified one:** a bulk-unsubscribe script tried to copy flagged spam into a Bulk folder over IMAP before deleting the originals. The copy hit a rate limit and failed. The script deleted the originals anyway, because it never checked the copy's return status before proceeding. Nothing valuable was lost here, everything deleted was already confirmed junk, but the pattern is the lesson: check success before the next irreversible step, every time.

## Pipeline shape

```
IMAP fetch headers (chunked, 200/req)
  -> build state arrays (25 emails/chunk, from+subject only)
  -> Jev classify (concurrent, 8 workers, 5 noul questions/email)
  -> results.jsonl
  -> threshold-based bucketing in plain code
  -> bulk unsubscribe (List-Unsubscribe header, HTTP GET)
  -> event date verification (separate pass, full body fetch, flagged subset only)
  -> calendar write for confirmed future events only
```
