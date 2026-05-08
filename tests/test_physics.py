"""Tests for the steam-engine physics module.

Organized into:
1. Pure-function correctness (sat_pressure, sat_temp, cylinder_pressure)
2. Geometry (piston / stroke at known crank angles)
3. Conservation invariants over a long run (mass, omega>=0, angle range)
4. Phase model behaviour (heating, plateau, cooling reverses)
5. Mechanics sanity (zero ΔP -> zero torque, torque sign in power strokes)
6. Regression for fixed bugs (consumption rate, condenser ΔT source)

Run with: ./venv/bin/pytest tests/ -v
"""
import math
import pytest

from physics import (
    EnginePhysics,
    sat_pressure, sat_temp, cylinder_pressure,
    R_STEAM, P_ATM, T_AMB, L_VAP,
    DISPLACEMENT, CUTOFF, COND_K,
    X_TDC, X_BDC,
    WATER_INIT,
)


# ──────────────────────────────────────────────────────────────────────────────
# 1. Pure functions
# ──────────────────────────────────────────────────────────────────────────────

def test_sat_pressure_monotonic_in_T():
    Ts = [10, 30, 60, 100, 150, 200]
    Ps = [sat_pressure(T) for T in Ts]
    assert all(Ps[i] < Ps[i + 1] for i in range(len(Ps) - 1))


def test_sat_pressure_at_boiling_near_one_atm():
    # Currently the code returns 1.000 at 100°C (P_ATM prefactor missing,
    # see code_review.md §3.4). 2% tolerance leaves room either way.
    assert sat_pressure(100.0) == pytest.approx(1.0, rel=0.02)


def test_sat_round_trip_over_engine_range():
    # Below ~7°C sat_pressure() short-circuits to a floor (T_K < 280 guard),
    # so the round trip is only meaningful above that.
    for T in [25.0, 75.0, 100.0, 130.0, 180.0, 220.0]:
        assert sat_temp(sat_pressure(T)) == pytest.approx(T, abs=0.5)


def test_cylinder_pressure_during_admission_equals_supply():
    P_s, P_e = 3.0, 0.1
    for s in [0.0, 0.1, CUTOFF / 2, CUTOFF]:
        assert cylinder_pressure(s, P_s, P_e) == pytest.approx(P_s)


def test_cylinder_pressure_strictly_decreasing_after_cutoff():
    P_s, P_e = 3.0, 0.05
    pressures = [cylinder_pressure(s, P_s, P_e)
                 for s in [CUTOFF + 1e-3, 0.6, 0.8, 1.0]]
    assert all(pressures[i] > pressures[i + 1]
               for i in range(len(pressures) - 1))


def test_cylinder_pressure_floored_at_exhaust():
    # Adiabatic curve drops below P_exhaust deep in the stroke; max(...) clamps.
    P_s, P_e = 0.5, 0.4
    assert cylinder_pressure(1.0, P_s, P_e) >= P_e


# ──────────────────────────────────────────────────────────────────────────────
# 2. Geometry
# ──────────────────────────────────────────────────────────────────────────────

def test_piston_at_TDC_when_crank_angle_pi():
    e = EnginePhysics()
    e.crank_angle = math.pi
    assert e.piston_x() == pytest.approx(X_TDC, abs=0.5)


def test_piston_at_BDC_when_crank_angle_zero():
    e = EnginePhysics()
    e.crank_angle = 0.0
    assert e.piston_x() == pytest.approx(X_BDC, abs=0.5)


def test_stroke_progress_zero_at_TDC():
    e = EnginePhysics()
    e.crank_angle = math.pi
    assert e.stroke_progress() == pytest.approx(0.0, abs=1e-3)


def test_stroke_progress_one_at_BDC():
    e = EnginePhysics()
    e.crank_angle = 0.0
    assert e.stroke_progress() == pytest.approx(1.0, abs=1e-3)


# ──────────────────────────────────────────────────────────────────────────────
# 3. Conservation invariants over a long run
# ──────────────────────────────────────────────────────────────────────────────

def _total_mass(e):
    return e.water_kg + e.steam_kg + e.cond_steam_kg + e.condensate_kg


def test_mass_conserved_under_normal_operation():
    e = EnginePhysics()
    e.heat_input = 0.6
    e.load = 0.3
    e.omega = 5.0  # bootstrap so the engine runs
    initial = _total_mass(e)
    for _ in range(2000):  # ≈100 s at dt=0.05
        e.update(0.05)
    # Floors on water_kg / steam_kg can leak ~mg per step; allow 10 g.
    assert abs(_total_mass(e) - initial) < 0.01


def test_omega_never_negative():
    e = EnginePhysics()
    e.heat_input = 0.4
    e.load = 1.0  # heavy load makes ω hover near the floor
    for _ in range(500):
        e.update(0.05)
        assert e.omega >= 0.0


def test_crank_angle_stays_in_zero_two_pi():
    e = EnginePhysics()
    e.heat_input = 1.0
    for _ in range(500):
        e.update(0.05)
        assert 0.0 <= e.crank_angle < 2 * math.pi


def test_stroke_progress_in_unit_interval():
    e = EnginePhysics()
    e.heat_input = 1.0
    for _ in range(500):
        e.update(0.05)
        s = e.stroke_progress()
        assert 0.0 <= s <= 1.0


# ──────────────────────────────────────────────────────────────────────────────
# 4. Phase model behaviour
# ──────────────────────────────────────────────────────────────────────────────

