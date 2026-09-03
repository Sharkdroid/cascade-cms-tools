# Why there's no "lite" version of the skill

`cascade-script-writer` used to ship in two forms: a full skill, and a
`-lite` variant with a ~3.5k-token budget aimed at small/fast models —
single-operation scripts only, everything else routed to the full skill.
That split is gone. This is why, and what it means for which model you
should point at this tooling.

## What we actually saw

Lite's premise was that most script-writing tasks are simple enough for a
small model to handle inside a tight token budget, with the full skill as a
fallback for anything more involved. In practice, this didn't hold. A real
multi-agent session tasked with generating a bulk asset-management
script — create new assets, edit existing ones, move/rename structured-data
nodes, all from one CSV — was built entirely inside the lite skill, despite
lite's own stated scope saying multi-operation pipelines should escalate to
the full skill. The escalation never happened. Nothing enforced it; it was
prose in a description field, and the agent driving the session had no
reason to notice it applied.

That session is not an edge case. Once you're describing actual business
logic rather than a single read/write, "one operation" is the exception,
not the rule. A skill scoped to single-operation scripts is scoped to a
shape of task that real usage mostly isn't.

## The deeper problem: the model tier lite targeted isn't reliable enough to design around

Lite's token budget existed to make the skill usable by small, fast, often
free-tier models — the assumption being that a tighter, cheaper prompt
would let those models handle simple cases reliably. Looking into this
further, that assumption doesn't hold either, for two separate reasons:

**Weak cloud models are unreliable at structured, multi-step generation
specifically**, not just "a bit worse" than frontier models. Independent
benchmarking (Scale AI's SWE-Bench Pro analysis) found that smaller models
don't just score lower on average — they're *erratic*: succeeding on some
tasks and failing almost completely on others of similar difficulty, where
larger models show more consistent, generalizable problem-solving. For a
tool meant to be handed to anyone, unpredictable failure is worse than a
flat, lower success rate — you can't tell a user in advance which of their
tasks will hit the failure mode.

**Free-tier access to capable models is not a stable target.** In the
course of evaluating this, we watched several free or low-cost agentic
coding options change out from under us within a single quarter: a major
CLI tool's free serving being discontinued outright, a free usage quota
being cut after launch, an actively-maintained open-source fork going
unmaintained, and a promotional "free in this tool" model offer reverting
to paid. Designing a skill's token budget around "whatever free model is
currently available" means re-tuning that budget every few weeks against a
target that's actively shrinking, not growing.

**Local, self-hosted models are a distinct failure mode, not a stable free
alternative.** It's tempting to treat "run something locally via Ollama" as
the free option once cloud free tiers prove unstable. It isn't a clean
substitute: tool-calling reliability in local models can collapse
independently of how good the model's raw code output looks, and this is
most pronounced at the quantization levels realistically deployable on
consumer hardware. A model can score well on code-quality metrics while
being nearly unusable as an agent — failing to invoke tools in the expected
format, or not emitting tool calls at all. Since this skill's value is
partly delivered through a companion MCP server (schema-authoritative field
lookups, not guesswork), a model that can't reliably call tools loses that
benefit even if it could otherwise write a correct script when handed the
right information directly. And the hardware capable of running local
models at quantization levels where this problem eases (Q6/FP8 and above)
costs more up front than a paid model subscription costs over several
years — so it isn't meaningfully "free" once that's priced in.

Put together: the audience lite was built to serve — small/free-tier
models, working from a deliberately thin instruction budget — isn't a
reliable target. Trimming the skill down further to fit that audience
better would mean optimizing for a moving target that's already
unreliable at the task.

## What we did instead

One skill, no token-budget compromise. `cascade-script-writer` is written
for an agent capable of reading full instructions, calling the companion
MCP server's tools, and iterating on validator failures — not for the
weakest model that might be pointed at it. See
[`model-requirements.md`](./model-requirements.md) for what that
capability floor means in practice, and for honest free-vs-paid guidance
rather than a specific "current best free model" recommendation that would
go stale within weeks.

This isn't a claim that everyone needs a frontier model for everything.
Writing directly against `cascade-cms-rest` — no skill, no MCP, no
agent — remains fully supported and is often the better choice for a
simple, one-off script. The skill and MCP earn their keep specifically for
multi-step business logic, and for cases where the requirements change
often enough that repeatedly re-deriving correct API usage by hand is the
actual recurring cost. If that's not your situation, you may not need this
tooling at all, and that's a fine outcome.
