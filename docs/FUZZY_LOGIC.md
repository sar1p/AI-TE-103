# Illustrative fuzzy speed controller

## Purpose and scope

`fuzzy_logic` is a standalone fuzzy speed recommendation for the warehouse
simulation. It provides Mamdani inference by default and an optional
zero-order Sugeno comparison. Both map clearance in cells and battery
percentage to a speed percentage and normalized speed factor. The input
thresholds and output sets are illustrative coursework values. They are not
calibrated from field data, and membership degrees are not probabilities.

The controller does not implement stop safety, collision avoidance, or
reservation checks. A caller must override motion based on diagnostics and
reservations whenever those checks require it. The returned speed value is an
illustrative recommendation, not a physical robot command.

## Model

Each input is fuzzified with triangular membership functions. Repeated triangle
endpoints create left or right shoulders: the membership is one at that
endpoint and then falls or rises linearly across the set. For a triangle with
parameters `(left, peak, right)`, the degree rises linearly from `left` to
`peak`, then falls linearly to `right`.

| Variable | Set | Triangle `(left, peak, right)` |
|---|---|---:|
| Clearance (cells) | near | `(0, 0, 1.5)` |
| Clearance (cells) | medium | `(0.5, 2, 3.5)` |
| Clearance (cells) | far | `(2.5, 5, 5)` |
| Battery (percent) | low | `(0, 0, 35)` |
| Battery (percent) | medium | `(20, 50, 80)` |
| Battery (percent) | high | `(65, 100, 100)` |
| Speed (percent) | slow | `(0, 0, 40)` |
| Speed (percent) | medium | `(20, 50, 80)` |
| Speed (percent) | fast | `(60, 100, 100)` |

The nine IF-THEN rules use the minimum of the clearance and battery degrees as
the rule activation. Their stable IDs are `F01` through `F09`, distinct from
the expert system's `Rxx` identifiers.

| Clearance \ Battery | low | medium | high |
|---|---|---|---|
| near | slow | slow | slow |
| medium | slow | medium | medium |
| far | slow | medium | fast |

### Mamdani (default)

Each consequent set is clipped at its rule activation, and the clipped
consequents are combined with the maximum operator. The crisp output is the
centroid of the aggregated output membership curve.

The implementation samples speed from 0 through 100 percent at 0.5-point
intervals (201 points). It estimates both centroid integrals with composite
trapezoidal quadrature on that uniform grid:

```text
speed_percent = integral(speed * membership) / integral(membership)
speed_factor  = speed_percent / 100
```

The reported numerator and denominator are the two approximate integrals.
The step size means this is a numerical approximation to the centroid.

### Zero-order Sugeno

`evaluate_sugeno_speed` uses the same validated inputs, membership functions,
minimum antecedent firing strengths, and rule matrix. Each rule consequent is
a fixed singleton speed, selected here as the analytic centroid of the
corresponding triangle: slow `40/3`, medium `50`, and fast `260/3` percent.
The output is the firing-strength-weighted average of the active singleton
values:

```text
speed_percent = sum(activation * singleton_percent) / sum(activation)
```

Because this method has no aggregated fuzzy output set, `aggregation` is an
empty list and `defuzzification.sample_step` is `null`. These singleton values
are illustrative. Using triangle centroids as singletons does not make the
Sugeno and Mamdani evaluators equivalent: the former averages rule outputs,
while the latter aggregates clipped membership curves and then computes a
centroid. The comparison does not assert monotonicity or a preferred result.

## Python API

```python
from fuzzy_logic import (
    FuzzyInputError,
    configuration,
    evaluate_speed,
    evaluate_sugeno_speed,
)

result = evaluate_speed(clearance_cells=3, battery_percent=80)
comparison = evaluate_sugeno_speed(clearance_cells=3, battery_percent=80)
print(result["output"]["speed_factor"])
controller_configuration = configuration()
```

`evaluate_speed(clearance_cells, battery_percent)` accepts finite built-in
`int` or `float` values, excluding booleans. Clearance must be in `[0, 5]` and
battery in `[0, 100]`. Invalid types, non-finite floats, or out-of-range values
raise `FuzzyInputError`, which is a `ValueError`.

