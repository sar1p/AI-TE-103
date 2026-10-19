"""Interactive, inspectable Mamdani and Sugeno speed recommendations."""

import json

import streamlit as st

from fuzzy_logic import configuration, evaluate_speed, evaluate_sugeno_speed


def render_fuzzy_tab() -> dict:
    st.subheader("Fuzzy speed control")
    st.caption(
        "Explore crisp inputs, memberships, active rules, and the final speed proposal. "
        "The fleet workspace applies these controllers to actual simulated move cadence."
    )
    left, right = st.columns(2)
    with left:
        clearance = st.slider(
            "Obstacle clearance (grid cells)", 0.0, 5.0, 3.0, 0.1, key="fuzzy_clearance",
        )
    with right:
        battery = st.slider(
            "Battery reading (%)", 0.0, 100.0, 85.0, 1.0, key="fuzzy_battery",
        )
    mamdani = evaluate_speed(clearance, battery)
    sugeno = evaluate_sugeno_speed(clearance, battery)
    comparison = {"mamdani": mamdani, "sugeno": sugeno}
    st.session_state.fuzzy_comparison = comparison
    metrics = st.columns(2)
    metrics[0].metric("Mamdani proposal", f"{mamdani['output']['speed_percent']:.2f}%")
    metrics[1].metric("Sugeno proposal", f"{sugeno['output']['speed_percent']:.2f}%")
    st.caption(
        "Both methods use the same input memberships and antecedent rules. Mamdani aggregates clipped fuzzy "
        "sets and approximates their centroid; Sugeno averages rule singleton outputs. Different outputs do not establish which is better."
    )
    st.markdown("**Fuzzification**")
    st.dataframe([
        {"Input": name, "Term": term, "Membership": round(value, 5)}
        for name, terms in mamdani["memberships"].items()
        for term, value in terms.items()
    ], hide_index=True, width="stretch")
    st.markdown("**Rule activation**")
    st.dataframe(mamdani["rules"], hide_index=True, width="stretch")
    st.markdown("**Mamdani aggregation and centroid**")
    st.line_chart(
        mamdani["aggregation"], x="speed_percent", y="membership",
        x_label="Speed proposal (%)", y_label="Aggregated membership", height=230,
    )
    st.caption(
        f"Centroid = {mamdani['defuzzification']['numerator']:.4f} / "
        f"{mamdani['defuzzification']['denominator']:.4f}. "
        "The 0.5 percentage-point sampling grid introduces a documented numerical approximation."
    )
    with st.expander("Sugeno weighted contributions"):
        st.dataframe(sugeno["rules"], hide_index=True, width="stretch")
        st.json(sugeno["defuzzification"])
    with st.expander("Membership definitions, rules, and provenance"):
        st.json(configuration())
    st.caption(
        "Membership degrees are not probabilities. These illustrative thresholds are not calibrated to hardware; "
        "diagnostic stops and traffic reservations always override the proposal in the fleet simulation."
    )
    st.download_button(
        "Download fuzzy comparison (JSON)", json.dumps(comparison, indent=2, allow_nan=False),
        file_name="fuzzy-comparison.json", mime="application/json", key="fuzzy_download",
    )
    return comparison
