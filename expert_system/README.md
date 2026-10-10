# Expert system

Status: **two-rule starter; full teammate scope remains incomplete**.

The teammate introduced R01 (suspected motor overheating) and R02 (lidar
obstruction). The integration correction preserves that original commit and
returns the structured records required by
[the module contract](../docs/MODULE_CONTRACTS.md).

Both rules are illustrative simulation rules. They evaluate categorical
observations once; they do not implement chained inference or diagnose a physical
robot. See [EXPERT_SYSTEM.md](../docs/EXPERT_SYSTEM.md) for accepted observations,
running examples, correction behavior, and limitations.

Run the visual application from the repository root, select Diagnostics, and
enter the documented JSON examples. Enable the diagnostic safety gate to verify
that a fault or incomplete evidence pauses simulated movement.

```powershell
.\.venv\Scripts\python.exe -m pytest tests/expert_system tests/integration/test_expert_system_app.py -q
.\.venv\Scripts\python.exe -m streamlit run app.py --server.address 127.0.0.1
```

Remaining teammate work includes validated external rule data, actual forward
chaining, expanded named scenarios, an independent CLI, and final reproduction
and presentation evidence. Track that work in
[issue #3](https://github.com/sar1p/AI-TE-303/issues/3) and
[TEAMMATE_TASKS.md](../docs/TEAMMATE_TASKS.md).
