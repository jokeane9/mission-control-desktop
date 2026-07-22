# Does anyone care about monitoring the agents working on your repos?

**Demand validation + competitive scan for Orrery** — the local watchtower over the
exhaust AI coding agents leave across git repos.

*Prepared July 2026 · lean web scan, adversarial read · sources at end.*
*The question isn't "is it clever." It's "does anyone feel this pain enough to want it."*

---

## Executive summary

**Yes — the demand is real and present, not 1–2 years early.** But the pain that is
*quantified and screaming* is not "watch my agent sessions and worktrees." It is the
**trust & review bottleneck**: agents now produce code far faster than humans can verify
it, and every measured signal points there.

That single finding should **reshape Orrery's positioning**. The pure session/worktree
watchtower is genuine whitespace — but it's the *quieter* pain. The "run agents in
parallel" adjacency is loud but **crowded with orchestrators**. The loudest,
most-monetizable demand sits in **verification**: what got reviewed, what got tested, did
the agent do what it claimed. Angle the watchtower there.

Meanwhile, **absorption is accelerating** — Anthropic, Augment, and Microsoft all shipped
agent-coordination or agent-review features in 2026. The window is open but heating.
Orrery's durable edge is the one none of them will build: **cross-tool, local, read-only**
— the neutral pane that watches every agent vendor at once, joined to git.

---

## Key takeaways

| Signal | Takeaway |
|---|---|
| 🟢 **Strong** | **The review/validation bottleneck is the dominant, measured pain.** Teams merge 98% more PRs with AI — but review time is up 91% and AI PRs wait 4.6× longer to be picked up. This is the demand. |
| 🟢 **Strong** | **People care enough to build** — a wave of open-source parallel-agent tools. But note: they're *orchestration* (run more agents), not *observability* (see the mess). Different job. |
| 🟡 **Mixed** | **The observability category is huge and funded** (~$2.7B; Langfuse acquired by ClickHouse) — but aimed at agents you *build in production*, not the coding agents you *use* on your machine. |
| 🟠 **Caution** | **Incumbents are moving in fast** — Claude Code AI review agents, Augment "Cosmos", Microsoft Conductor, all 2026. Absorption risk is live, not theoretical. |
| 🟢 **Strong** | **The money and quantified pain are team-scale.** The fleet-manager fork aligns with existing DevEx budgets (Faros, LinearB audiences already pay to measure this). |
| 🔵 **Insight** | **Orrery's true whitespace = observability × cross-tool × local.** Nobody owns it. But because it's the quieter pain, *lead with trust*, not the session list. |

---

## 01 · The pain is measured, not anecdotal

The strongest demand signal isn't sentiment — it's telemetry. AI made *producing* code
cheap; *reviewing and trusting* it didn't speed up at all. A dev with an agent opens 5–6
PRs a day; the human queue behind them buckles.

| Figure | What it measures |
|---|---|
| **+98%** | more PRs merged by high-AI-adoption teams |
| **+91%** | longer PR review time |
| **4.6×** | longer wait before an AI PR is picked up |
| **39 pt** | gap: devs *feel* 20% faster, are 19% slower |

Sources: a Faros AI study of 10,000+ developers across 1,255 teams, and LinearB's analysis
of 8.1M pull requests. The refrain across industry writing in 2026: **"coding agents
generate PRs faster than anyone can review them — open-source maintainers are the first
casualties."** That is Orrery's user, described by strangers.

## 02 · Homegrown activity is exploding — but it's the wrong half

People care enough to build their own tooling — a strong signal. But almost all of it
solves **orchestration** (spawn agents in parallel, each in a git worktree), not
**observability** (watch what they did and left behind).

- **parallel-code, FleetCode, Claude Squad, Code Conductor, Microsoft Conductor,
  Conductor (Melty Labs)** — run multiple CLI agents side by side in isolated worktrees.
- "9 open-source agent orchestrators" roundups already exist; Claude Code's own docs now
  cover worktrees + `isolation: worktree`.
- **The tell:** this crowd wants to *run more*, mostly on their own machine. Nobody in this
  set is building the neutral, cross-tool, read-only *watchtower* — that lane is open.

## 03 · The category is real and funded — aimed elsewhere

