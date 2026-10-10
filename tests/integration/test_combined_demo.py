"""Verify the combined evidence comes from real diagnostic and planner runs."""

from tools.combined_demo import run_demo


def test_combined_demo_captures_raw_chain_gate_correction_and_incremental_costs():
    payload = run_demo()

    fault, corrected = payload["diagnostic_sequence"]
    assert fault["event"] == "fault_observations"
    assert fault["facts"]["battery_voltage"] == "low"
    assert fault["facts"]["battery_connection"] == "disconnected"
    assert fault["facts"]["movement_status"] == "stalled"
    assert fault["result"]["status"] == "ok"
    assert {
        finding["condition"] for finding in fault["result"]["findings"]
    } == {"battery_power_path_issue", "battery_related_stall"}
    assert [step["rule_id"] for step in fault["result"]["rule_trace"]] == [
        "R03", "R04", "R05", "R06"
    ]
    assert fault["movement_allowed"] is False

    assert corrected["event"] == "corrected_observations"
    assert corrected["facts"]["movement_status"] == "moving"
    assert corrected["facts"]["battery_voltage"] == "normal"
    assert corrected["facts"]["battery_connection"] == "connected"
    assert corrected["result"]["status"] == "ok"
    assert all(
        corrected["result"][key] == []
        for key in ("findings", "rule_trace", "recommendations", "missing_facts")
    )
    assert corrected["movement_allowed"] is True

    rejected = payload["rejected_movement"]
    assert rejected["session_unchanged"] is True
    assert rejected["position"] == payload["search_session"]["scenario"]["start"]
    assert rejected["event_id"] == "corridor-step-around-shelves"

    session = payload["search_session"]
    assert session["scenario"]["id"] == "corridor-changes"
    records = session["records"]
    dstar_costs = [record["dstar_lite"]["cost"] for record in records]
    astar_costs = [record["astar"]["cost"] for record in records]
    assert dstar_costs == [10, 12, 11]
    assert astar_costs == dstar_costs
    assert [record["initialization_count"] for record in records] == [1, 1, 1]
    assert [event["type"] for event in session["applied_events"]] == ["map", "move"]
    start = session["scenario"]["start"]
    resumed = records[-1]["start"]
    assert abs(resumed[0] - start[0]) + abs(resumed[1] - start[1]) == 1
    assert all(payload["checks"].values())
