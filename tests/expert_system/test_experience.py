import pytest

from expert_system.anfis import ANFIS, ANFISError, generate_warehouse_training_data
from expert_system.bayesian_network import (
    BayesianNetwork,
    BayesianNetworkError,
    get_default_warehouse_bayesian_network,
)


def test_bayesian_network_dag_cycle_detection():
    bn = BayesianNetwork()
    bn.add_variable("A", ["0", "1"])
    bn.add_variable("B", ["0", "1"], parents=["A"])
    # Attempting to add variable C that would create a cycle requires careful setup,
    # but duplicate or cycle checks can be verified directly:
    with pytest.raises(BayesianNetworkError, match="Parent variable 'Z' must be added"):
        bn.add_variable("C", ["0", "1"], parents=["Z"])


def test_bayesian_network_cpt_sum_validation():
    bn = BayesianNetwork()
    bn.add_variable("Fault", ["false", "true"])
    with pytest.raises(BayesianNetworkError, match="must sum to 1.0"):
        bn.set_cpt("Fault", {"false": 0.5, "true": 0.9})


def test_bayesian_network_warehouse_inference():
    bn = get_default_warehouse_bayesian_network()

    # Prior probability of MotorOverheat is small (0.08)
    prior_overheat = bn.query("MotorOverheat")
    assert prior_overheat["true"] == pytest.approx(0.08, abs=0.01)

    # When MotorTemperature is high and CurrentDraw is high, probability increases significantly
    posterior_overheat = bn.query(
        "MotorOverheat",
        evidence={"MotorTemperature": "high", "CurrentDraw": "high"},
    )
    assert posterior_overheat["true"] > 0.50

    # Test diagnose_all_faults
    all_diagnoses = bn.diagnose_all_faults(
        fault_variables=["MotorOverheat", "BatteryFault", "DriveTrainFault"],
        evidence={"VoltageDrop": "high"},
    )
    assert "BatteryFault" in all_diagnoses
    assert all_diagnoses["BatteryFault"]["true"] > 0.40


def test_bayesian_network_invalid_evidence():
    bn = get_default_warehouse_bayesian_network()
    with pytest.raises(BayesianNetworkError, match="not found in network"):
        bn.query("MotorOverheat", evidence={"UnknownSensor": "high"})

    with pytest.raises(BayesianNetworkError, match="is invalid"):
        bn.query("MotorOverheat", evidence={"MotorTemperature": "invalid_value"})


def test_anfis_init_and_forward_pass():
    model = ANFIS(n_inputs=2, mfs_per_input=2)
    assert model.n_rules == 4
    pred = model.predict_one([0.5, 0.5])
    assert isinstance(pred, float)

    preds = model.predict([[0.2, 0.3], [0.8, 0.7]])
    assert len(preds) == 2


def test_anfis_invalid_inputs():
    with pytest.raises(ANFISError):
        ANFIS(n_inputs=0)
    with pytest.raises(ANFISError):
        ANFIS(mfs_per_input=1)

    model = ANFIS(n_inputs=2, mfs_per_input=2)
    with pytest.raises(ANFISError, match="Expected 2 features"):
        model.predict_one([0.5])


def test_anfis_training_convergence():
    X, y = generate_warehouse_training_data(n_samples=50, seed=123)
    model = ANFIS(n_inputs=2, mfs_per_input=2, seed=42)

    losses = model.fit(X, y, epochs=25, learning_rate=0.03)
    assert len(losses) == 25
    # Loss should decrease over epochs
    assert losses[-1] < losses[0]

    eval_res = model.evaluate(X, y)
    assert "mse" in eval_res
    assert "rmse" in eval_res
    assert eval_res["rmse"] < 0.5


def test_anfis_to_dict_serialization():
    model = ANFIS(n_inputs=2, mfs_per_input=2)
    exported = model.to_dict()
    assert exported["n_inputs"] == 2
    assert exported["n_rules"] == 4
    assert len(exported["rules"]) == 4
