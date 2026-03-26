# MyReps — Product Spec

This document defines what MyReps is, why it exists, and the principles that guide every design and engineering decision. Read this before making changes.

## The Problem

Most Americans only think about their elected officials once every two or four years — and even then, attention narrows to a handful of headline races. The vast majority of elected officials at the state and municipal level operate in near-total obscurity, making decisions that directly shape people's daily lives with almost no public scrutiny.

This isn't because people don't care. It's because the information is scattered, hard to find, and rarely presented in a way that's useful. Who represents you on your city council? What has your state senator been working on? What committees does your House representative sit on, and what have they actually done lately? For most people, answering these questions requires more effort than feels reasonable.

The result is a feedback loop: representatives face little accountability between elections, voters feel uninformed and disengaged, and the gap between citizens and their government widens.

## What MyReps Does

MyReps makes it trivially easy to find out who represents you — at every level of government — and what they've been up to. Enter your address and you instantly see:

- Every elected official who represents you, from the President down to your city council member
- Direct contact information — phone numbers, emails, and websites — so you can actually reach them
- On-demand, AI-researched summaries for any rep you want to learn more about: their background, recent news, policy positions, and committee work
- Upcoming elections relevant to your address — with ballot contests, candidates, voter info, and AI-researched context on what's at stake

## Why This Matters

Democracy works better when people pay attention — not just at the ballot box, but between elections. A phone call to a representative's office carries real weight. An informed voter asking pointed questions at a town hall changes the dynamic. But none of that happens if people don't know who their representatives are or what they're doing.

MyReps exists to lower the barrier from "I should probably look into this" to "now I know, and here's how to reach them." And when elections come around, it ensures voters know what's on their ballot and what's at stake — not just the headline races, but every contest they'll be voting on.

## Design Principles

These guide every product decision:

1. **Comprehensive by default.** Show every elected official, at every level. The city council member matters as much as the senator. Don't make users dig for the officials who affect their lives most directly.

2. **Current and honest.** AI-researched summaries should reflect what representatives are actually doing right now — not campaign talking points. Present facts, not spin. Cut through the PR language and give people genuinely useful information: a reader should be able to look at a summary and clearly see what they might agree or disagree with about their rep's positions. Doing this in a nonpartisan way — presenting substance without editorializing — is perhaps the hardest design challenge in the product.

3. **Action-oriented.** Information without a path to action is just trivia. Every representative card should make it dead simple to pick up the phone, send an email, or visit their office's website.

4. **Respect the user's time.** People are busy. Get them what they need fast, explain what's happening while they wait, and don't waste their attention on anything that isn't useful.

## Design Approach

See [DESIGN.md](./DESIGN.md) for design decisions, challenges, and open questions.