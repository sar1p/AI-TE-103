# Warehouse interface design

The interface is a local operations console for a simulated warehouse robot.
Its primary task is to inspect a route, change a map or observation, and see the
computed consequence. The map, movement gate, and next available action take
priority over introductory copy.

## Design decisions

- Use a light working surface, graphite text, restrained borders, and one blue
  accent. Amber and red identify cautions and paused movement. Color is paired
  with written status so it is not the only signal.
- Place mission controls close to the warehouse map. Keep scenario selection,
  reset, route overlay, and movement controls consistent between reruns.
- Display actual position, remaining cost, and map revision. Do not present
  unmeasured battery readings, diagnostic confidence, or performance claims.
- Provide guided observations with an explicit Unknown choice and real named
  scenarios. Advanced JSON remains available for inspection and boundary cases.
- Explain findings through their fired rules, premises, derived facts, and
  recommendations. A compact summary comes before the complete trace.
- Put detailed algorithm counters, source metadata, and raw JSON behind clearly
  labeled sections. Preserve exports for reproducing results.
- Use ordinary text labels and sentence case. Avoid decorative marketing copy,
  gradients, glowing panels, or unrelated imagery.
- Keep controls accessible through labels and keyboard operation. On narrow
  windows, stack panels and allow deliberate map overflow rather than compressing
  cells beyond legibility.

The actual observation choices come from the validated knowledge-base schema.
The interface does not supply a diagnosis of its own or interpret an Unknown
selection as a negative observation.

## References and tools

The [IBM Carbon data-table guidelines](https://www.carbondesignsystem.com/building-blocks/core/components/data-table/guidelines)
inform clear table titles, consistent density, readable column labels, and
progressive disclosure. They are design references; the application does not
bundle Carbon's React components.

[Streamlit's theming documentation](https://docs.streamlit.io/develop/concepts/configuration/theming)
and [container API](https://docs.streamlit.io/develop/api-reference/layout/st.container)
inform the implementation using the project's pinned Streamlit version. Native
widgets keep working labels, state, and input handling; small scoped CSS and a
repository-native grid renderer provide the visual treatment.

The available capabilities were checked before implementation. Browser control
and screenshots suit interaction and visual verification of this running app.
Git/GitHub CLI handles source history and required CI checks. Figma tools are
available for a supplied design file or a requested design artifact; no separate
cloud design file is needed for this revision. No additional UI package or
external image asset is required.

## Verification

Automated checks cover session persistence, safe map edits, observation parsing,
diagnostic gating, and corrected observations. Live browser checks must cover
scenario loading, guided input, the rule chain, pause/correction, route repair,
export downloads, and both narrow and wide layouts. Actual screenshots and
exported results are recorded with their source revision in the evidence guide.

These checks establish behavior and presentation in the simulation. They do not
validate a physical robot.
