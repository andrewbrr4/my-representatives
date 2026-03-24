# Elections Feature — Work in Progress

## Branch: `elections`

Pushed to remote. Resume with `git checkout elections`.

## What's done

- **Design spec:** `docs/superpowers/specs/2026-03-24-upcoming-elections-design.md`
- **Implementation plan (12 tasks, full code):** `docs/superpowers/plans/2026-03-24-upcoming-elections.md`
- **Task 1:** Backend data models — 9 new Pydantic models in `backend/models.py` + migration `002_add_task_type_to_research_tasks.sql`
- **Task 2:** Parameterized `InMemoryResearchStore` — supports both rep (7 sections) and election (2 sections) research

## What's left

| Task | What |
|------|------|
| 3 | Election cache interface + Redis (`store/interfaces.py`, `redis.py`, `dependencies.py`) |
| 4 | Google Civic API service (`services/elections.py`) |
| 5 | Election research pipeline (`research/election_pipeline.py` + prompts) |
| 6 | Elections router + wire into `main.py` + update `db.py` |
| 7 | React Router + AddressContext + TabNav |
| 8 | SearchPage + RepresentativesPage (extract from App.tsx) |
| 9 | Election TypeScript types + hooks |
| 10 | ElectionsPage + ElectionCard + CandidateCard |
| 11 | Integration verification |
| 12 | Update CLAUDE.md |

## How to resume

Open Claude Code and say:

> Continue implementing the elections plan starting from Task 3. Plan is at `docs/superpowers/plans/2026-03-24-upcoming-elections.md`. Tasks 1-2 are done. Use subagent-driven development.

The plan file has complete code for every task — it's mostly mechanical from here.
