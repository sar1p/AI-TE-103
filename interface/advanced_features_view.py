"""Visual components for advanced AI methods: AD*, CBS, Bayesian Network, and ANFIS."""

import streamlit as st

from expert_system.anfis import ANFIS, generate_warehouse_training_data
from expert_system.bayesian_network import get_default_warehouse_bayesian_network
from search_algorithm.ad_star import ad_star
from search_algorithm.cbs import AgentTask, cbs_search, find_first_conflict
from search_algorithm.grid import Grid


def render_ad_star_section(grid: Grid, start: tuple[int, int], goal: tuple[int, int]) -> None:
    """Render interactive AD* controls and anytime convergence metrics."""
    st.markdown("#### AD* (Anytime Dynamic A*) Search")
    st.caption(
        "Finds an initial path quickly using inflated heuristic epsilon, then refines it "
        "progressively towards optimal (epsilon = 1.0) within your time budget."
    )

    c1, c2, c3 = st.columns(3)
    with c1:
        initial_eps = st.slider("Initial Epsilon", min_value=1.0, max_value=3.5, value=2.5, step=0.5, key="ad_init_eps")
    with c2:
        eps_step = st.slider("Epsilon Step", min_value=0.1, max_value=1.0, value=0.5, step=0.1, key="ad_eps_step")
    with c3:
        budget_ms = st.number_input("Time Budget (ms)", min_value=1.0, max_value=500.0, value=50.0, step=10.0, key="ad_budget_ms")

    if st.button("Run AD* Search", key="btn_run_ad_star", width="stretch"):
        result = ad_star(
            grid=grid,
            start=start,
            goal=goal,
            time_budget_ms=float(budget_ms),
            initial_epsilon=float(initial_eps),
            min_epsilon=1.0,
            epsilon_step=float(eps_step),
        )

        if result.status == "found":
            st.success(f"Path found! Cost: {result.cost} moves in {result.metrics.elapsed_ms:.2f} ms (Epsilon: {result.epsilon:.2f})")
            if result.solutions:
                st.markdown("**Anytime Progression History:**")
                table_data = [
                    {
                        "Iteration": i + 1,
                        "Epsilon": s["epsilon"],
                        "Path Cost": s["cost"],
                        "Elapsed (ms)": s["elapsed_ms"],
                        "Waypoints": len(s["path"]),
                    }
                    for i, s in enumerate(result.solutions)
                ]
                st.dataframe(table_data, hide_index=True, width="stretch")
        elif result.status == "unreachable":
            st.error("Goal is unreachable on the current map.")
        else:
            st.warning(f"AD* status: {result.status} - {result.message}")


def render_cbs_section(grid: Grid) -> None:
    """Render interactive Conflict-Based Search (CBS) for multi-agent path finding."""
    st.markdown("#### Conflict-Based Search (CBS) Multi-Robot Routing")
    st.caption(
        "Solves multi-agent path finding (MAPF) by resolving vertex conflicts (same cell collision) "
        "and edge swap conflicts (narrow aisle passing) using a Conflict Tree."
    )

    scenario_type = st.selectbox(
        "Multi-Agent Demo Scenario",
        [
            "2 Robots Crossing Paths (Vertex Conflict)",
            "2 Robots Swapping in Narrow Passage (Edge Swap)",
            "3 Robots Warehouse Junction",
        ],
        key="cbs_scenario_choice",
    )

    if scenario_type == "2 Robots Crossing Paths (Vertex Conflict)":
        tasks = [
            AgentTask(agent_id="Robot-1", start=(0, 0), goal=(min(grid.height - 1, 3), min(grid.width - 1, 3))),
            AgentTask(agent_id="Robot-2", start=(0, min(grid.width - 1, 3)), goal=(min(grid.height - 1, 3), 0)),
        ]
    elif scenario_type == "2 Robots Swapping in Narrow Passage (Edge Swap)":
        tasks = [
            AgentTask(agent_id="Robot-1", start=(0, 0), goal=(0, min(grid.width - 1, 4))),
            AgentTask(agent_id="Robot-2", start=(0, min(grid.width - 1, 4)), goal=(0, 0)),
        ]
    else:
        tasks = [
            AgentTask(agent_id="Robot-1", start=(0, 0), goal=(min(grid.height - 1, 4), min(grid.width - 1, 4))),
            AgentTask(agent_id="Robot-2", start=(min(grid.height - 1, 4), 0), goal=(0, min(grid.width - 1, 4))),
            AgentTask(agent_id="Robot-3", start=(min(grid.height - 1, 2), 0), goal=(min(grid.height - 1, 2), min(grid.width - 1, 4))),
        ]

    # Filter tasks to ensure coordinates are valid in current grid
    valid_tasks = []
    for t in tasks:
        if (
            0 <= t.start[0] < grid.height
            and 0 <= t.start[1] < grid.width
            and 0 <= t.goal[0] < grid.height
            and 0 <= t.goal[1] < grid.width
            and t.start not in grid.blocked
            and t.goal not in grid.blocked
        ):
            valid_tasks.append(t)

    if st.button("Solve Multi-Robot Paths with CBS", key="btn_run_cbs", width="stretch"):
        if len(valid_tasks) < 2:
            st.warning("Current grid size/obstacles cannot accommodate this multi-agent configuration.")
            return

        res = cbs_search(grid, valid_tasks)
        if res.status == "found":
            st.success(
                f"Conflict-free paths found! Total Cost (Sum of Costs): {res.cost} | "
                f"Makespan: {res.makespan} ticks | Conflicts Resolved: {res.conflicts_resolved} | "
                f"Time: {res.elapsed_ms:.2f} ms"
            )

            # Display individual robot paths
            robot_data = []
            for ar in res.agent_results:
                robot_data.append({
                    "Agent": ar.agent_id,
                    "Start": str(ar.start),
                    "Goal": str(ar.goal),
                    "Steps / Cost": ar.cost,
                    "Path Coordinates": " -> ".join(f"({r},{c})" for r, c in ar.path),
                })
            st.dataframe(robot_data, hide_index=True, width="stretch")
        else:
            st.error(f"CBS could not find conflict-free paths: {res.message}")


