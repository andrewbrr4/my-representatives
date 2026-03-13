# User Feedback

## Goal
Understand whether MyReps is surfacing the right information about representatives —
the right topics, the right depth, the right framing. UI/UX feedback is also welcome
but secondary. This data informs prompt and product iteration, and eventually feeds
a public transparency dashboard.

## What we capture
- **Content feedback** — is the AI research summary useful? Does it cover what the
  user actually wanted to know? Is anything missing or surprising?
- **General app feedback** — layout, usability, what they wished the app did

No thumbs up/down or ratings. Free text only — we want signal, not sentiment scores.

## Where feedback lives
A dedicated `/feedback` page, linked from the results page and the nav. Not embedded
in the lookup flow — users who want to leave feedback seek it out. This keeps the
main flow clean and avoids pestering users who just want their results.

## Why not a SaaS feedback tool
Tools like Canny and Featurebase are built around feature request voting boards —
structured posts that users upvote. That's a poor fit here for two reasons:

1. **Wrong shape.** Our primary feedback is qualitative content critique ("the summary
   for my senator got the policy positions wrong"), not feature requests ("I wish the
   app did X"). These tools handle that awkwardly.
2. **LLM processing.** The long-term vision involves running AI analysis over the raw
   feedback corpus. A self-hosted table gives full programmatic access; a SaaS tool
   would require pulling data out via API into a model that doesn't match our schema.

Building it ourselves costs one table and one form. Public upvoting, if we want it
later, is a small addition to our own UI.

## Schema
```
feedback
  - id
  - created_at
  - feedback_text        (free text, required)
  - feedback_type        (content | general)
  - rep_id               (optional — if feedback is about a specific representative)
  - request_id           (optional — links back to the lookup that prompted the feedback)
  - address_input        (optional — what address was searched, for context)
```

`rep_id` and `request_id` are optional but valuable — if a user navigates to `/feedback`
from a results page, pre-populate them silently so the feedback is anchored to the
lookup that prompted it.

## Phases

### Phase 1 — Simple form, database storage
A minimal feedback form on `/feedback`. No auth required. Free text field plus a
toggle for content vs. general feedback. Submissions write directly to a `feedback`
table in the app database.

Review feedback manually via a simple admin query. No dashboard yet.

**Form fields:**
- Feedback type: "About the representative summaries" / "About the app generally"
- Text area: open prompt, e.g. "What would you like us to know?"
- Optional: which representative this is about (pre-populated if coming from results page)
- Submit — no account required

### Phase 2 — Admin review interface
A simple internal `/admin/feedback` page listing submissions, filterable by type and
date. Lets you review feedback without querying the database directly. Not public-facing.

### Phase 3 — Public upvoting
A lightweight upvoting mechanic on the public `/feedback` page — users can see
recent submissions and +1 ones they agree with. Simple `feedback_votes` join table.
No SaaS dependency needed; this is a small UI addition to what we already own.

### Phase 4 — LLM processing
Automated AI analysis over the feedback corpus. This is where things get interesting.

**Basic version:** nightly job that clusters feedback themes and surfaces what people
keep saying — a digest you can read instead of scrolling raw submissions.

**More sophisticated:** because feedback is anchored to `request_id` and `rep_id`,
you can ask targeted questions of the corpus:
- "What topics do users wish were covered that we don't surface?"
- "What do people find missing from senator summaries vs. house member summaries?"
- "Are there patterns in content feedback that correlate with specific representatives
  or geographic regions?"

This is qualitative product research at a scale that would normally require a UX
research team — powered by the same AI pipeline already running the app.

**Public transparency angle:** anonymized theme summaries from LLM analysis could
surface on the public transparency dashboard alongside cost data — showing not just
what MyReps costs to run but what users think of it and what it's improving toward.