The "agent observability" market validates the *pattern* (a monitoring layer forms around
every new class of worker) but the incumbents point at production apps, not your local
coding agents.

- Braintrust, LangSmith, Arize, Helicone, Datadog LLM Observability — a ~$2.7B market;
  **Langfuse was acquired by ClickHouse (Jan 2026)** at 2,000+ paying customers. All target
  **agents you build and ship**.
- **Absorbers to watch:** Anthropic's Claude Code review agents (attacking the trust
  bottleneck from automation), **Augment "Cosmos"** (unified cloud-agents platform across
  the SDLC), Microsoft Conductor (Copilot + Anthropic SDKs).
- **Still open:** a cross-tool, local, read-only pane over the coding agents you *use*. No
  incumbent will build it — it means watching their competitors too.

---

## Recommendations — product positioning

The scan doesn't say "stop." It says "aim." Five moves, in order.

1. **Reposition: from "watchtower" to "trust plane."** Lead with the pain that's screaming:
   *what merged without review, what got tested, what did this agent actually change, did
   it do what it claimed.* Promote the verification view to the front of the roadmap, ahead
   of the softer session-watcher features.

2. **Keep the moat: observability, cross-tool, local — not orchestration.** Don't become the
   tenth FleetCode/Conductor. Your edge is watching **across Claude Code + Cursor + git, on
   your machine**. Orchestration is contested *and* it breaks the read-only trust posture
   that makes a watchtower believable.

3. **Build personal now; make team the north star.** Ship the personal power-tool (fast,
   defensible, you're the user). But shape the data model so a **team "fleet +
   review-bottleneck" view** is a natural extension — that's where willingness-to-pay is
   already proven (DevEx budgets).

4. **Race the absorbers with the cross-vendor angle.** Every agent vendor will build its own
   single-tool view. Your durable position is the **neutral pane no single vendor can
   build** — because it has to watch all of them. Say that out loud in the positioning.

5. **Instrument demand before you scale it.** The stats above are vendor-flavored. Validate
   cheaply: does *your* "PRs merged with no review/tests" view make you change behavior?
   Ship it, watch if power-users on Reddit/HN pull it. Let real pull, not this memo, fund
   the team build.

> **Positioning statement**
>
> *"Orrery — the trust plane for the agents working on your repos. See what they changed,
> what they left behind, and what shipped without review — across every tool, on your
> machine."*

---

## Sources

**Review bottleneck / telemetry** —
[Signadot](https://www.signadot.com/blog/ai-generated-code-crisis/) ·
[DEV: The Review Bottleneck](https://dev.to/code-board/the-review-bottleneck-why-more-ai-code-means-slower-teams-in-2026-1e5n) ·
[Moderne](https://moderne.ai/blog/ai-didnt-break-coding-it-broke-code-review) ·
[Codacy](https://blog.codacy.com/ai-breaking-code-review-how-engineering-teams-survive-pr-bottleneck)

**Homegrown / orchestration** —
[parallel-code](https://github.com/johannesjo/parallel-code) ·
[FleetCode](https://github.com/built-by-as/FleetCode) ·
[Claude Squad](https://github.com/kevensavard/Claude-Squad) ·
[Code Conductor](https://github.com/ryanmac/code-conductor) ·
[Microsoft Conductor](https://github.com/microsoft/conductor) ·
[Augment: 9 orchestrators](https://www.augmentcode.com/tools/open-source-agent-orchestrators) ·
[Claude Code worktrees docs](https://code.claude.com/docs/en/worktrees)

**Competitive / incumbents** —
[Confident AI: observability tools 2026](https://www.confident-ai.com/knowledge-base/compare/best-ai-agent-observability-tools-2026) ·
[Tessl: Claude Code review agents](https://tessl.io/blog/anthropic-launches-ai-code-review-agents-that-scan-pull-requests-for-bugs/) ·
[Augment: AI agent monitoring](https://www.augmentcode.com/guides/ai-agent-monitoring)

---

*Caveat: the sharpest statistics (Faros AI, LinearB) come from vendors with a commercial
interest in the "AI breaks review" narrative — treat them as directional, not gospel. This
was a lean scan, not an exhaustive market study; a deeper pass could surface a stealth
startup or platform feature not visible here.*
