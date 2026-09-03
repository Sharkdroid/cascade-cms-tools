# Model requirements

This skill and MCP server are written for an agent capable of reading full
instructions, calling the companion MCP server's tools, and iterating on
validator failures — not for the weakest model that might be pointed at
them. This page states that capability floor plainly, and gives honest
free-vs-paid guidance instead of naming a specific "current best free
option" that would go stale within weeks. See
[`why-no-lite-skill.md`](./why-no-lite-skill.md) for the fuller reasoning
behind dropping the token-minimized `-lite` variant this page's floor
replaces.

## The capability floor

To use `cascade-script-writer` reliably, an agent needs to:

- Read and follow multi-step instructions from `SKILL.md` without losing
  track of earlier steps.
- Call tools reliably — both `scripts/new_script.py`/`validate_script.py`
  and, when connected, the MCP server's schema tools. A model that can write
  correct code but fails to invoke tools in the expected format gets none of
  this tooling's actual value.
- Iterate on validator failures: read `validate_script.py`'s output, apply
  the specific fix it names, and re-run — not give up after one attempt or
  loop indefinitely on the same mistake.

This is a floor, not a recommendation to always reach for the largest
available model — see `SKILL.md`'s own "Model routing" section for routing
single-operation, template-driven work to a fast model and reserving
multi-operation/novel-pattern work for a frontier model.

## Free vs. paid: the pattern, not a specific recommendation

Free-tier access to capable agentic coding tools is not a stable target.
Over the course of building this tooling, several free or low-cost options
changed out from under it within a single quarter: a major CLI tool's free
serving being discontinued outright, a free usage quota being cut after
launch, an actively-maintained open-source fork going unmaintained, and a
promotional "free in this tool" model offer reverting to paid. Any
specific "best free option" named here would likely be wrong, or gone,
within weeks of being written down — so this page states the pattern
instead and asks you to check current status yourself:

- **Free/best-effort path.** Whatever free-tier agentic access is currently
  available to you may work, but expect it to be less reliable than a paid
  tier and to change without notice. Budget time for re-evaluating your
  setup periodically, not just once.
- **Recommended paid path.** A ~$20/mo-tier subscription to a frontier
  coding agent removes the need for any workaround built around a smaller
  model's limitations (a Plan/Act split, a trimmed instruction budget, etc.)
  and is the more predictable choice if this tooling is something you'll
  rely on regularly.

Independent benchmarking (Scale AI's SWE-Bench Pro analysis) found that
smaller models aren't just "a bit worse" at structured, multi-step
generation than frontier models — they're *erratic*, succeeding on some
tasks and failing almost completely on others of similar difficulty. For a
tool meant to be handed to anyone, that unpredictability is worse than a
flat, lower success rate: you can't tell in advance which of your tasks will
hit the failure mode.

## Local models: a separate, distinct caveat

Running a model locally (via Ollama or similar) is **not** treated as a
stable free alternative here — it's filed as unsupported, and for a
different reason than "weak cloud models are unreliable" above.

Tool-calling reliability in local models can collapse independently of how
good the model's raw code output looks, and this is most pronounced at the
quantization levels realistically deployable on consumer hardware. A model
can score well on code-quality benchmarks while being nearly unusable as an
agent — failing to invoke tools in the expected format, or not emitting tool
calls at all. Since this tooling's value is partly delivered through the
companion MCP server (schema-authoritative field lookups, not guesswork), a
model that can't reliably call tools loses that benefit even if it could
otherwise write a correct script when handed the right information
directly.

This eases at higher quantization (roughly Q6/FP8 and above), but the
hardware capable of running local models at that level costs more up front
than a paid model subscription costs over several years — so it isn't
meaningfully "free" once that's priced in.
