# Cooperative warehouse agents

```text
python -m multi_agent_system --ticks 12 --output artifacts/multi-agent.json
python tools/fleet_demo.py --method mamdani --output artifacts/fleet-mamdani.json
```

The standalone module gives each robot an independent persistent D* Lite
planner. Robots submit next-cell requests and react to grants or denials from
a traffic coordinator. The module CLI uses full-speed discrete steps; the
integrated replay additionally applies per-robot diagnosis and fuzzy cadence.

The current policy reserves cells that are free at the start of a tick and
rejects duplicate destinations and position swaps. It can wait indefinitely
in a single-width head-on deadlock. It does not implement CBS, WHCA*, or
continuous-time fleet scheduling.

See [the module guide](../docs/MULTI_AGENT_SYSTEM.md) for the API, exact model,
invariants, known limitations, primary references, and extension options.
