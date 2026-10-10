"""Reusable, plain-language presentation for simulation and diagnosis results."""

from html import escape
import json
from typing import Any

import streamlit as st


def route_status_strip(items: list[tuple[str, Any]]) -> None:
    """Show the current planner state in a compact responsive strip."""
    values = "".join(
        "<div class='route-status-item'>"
        f"<div class='route-status-label'>{escape(label)}</div>"
        f"<div class='route-status-value'>{escape(str(value))}</div>"
        "</div>"
        for label, value in items
    )
    st.html(
        f"""<style>
        .route-status-strip {{
          display: grid; grid-template-columns: repeat({len(items)}, minmax(0, 1fr));
          gap: 1px; border: 1px solid #d6dde2; border-radius: 4px;
          background: #d6dde2; overflow: hidden;
        }}
        .route-status-item {{ background: #ffffff; padding: 10px 14px; min-width: 0; }}
        .route-status-label {{ color: #596773; font: 11px system-ui, sans-serif;
          letter-spacing: .025em; }}
        .route-status-value {{ color: #1f2d37; font: 600 14px system-ui, sans-serif;
          margin-top: 3px; overflow-wrap: anywhere; }}
        @media (max-width: 760px) {{
          .route-status-strip {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
        }}
        </style><div class="route-status-strip">{values}</div>"""
    )


def _label(value: str) -> str:
    return value.replace("_", " ").strip().capitalize()


def _inline_value(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, allow_nan=False)


def _field_values(values: dict[str, Any]) -> str:
    return " · ".join(f"{_label(key)} = {_inline_value(value)}" for key, value in values.items())


def _finding_steps(finding: dict[str, Any], trace: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return only the traced rules that directly derive this final finding."""
    rule_ids = set(finding["rule_ids"])
    return [
        step
        for step in trace
        if step["rule_id"] in rule_ids
        and step["conclusion"].get("condition") == finding["condition"]
    ]


def render_diagnostic_result(result: dict[str, Any], observed_facts: dict[str, Any]) -> None:
    """Render concise findings and keep their full premise proofs in one expander."""
    status = result["status"]
    trace = result["rule_trace"]
    st.markdown(f"**Diagnosis status:** `{status}`")

    if status == "ok":
        st.success("The submitted observations produced a valid diagnostic result.")
    elif status == "insufficient_evidence":
        st.warning("Evidence is incomplete. The diagnostic safety gate requires complete observations before movement.")
    else:
        st.warning("The observations were rejected by the diagnostic rules. The diagnostic safety gate blocks movement for invalid observations.")

    st.markdown("#### Findings")
    if result["findings"]:
        for finding in result["findings"]:
            direct_steps = _finding_steps(finding, trace)
            if direct_steps:
                for step in direct_steps:
                    st.markdown(
                        f"- **{_label(finding['condition'])}** · `{step['rule_id']}` — "
                        f"{step['reason']}"
                    )
            else:
                st.markdown(
                    f"- **{_label(finding['condition'])}** · "
                    f"rules {', '.join(finding['rule_ids'])}"
                )
    else:
        st.caption("No rule returned a finding for these observations.")

    pause_reasons = list(dict.fromkeys(
        item["reason"] for item in result["recommendations"]
        if item["action"] == "pause_robot" and item["reason"]
    ))
    other_actions = list(dict.fromkeys(
        (item["action"], item["reason"]) for item in result["recommendations"]
        if item["action"] != "pause_robot"
    ))
    st.markdown("#### Recommended actions")
    if pause_reasons:
        st.warning("Movement pause")
        for reason in pause_reasons:
            st.markdown(f"- {reason}")
    if other_actions:
        for action, reason in other_actions:
            text = f"**{_label(action)}**"
            st.markdown(f"- {text} — {reason}" if reason else f"- {text}")
    if not pause_reasons and not other_actions:
        st.caption("No action was returned by the diagnostic rules.")

    if result["missing_facts"]:
        st.info("Missing observations: " + ", ".join(_label(name) for name in result["missing_facts"]))

    if trace:
        chain = " → ".join(step["rule_id"] for step in trace)
        st.markdown(f"**Rule firing order:** `{chain}`")
        derived_conditions = list(dict.fromkeys(
            step["conclusion"]["condition"]
            for step in trace
            if type(step["conclusion"].get("condition")) is str
        ))
        if derived_conditions:
            st.caption("Derived conditions: " + ", ".join(_label(name) for name in derived_conditions))
    else:
        st.caption("No rule fired for these observations.")

    with st.expander(f"Inference trace and source proofs ({len(trace)} steps)"):
        for index, step in enumerate(trace, start=1):
            st.markdown(f"**Step {index} · {step['rule_id']}**")
            premises = step["premises"]
            observed = {
                key: value
                for key, value in premises.items()
                if key in observed_facts and observed_facts[key] is not None
            }
            derived = {key: value for key, value in premises.items() if key not in observed}
            if observed:
                st.caption("Observed premises: " + _field_values(observed))
            if derived:
                st.caption("Derived premises: " + _field_values(derived))
            if step["conclusion"]:
                st.caption("Derived conclusion: " + _field_values(step["conclusion"]))
            if step["reason"]:
                st.write(step["reason"])
        with st.expander("Trace JSON for evidence"):
            st.json(trace)

    st.caption(
        "This result reflects the supplied observations and documented illustrative rules. "
        "It does not verify the physical condition of a robot."
    )