def render_bayesian_and_anfis_section() -> None:
    """Render interactive Bayesian Network and ANFIS diagnostic panels."""
    st.markdown("#### Bayesian Network Probabilistic Fault Diagnosis")
    st.caption(
        "Calculates exact posterior fault probabilities P(Fault | Sensor Evidence) "
        "rather than binary IF-THEN rules."
    )

    bn = get_default_warehouse_bayesian_network()

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        temp = st.selectbox("Motor Temperature", ["(unknown)", "normal", "high"], key="bn_temp")
    with col2:
        curr = st.selectbox("Current Draw", ["(unknown)", "normal", "high"], key="bn_curr")
    with col3:
        volt = st.selectbox("Voltage Drop", ["(unknown)", "normal", "high"], key="bn_volt")
    with col4:
        vibr = st.selectbox("Vibration", ["(unknown)", "low", "high"], key="bn_vibr")

    evidence = {}
    if temp != "(unknown)":
        evidence["MotorTemperature"] = temp
    if curr != "(unknown)":
        evidence["CurrentDraw"] = curr
    if volt != "(unknown)":
        evidence["VoltageDrop"] = volt
    if vibr != "(unknown)":
        evidence["Vibration"] = vibr

    diagnoses = bn.diagnose_all_faults(
        fault_variables=["MotorOverheat", "BatteryFault", "DriveTrainFault"],
        evidence=evidence,
    )

    res_col1, res_col2, res_col3 = st.columns(3)
    with res_col1:
        prob_overheat = diagnoses["MotorOverheat"]["true"]
        st.metric("P(Motor Overheat)", f"{prob_overheat * 100:.1f}%")
        st.progress(prob_overheat)
    with res_col2:
        prob_battery = diagnoses["BatteryFault"]["true"]
        st.metric("P(Battery Fault)", f"{prob_battery * 100:.1f}%")
        st.progress(prob_battery)
    with res_col3:
        prob_drive = diagnoses["DriveTrainFault"]["true"]
        st.metric("P(Drive Train Fault)", f"{prob_drive * 100:.1f}%")
        st.progress(prob_drive)

    st.divider()

    st.markdown("#### ANFIS (Adaptive Neuro-Fuzzy Inference System)")
    st.caption(
        "Trained Takagi-Sugeno neuro-fuzzy model estimating traversal delay and energy consumption "
        "based on route distance and warehouse clutter density."
    )

    a1, a2 = st.columns(2)
    with a1:
        dist_input = st.slider("Normalized Planned Distance (0.0 = short, 1.0 = long)", 0.05, 1.0, 0.65, 0.05, key="anfis_dist")
    with a2:
        clutter_input = st.slider("Obstacle Clutter / Congestion (0.0 = open, 1.0 = packed)", 0.0, 1.0, 0.40, 0.05, key="anfis_clutter")

    if "trained_anfis" not in st.session_state:
        # Pre-train a lightweight ANFIS model once in session state
        X_train, y_train = generate_warehouse_training_data(n_samples=60, seed=42)
        model = ANFIS(n_inputs=2, mfs_per_input=2, seed=42)
        model.fit(X_train, y_train, epochs=20, learning_rate=0.03)
        st.session_state["trained_anfis"] = model

    anfis_model: ANFIS = st.session_state["trained_anfis"]
    predicted_time = anfis_model.predict_one([dist_input, clutter_input])

    m1, m2 = st.columns(2)
    with m1:
        st.metric("Estimated Traversal Time", f"{predicted_time:.2f} time units")
    with m2:
        estimated_battery_cost = predicted_time * 1.85
        st.metric("Estimated Battery Drain", f"{estimated_battery_cost:.1f}%")

    with st.expander("View Takagi-Sugeno Fuzzy Rules and Parameters"):
        st.json(anfis_model.to_dict())
