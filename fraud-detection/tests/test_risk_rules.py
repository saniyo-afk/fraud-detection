from __future__ import annotations

import pytest
from risk_rules import label_risk, score_transaction


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def base_tx(**overrides) -> dict:
    """Minimal low-risk transaction; override individual fields per test."""
    tx = {
        "device_risk_score": 10,   # no points
        "is_international": 0,     # no points
        "amount_usd": 100,         # no points
        "velocity_24h": 1,         # no points
        "failed_logins_24h": 0,    # no points
        "prior_chargebacks": 0,    # no points
    }
    tx.update(overrides)
    return tx


# ---------------------------------------------------------------------------
# label_risk thresholds
# ---------------------------------------------------------------------------

class TestLabelRisk:
    def test_below_low_boundary(self):
        assert label_risk(0) == "low"

    def test_just_below_medium(self):
        assert label_risk(29) == "low"

    def test_medium_lower_boundary(self):
        assert label_risk(30) == "medium"

    def test_mid_medium(self):
        assert label_risk(45) == "medium"

    def test_just_below_high(self):
        assert label_risk(59) == "medium"

    def test_high_lower_boundary(self):
        assert label_risk(60) == "high"

    def test_max_score(self):
        assert label_risk(100) == "high"


# ---------------------------------------------------------------------------
# Device risk score
# ---------------------------------------------------------------------------

class TestDeviceRiskScore:
    def test_low_device_risk_adds_nothing(self):
        assert score_transaction(base_tx(device_risk_score=39)) == 0

    def test_medium_device_risk_adds_10(self):
        assert score_transaction(base_tx(device_risk_score=40)) == 10

    def test_medium_device_risk_boundary_top(self):
        assert score_transaction(base_tx(device_risk_score=69)) == 10

    def test_high_device_risk_adds_25(self):
        assert score_transaction(base_tx(device_risk_score=70)) == 25

    def test_max_device_risk_adds_25(self):
        assert score_transaction(base_tx(device_risk_score=100)) == 25


# ---------------------------------------------------------------------------
# International transactions
# ---------------------------------------------------------------------------

class TestInternational:
    def test_domestic_adds_nothing(self):
        assert score_transaction(base_tx(is_international=0)) == 0

    def test_international_adds_15(self):
        assert score_transaction(base_tx(is_international=1)) == 15


# ---------------------------------------------------------------------------
# Transaction amount
# ---------------------------------------------------------------------------

class TestAmount:
    def test_small_amount_adds_nothing(self):
        assert score_transaction(base_tx(amount_usd=499)) == 0

    def test_medium_amount_boundary_adds_10(self):
        assert score_transaction(base_tx(amount_usd=500)) == 10

    def test_medium_amount_just_below_large(self):
        assert score_transaction(base_tx(amount_usd=999)) == 10

    def test_large_amount_boundary_adds_25(self):
        assert score_transaction(base_tx(amount_usd=1000)) == 25

    def test_very_large_amount_adds_25(self):
        assert score_transaction(base_tx(amount_usd=50000)) == 25


# ---------------------------------------------------------------------------
# Transaction velocity (24 h)
# ---------------------------------------------------------------------------

class TestVelocity:
    def test_low_velocity_adds_nothing(self):
        assert score_transaction(base_tx(velocity_24h=2)) == 0

    def test_medium_velocity_boundary_adds_5(self):
        assert score_transaction(base_tx(velocity_24h=3)) == 5

    def test_medium_velocity_top_adds_5(self):
        assert score_transaction(base_tx(velocity_24h=5)) == 5

    def test_high_velocity_boundary_adds_20(self):
        assert score_transaction(base_tx(velocity_24h=6)) == 20

    def test_very_high_velocity_adds_20(self):
        assert score_transaction(base_tx(velocity_24h=20)) == 20


# ---------------------------------------------------------------------------
# Failed logins (account takeover signal)
# ---------------------------------------------------------------------------

class TestFailedLogins:
    def test_no_failed_logins_adds_nothing(self):
        assert score_transaction(base_tx(failed_logins_24h=0)) == 0

    def test_one_failed_login_adds_nothing(self):
        assert score_transaction(base_tx(failed_logins_24h=1)) == 0

    def test_two_failed_logins_adds_10(self):
        assert score_transaction(base_tx(failed_logins_24h=2)) == 10

    def test_four_failed_logins_adds_10(self):
        assert score_transaction(base_tx(failed_logins_24h=4)) == 10

    def test_five_failed_logins_adds_20(self):
        assert score_transaction(base_tx(failed_logins_24h=5)) == 20

    def test_many_failed_logins_adds_20(self):
        assert score_transaction(base_tx(failed_logins_24h=99)) == 20


# ---------------------------------------------------------------------------
# Prior chargebacks
# ---------------------------------------------------------------------------

class TestPriorChargebacks:
    def test_no_prior_chargebacks_adds_nothing(self):
        assert score_transaction(base_tx(prior_chargebacks=0)) == 0

    def test_one_prior_chargeback_adds_5(self):
        assert score_transaction(base_tx(prior_chargebacks=1)) == 5

    def test_two_prior_chargebacks_adds_20(self):
        assert score_transaction(base_tx(prior_chargebacks=2)) == 20

    def test_many_prior_chargebacks_adds_20(self):
        assert score_transaction(base_tx(prior_chargebacks=10)) == 20


# ---------------------------------------------------------------------------
# Score clamping
# ---------------------------------------------------------------------------

class TestScoreClamping:
    def test_score_cannot_exceed_100(self):
        tx = base_tx(
            device_risk_score=100,   # +25
            is_international=1,      # +15
            amount_usd=5000,         # +25
            velocity_24h=10,         # +20
            failed_logins_24h=10,    # +20
            prior_chargebacks=5,     # +20
        )
        assert score_transaction(tx) == 100

    def test_score_cannot_go_below_zero(self):
        # All-clean transaction; no signal should produce a negative score
        assert score_transaction(base_tx()) == 0


# ---------------------------------------------------------------------------
# Additive combinations (integration-style)
# ---------------------------------------------------------------------------

class TestCombinations:
    def test_all_low_risk_signals_scores_zero(self):
        assert score_transaction(base_tx()) == 0

    def test_high_risk_device_plus_international(self):
        tx = base_tx(device_risk_score=80, is_international=1)
        assert score_transaction(tx) == 40  # 25 + 15

    def test_large_amount_plus_high_velocity_plus_failed_logins(self):
        tx = base_tx(amount_usd=1500, velocity_24h=8, failed_logins_24h=6)
        assert score_transaction(tx) == 65  # 25 + 20 + 20 → high risk

    def test_prior_chargeback_account_with_international_large_amount(self):
        tx = base_tx(is_international=1, amount_usd=2000, prior_chargebacks=2)
        assert score_transaction(tx) == 60  # 15 + 25 + 20 → just at high threshold

    def test_worst_case_transaction_is_high_risk(self):
        tx = base_tx(
            device_risk_score=90,
            is_international=1,
            amount_usd=9999,
            velocity_24h=9,
            failed_logins_24h=7,
            prior_chargebacks=3,
        )
        assert label_risk(score_transaction(tx)) == "high"

    def test_best_case_transaction_is_low_risk(self):
        assert label_risk(score_transaction(base_tx())) == "low"