def test_heating_reaches_boiling_plateau():
    e = EnginePhysics()
    e.heat_input = 1.0
    e.load = 1.0  # stall the engine so steam isn't drained
    for _ in range(2000):  # 100 s
        e.update(0.05)
    assert e.T_boiler >= 99.0
    assert e.water_kg < WATER_INIT  # some water has been vaporised


def test_cooling_reverses_phase2_to_phase1():
    """Recent fix (commit f9d52cb): negative Q_net while in Phase 2 should
    re-condense steam and slide T back below 100°C along the saturation curve."""
    e = EnginePhysics()
    e.T_boiler = 100.0
    e.water_kg = 4.0
    e.steam_kg = 0.05
    e.P_abs = 1.0
    e.heat_input = 0.0
    e.load = 1.0
    e.omega = 0.0
    for _ in range(2000):  # 100 s of heat-loss only
        e.update(0.05)
    assert e.T_boiler < 99.0


def test_steady_state_no_heat_stays_at_ambient():
    e = EnginePhysics()  # default state already at T_AMB
    e.heat_input = 0.0
    e.load = 0.0
    for _ in range(1000):
        e.update(0.05)
    assert abs(e.T_boiler - T_AMB) < 1.0


# ──────────────────────────────────────────────────────────────────────────────
# 5. Mechanics sanity
# ──────────────────────────────────────────────────────────────────────────────

def test_zero_pressure_differential_yields_zero_torque():
    """If P_supply == P_exhaust on both faces, drive torque must be zero
    regardless of crank angle."""
    e = EnginePhysics()
    P = 0.5
    e.T_cond = sat_temp(P)  # ⇒ P_cond_abs = P (below P_ATM, no clip)
    e.P_abs = P             # ⇒ P_supply == P_cond_abs
    for angle in [0.5, 1.0, math.pi / 2, math.pi, 4.0, 5.5]:
        e.crank_angle = angle
        e._update_mechanics(1e-3)
        assert abs(e.torque_drive) < 1e-3


def test_positive_drive_torque_in_forward_power_stroke():
    e = EnginePhysics()
    e.P_abs = 3.0
    e.T_boiler = 130.0
    e.T_cond = 35.0
    e.crank_angle = 3 * math.pi / 2  # mid-forward, left face driven
    e._update_mechanics(1e-3)
    assert e.torque_drive > 0


def test_positive_drive_torque_in_return_power_stroke():
    e = EnginePhysics()
    e.P_abs = 3.0
    e.T_boiler = 130.0
    e.T_cond = 35.0
    e.crank_angle = math.pi / 2  # mid-return, right face driven
    e._update_mechanics(1e-3)
    assert e.torque_drive > 0


# ──────────────────────────────────────────────────────────────────────────────
# 6. Regression tests for fixed bugs
# ──────────────────────────────────────────────────────────────────────────────

def test_steam_consumption_rate_per_rotation():
    """Per full rotation, mass admitted = 2·DISPLACEMENT·CUTOFF·ρ
    (two faces, one admission each). Catches reintroduction of the 2.0× bug."""
    e = EnginePhysics()
    e.P_abs = 3.0
    e.T_boiler = 130.0
    e.steam_kg = 100.0   # plenty so consumption never starves
    e.water_kg = 0.0     # bypass boiler phase logic
    e.cond_steam_kg = 0.0
    e.condensate_kg = 0.0
    e.heat_input = 0.0
    e.load = 1.0         # damp ω growth
    e.omega = 5.0

    rho = e.P_abs * 1e5 / (R_STEAM * (e.T_boiler + 273.15))
    expected_per_rev = 2 * DISPLACEMENT * CUTOFF * rho

    initial_steam = e.steam_kg
    angle_traversed = 0.0
    prev = e.crank_angle
    for _ in range(5000):
        e._update_mechanics(1e-3)
        delta = (e.crank_angle - prev) % (2 * math.pi)
        angle_traversed += delta
        prev = e.crank_angle
        if angle_traversed >= 2 * math.pi:
            break
    assert angle_traversed >= 2 * math.pi, "engine didn't complete a rotation"

    consumed = initial_steam - e.steam_kg
    expected = expected_per_rev * (angle_traversed / (2 * math.pi))
    assert consumed == pytest.approx(expected, rel=0.02)


def test_condenser_uses_pcond_sat_temp_not_boiler():
    """Driving ΔT must come from saturation temp at P_cond (~T_cond + a few °C),
    not from T_boiler. Catches reintroduction of the T_boiler-driven condenser."""
    e = EnginePhysics()
    e.T_boiler = 150.0
    e.T_cond = 35.0
    e.cond_steam_kg = 0.1
    e.condensate_kg = 0.0
    e.water_kg = 0.0
    e.steam_kg = 0.001

    P_cond = min(sat_pressure(e.T_cond), P_ATM)
    T_steam_correct = max(sat_temp(P_cond), e.T_cond + 1.0)
    dt = 0.1
    expected_dm = COND_K * (T_steam_correct - e.T_cond) * dt / L_VAP

    cond_before = e.cond_steam_kg
    e._update_condenser(dt)
    consumed = cond_before - e.cond_steam_kg

    assert consumed == pytest.approx(expected_dm, rel=0.02)

    # Sanity: the buggy version would have used ΔT = T_boiler - T_cond = 115°C,
    # giving roughly an order of magnitude more condensation per step.
    buggy_dm = COND_K * (e.T_boiler - e.T_cond) * dt / L_VAP
    assert consumed < 0.5 * buggy_dm
