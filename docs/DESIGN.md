# MyReps — Design Approach

This document captures the design thinking, tradeoffs, and open challenges behind MyReps. It's a living document — update it as the product evolves.

For the product vision and principles that inform these decisions, see [MISSION.md](./MISSION.md).

## Overall Design

1. User enters their address.
2. Third-party APIs return a list of representatives at every level of government.
3. A research agent crawls the web to gather information about each representative.
4. The user is presented with a "summary card" for each representative containing the research results.

![UI example](./ui_example.png)

## Summary Card Content

Agentic coding via Claude Code makes the technical aspects of building the functionality quite smooth. The true challenge of this project lies in the design of the product itself — specifically, crafting the content of the summary cards. For now, we are more focused on optimizing this content than the visual UI components such as color, font, etc.

The content in these cards is ultimately determined by the prompts given to the [research agent](../backend/services/research.py) and the Pydantic models used to structure the data.

### Challenges

Crafting these cards is not easy. We need to strike several difficult balances:

- **Comprehensive information vs. conciseness** — give people enough to be useful without overwhelming them.
- **No PR spin, but still nonpartisan** — cut through talking points and present substance, without editorializing or taking sides.
- **Government speak vs. real-world impact** — translate policy language into plain terms so people can understand what actually affects them.

## Options to Explore

<!-- TODO: Fill out when ready -->