Both evaluators return a JSON-shaped dictionary with `inputs`, `memberships`,
nine `rules` and their activations, `output`, `aggregation`, defuzzification
metadata, and provenance identifying the illustrative model and method.
Mamdani returns 201 aggregation points; Sugeno returns an empty aggregation
list and includes each rule's `singleton_percent`. Inputs and configuration
are not mutated, and each call to `configuration()` returns an isolated copy
containing universes, membership definitions, the rule table, both numerical
methods, provenance, and limitations.

## Command line

From the repository root, run:

```powershell
.\.venv\Scripts\python.exe -m fuzzy_logic --clearance 3 --battery 80
```

This runs Mamdani inference. Add `--method sugeno` to select zero-order Sugeno.
The command writes strict JSON to standard output. Add `--output result.json`
to write the JSON to a UTF-8 file instead. Invalid controller input returns
exit code 2 and writes a concise error to standard error. The module does not
import Streamlit.

## Alternatives and professional practice

Mamdani inference is a reasonable match for this coursework exercise because
its IF-THEN rules and fuzzy output sets are visible and easy to inspect. That
does not make it an appropriate safety controller. A simulation speed
recommendation can remain a separate advisory layer while independent safety
logic retains authority over motion and stopping.

Keep this output as a simulated performance recommendation. Nav2 illustrates
separate software layers for sensor-based stop or
slowdown filtering and velocity/acceleration smoothing; its CPU collision
monitor is explicitly not hard-real-time safety-certified
([Collision Monitor](https://docs.nav2.org/rolling/tutorials/general_tutorials/using_collision_monitor/using_collision_monitor/),
[Velocity Smoother](https://docs.nav2.org/rolling/configuration_and_development/configuration_guide/core_servers/configuring_velocity_smoother/),
[Nav2 project notes](https://github.com/ros-navigation/navigation2/blob/main/nav2_collision_monitor/README.md)).

Advanced alternatives are worth considering only when they solve a measured
need:

- **Sugeno / Takagi-Sugeno-Kang (TSK):** this repository includes a zero-order
  comparison with constant singleton consequents and a firing-strength
  weighted average. The selected singleton values are the analytic centroids
  of the Mamdani output triangles, but the inference methods can still return
  different results. Broader Sugeno systems can use functional consequents;
  the original TSK identification paper uses linear input-output relations.
  Consider them when a measured input-output model is needed, and compare on
  explicit scenarios and constraints ([MathWorks overview](https://www.mathworks.com/help/fuzzy/types-of-fuzzy-inference-systems.html),
  [Takagi and Sugeno, 1985](https://doi.org/10.1109/TSMC.1985.6313399)).
- **Adaptive neuro-fuzzy inference (ANFIS):** combines a fuzzy inference
  structure with a hybrid learning procedure that uses expert rules and
  input-output data pairs. It requires representative, trustworthy training
  and validation data and controls for distribution shift; learned thresholds
  are not automatically safer or more accurate ([Jang, 1993](https://doi.org/10.1109/21.256541)).
- **Type-2 fuzzy systems:** represent uncertainty in membership functions with
  an additional uncertainty model. Common interval type-2 systems add a
  type-reduction step before producing a crisp value. Consider one only when
  uncertainty in the membership shapes materially affects decisions and can be
  characterized ([Mendel, 2007](https://doi.org/10.1109/MCI.2007.380672)).
- **Established fuzzy libraries:** a library such as
  [scikit-fuzzy control](https://scikit-fuzzy.readthedocs.io/en/latest/api/skfuzzy.control.html)
  provides reusable antecedent, consequent, rule, control-system, and
  simulation abstractions for larger models. This project keeps a short
  standard library implementation so each coursework operation is explicit
  and no new dependency is required.

The current model has only two inputs, three fuzzy sets per input, nine rules,
and fixed illustrative thresholds. It does not model acceleration, jerk,
vehicle dynamics, localization uncertainty, pedestrian interaction, traffic
coordination, or a robot's safety-rated protective functions. Before using a
controller in a physical deployment, replace illustrative assumptions with a
requirements-led design, measured data, independent validation, and the
applicable safety engineering process. More complex inference does not replace
those steps.
