# Fuzzy speed control

Run the standalone illustrative controller from the repository root:

```text
python -m fuzzy_logic --clearance 3 --battery 85
python -m fuzzy_logic --method sugeno --clearance 3 --battery 85 --output artifacts/fuzzy.json
```

Inputs are clearance in grid cells (0–5) and a synthetic battery percentage
(0–100). Output is a proposed speed percentage, not a physical motor command.
Both methods expose memberships and rule activations. Mamdani returns a sampled
aggregate and centroid proof; Sugeno returns weighted singleton contributions.

The **Fuzzy speed control** tab visualizes these results, and **Fleet coordination**
uses the selected method to change actual simulated movement cadence.
Diagnosis and traffic reservations retain priority.

See [the model guide](../docs/FUZZY_LOGIC.md) for definitions, limitations,
method references, advanced alternatives, and test commands.
