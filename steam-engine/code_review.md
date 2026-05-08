# Steam Engine Simulation — Code & Physics Review

A walkthrough of `physics.py` and `steam_engine.py`, what they implement, how the physics is modelled, and the issues I found.

---

## 1. What the code does

The project is an interactive pygame simulation of a **double-acting reciprocating steam engine** with a closed steam loop:

```
  fire ──▶ boiler ──▶ cylinder (piston) ──▶ condenser
                          │                     │
                          └──── crank/flywheel ─┘  ▲
                                                   │
                              condensate pumped back ──┘
```

The user has two sliders — **heat input** (fire under the boiler, 0–60 kW) and **load** on the shaft — plus `SPACE` to nudge the flywheel. The window shows water level, fire, cylinder/piston/rod/crank/flywheel, condenser, gauges, and a phase indicator (heating / boiling / superheated).

### File split

| File | Role |
|------|------|
| `physics.py` | Pure simulation: thermodynamics, slider-crank kinematics, torque, integration. No pygame. Exposes `EnginePhysics` plus geometry constants used by the renderer. |
| `steam_engine.py` | Rendering, input, particles/drips. Owns an `EnginePhysics` and calls `update(dt)` each frame. |

This is a clean separation — the physics module is fully independent of the display layer.

### State held in `EnginePhysics`

- **Boiler:** `T_boiler` (°C), `water_kg`, `steam_kg`, `P_abs` (bar abs)
- **Condenser:** `cond_steam_kg`, `condensate_kg`, fixed `T_cond = 35 °C`
- **Mechanism:** `crank_angle`, `omega` (rad/s)
- **Controls:** `heat_input ∈ [0,1]`, `load ∈ [0,1]`
- **Diagnostics:** `torque_drive`, `torque_load_val`

Each frame, `update(dt)` calls three sub-updates in order: `_update_boiler`, `_update_condenser`, `_update_mechanics`.

---

## 2. Physics implementation, step by step

### 2.1 Saturation curve (Clausius–Clapeyron)

```python
def sat_pressure(T_c):
    T_K = T_c + 273.15
    return math.exp(L_R * (1/T_REF_K - 1/T_K))   # bar abs
```

This is the integrated Clausius–Clapeyron relation
$P(T) = P_{ref}\,\exp\!\left[\frac{L}{R}\left(\frac{1}{T_{ref}} - \frac{1}{T}\right)\right]$
with $L/R = L_{vap}/R_{specific} \approx 4891\;\text{K}$ (the constant `L_R = 4887` is correct to within rounding). `sat_temp` is the algebraic inverse. Both functions are clean.

### 2.2 Boiler — three-phase model

`_update_boiler` switches between phases based on water mass and temperature:

| Phase | Condition | Behaviour |
|-------|-----------|-----------|
| 1. Heating | `T < 99.9 °C` and `water_kg > 0` | Sensible heat: `ΔT = Q_net / (m·c_water)`. Headspace steam re-equilibrated to saturation. |
| 2. Boiling | `T ≥ 99.9` and `water_kg > 0.01` | Latent plateau: `dm = Q_net / L_vap` mass evaporates. Then `P = mRT/V`, `T = T_sat(P)`. |
| 3. Superheating | `water_kg ≤ 0.01` | Dry steam heats up: `ΔT = Q_net / (m·c_steam)`. Pressure follows ideal-gas at fixed boiler volume. |

Energy in: `Q_in = heat_input · 60 kW`. Loss to surroundings: `K·(T - T_amb)` with K = 0.15 kW/°C. Net Q drives the phase. Negative Q in Phase 2 condenses steam back to water, dropping P along the saturation curve until Phase 1 resumes — that's the recent "boiler not cooling below 100 °C" fix.

A simple condensate-return pump trickles `condensate_kg` back into `water_kg` at up to 0.5 kg/s, closing the mass loop.

### 2.3 Condenser

```python
T_steam  = max(self.T_boiler, self.T_cond + 1.0)
Q_reject = COND_K * (T_steam - self.T_cond) * dt
dm = Q_reject / L_VAP
```

Steam in the condenser shedding latent heat at rate `K·ΔT`, condensing into the `condensate_kg` pool. `COND_K = 3.0 kW/°C`. **(This is where the biggest physics bug lives — see §3.1.)**

### 2.4 Cylinder pressure (admission + adiabatic expansion)

```python
def cylinder_pressure(s, P_supply, P_exhaust):
    if s <= CUTOFF:           return P_supply
    v_cut = CLEARANCE + CUTOFF
    v_s   = CLEARANCE + s
    return max(P_exhaust, P_supply * (v_cut / v_s) ** GAMMA)
```

`s` is stroke progress (0 at TDC, 1 at BDC) for the active face. Three-stage idealization:

1. **Admission** (`0 ≤ s ≤ 0.40`): valve open, cylinder at `P_supply`.
2. **Cut-off + adiabatic expansion** (`s > 0.40`): valve shut, $PV^\gamma = $ const with $\gamma = 1.135$ (a wet-steam value, sensible).
3. **Floor at exhaust pressure** (clamping inside `max(...)`).

Volumes are normalised by displacement, so the dimensionless `CLEARANCE + s` works cleanly (constants cancel in the ratio).

Exhaust blow-down is treated as instantaneous at BDC/TDC. There is **no compression cushion** — at TDC the same face's pressure jumps from `P_cond` to `P_supply` discontinuously. That's a deliberate simplification (`# Exhaust blow-down happens at stroke reversal`).

### 2.5 Slider-crank kinematics

Exact (not the small-angle approximation):

$$\sin\varphi = \frac{R}{L}\sin\theta,\quad x_{piston} = R\cos\theta + L\cos\varphi$$

`piston_x()` and `_px_at()` use the geometry directly (intersection of the rod-length circle with the horizontal piston axis). Pixel and SI geometries share the same proportions via `M_PER_PX = R_m / R_px`.

### 2.6 Torque via virtual work

```python
self.torque_drive = -F_net * CRANK_R_M * math.sin(angle + phi) / cos_phi
```

Standard slider-crank result: the piston speed satisfies $v_{piston} = -\omega R \sin(\theta+\varphi)/\cos\varphi$, and power balance $F\cdot v = \tau\cdot\omega$ yields the formula above. Sign: at mid-forward stroke (θ = 3π/2, F > 0 rightward), this gives positive τ — engine accelerates. ✓

The **net force** is `(P_left − P_right) · 1e5 · A`. During the forward stroke the left face is driven, the right face exhausts; during the return stroke the assignments flip, with the right face's stroke parameter being `1 − s`. ✓

### 2.7 Load and integration

```python
load_ramp = min(1.0, omega / 2.0)
torque_load = (7.0 + 7.0*load) * omega + 150.0 * load * load_ramp
alpha = (torque_drive - torque_load) / I_FLYWHEEL
omega = clamp(omega + alpha*dt, 0, 45)
crank_angle = (crank_angle + omega*dt) % 2π
```

Phenomenological load (viscous + load-scaled term, ramped to avoid stiction issues at ω = 0). Forward Euler integration on `omega` and `angle`. Flywheel inertia `I = 12 kg·m²` smooths torque ripple.

### 2.8 Steam consumption

```python
dm_per_rad  = (DISPLACEMENT * CUTOFF * P_abs * 1e5) / (R_STEAM * T_K * π)
dm_consumed = 2.0 * dm_per_rad * omega * dt
```

The intent is to drain `steam_kg` (boiler) and refill `cond_steam_kg` (condenser) at the rate the cylinder admits new steam. **(This formula is wrong by a factor of 2 — see §3.2.)**

---

## 3. Issues found

### 3.1 🔴 Condenser uses `T_boiler` as the condensing-steam temperature

`physics.py:212`

```python
T_steam = max(self.T_boiler, self.T_cond + 1.0)
Q_reject = COND_K * (T_steam - self.T_cond) * dt
```

Steam arriving at the condenser has already expanded down to ~`P_cond` (≈ 0.06 bar in this model). Its saturation temperature at that pressure is ~36 °C, **not** the boiler temperature. Using `T_boiler` (which sits at 100–150 °C in normal operation) inflates the heat-rejection driving force by a factor of 5–10×, so the condenser empties `cond_steam_kg` far too aggressively. Knock-on effect: the simulation may show the condenser perpetually "dry" even when steam is being dumped into it.

**Fix:** drive the temperature difference from the condenser-side saturation temperature, not the boiler:

```python
T_steam = sat_temp(P_cond_abs)            # ≈ T_cond + a few °C
Q_reject = COND_K * (T_steam - self.T_cond) * dt
```

…where `P_cond_abs = min(sat_pressure(T_cond), P_ATM)` (you already compute this in `_update_mechanics`). To make it self-consistent you may want `COND_K` to be larger to compensate for the now-smaller ΔT.

### 3.2 🔴 Steam consumption is 2× too large

`physics.py:276–278`

The derivation:

- Per rotation, each face admits `DISPLACEMENT × CUTOFF` of steam at supply density.
- A double-acting engine has **two** admissions per rotation, total volume `2·DISPLACEMENT·CUTOFF`.
- Average mass-rate per radian of crank rotation = `2·DISPLACEMENT·CUTOFF·ρ / (2π)` = `DISPLACEMENT·CUTOFF·ρ / π`.

That is exactly what `dm_per_rad` already evaluates to — the factor of 2 for double-acting is already baked into the `π` in the denominator. The extra `2.0 *` in `dm_consumed = 2.0 * dm_per_rad * omega * dt` doubles the rate again.

Net effect: the boiler runs out about **twice as fast** as it should at any given RPM/pressure, and the condenser fills twice as fast.

**Fix:**

```python
dm_consumed = dm_per_rad * self.omega * dt
```

(Or, equivalently, replace `π` in the denominator with `2π` and keep the `2.0 *`.) The comment `×2 for double-acting` is correct in spirit but is being applied twice.

### 3.3 🟡 Phase 3 uses `c_p` (steam) instead of `c_v` for fixed-volume heating

`physics.py:193`

```python
C_eff = max(0.01, self.steam_kg * C_STEAM)   # C_STEAM = 2.01 kJ/(kg·K)
self.T_boiler = min(self.T_boiler + Q_net / C_eff, 300.0)
```

The boiler is a fixed-volume vessel, so heating dry steam should use $c_v = c_p - R_{specific} \approx 2.01 - 0.46 = 1.55$ kJ/(kg·K), not 2.01. The current code therefore underestimates the temperature rise per unit heat in the superheated regime by ~30%. Cosmetic for short bursts, more visible if the boiler is run dry for a while.

### 3.4 🟡 `sat_pressure` is missing the `P_atm` prefactor

`physics.py:62`

```python
return math.exp(L_R * (1.0 / T_REF_K - 1.0 / T_K))
```

Returns 1.000 bar at 100 °C, whereas the true saturation pressure at 100 °C is ~1.013 bar. Should be `P_ATM * exp(...)`. About a 1.3 % offset — tiny, but it does mean the model boils slightly below 100 °C at "1 atm" if you ever used `sat_temp(P_ATM)`.

### 3.5 🟡 Forward-Euler integration can be coarse at high ω

`physics.py:80, physics.py:271`

`steam_engine.py:80` caps `dt` at 0.05 s; `omega` is capped at 45 rad/s. In the worst case `omega·dt = 2.25 rad ≈ 130°` of crank rotation per step, which is far too coarse to integrate the rapidly varying drive torque accurately (admission / cutoff / exhaust transitions get skipped). At the typical 60 fps and moderate ω this is fine, but if frames stutter the simulated dynamics get noisy.

Possible fixes: sub-step the mechanics (e.g., split each frame into N integration sub-steps), or use a semi-implicit / RK2 scheme.

### 3.6 🟢 Minor: small mass-conservation slack from floor clamps

- `self.water_kg = max(0.0, ...)` (Phase 1)
- `self.steam_kg = max(0.001, ...)` (Phase 2 and tail of mechanics)
- `omega = max(0.0, ...)` and the `dm_consumed ≤ 0.3·steam_kg` cap

These all create or destroy fractions of a gram per frame in extreme conditions. Not user-visible, but worth knowing about if you ever plot total mass over time.

### 3.7 🟢 Minor: no compression cushion / re-compression of residual steam

Real reciprocating engines compress the trapped exhaust steam between exhaust-valve-close and TDC, providing a soft cushion and recovering a little energy. The current model has the cylinder pressure step instantly from `P_cond` to `P_supply` at TDC. This makes the indicator (P-V) diagram a rectangle-with-tail rather than the more realistic D-shape, but is a defensible simplification.

### 3.8 🟢 Minor: no condensation in the cylinder during expansion

Adiabatic expansion of saturated steam crosses into the wet-steam region — some droplets form, releasing latent heat and flattening the expansion curve. The choice `γ = 1.135` (vs. the dry-steam ideal-gas value of ~1.30) approximates this implicitly, which is a reasonable engineering trick.

---

## 4. Things that are done well

- **Clean physics/render split.** `physics.py` is pure simulation, easy to unit-test; the renderer never reaches inside it.
- **Exact slider-crank, not small-angle.** `piston_x()` solves the geometry properly; torque uses the rigorous virtual-work formula.
- **Three-phase boiler with correct Phase 1 ↔ Phase 2 reversibility.** Negative `Q_net` in Phase 2 condenses steam and slides back along the saturation curve — the recent fix is the right shape.
- **Closed mass loop** boiler → cylinder → condenser → pump → boiler, with mass tracked in each compartment.
- **Pixel ↔ SI geometry shared via a single scale factor** (`M_PER_PX`), so the on-screen mechanism is geometrically consistent with the physics.
- **`max(P_exhaust, ...)` floor** in `cylinder_pressure` is the right guard against the adiabatic curve dropping below back-pressure.
- **Calibrated load model** that gracefully handles ω = 0 (no false stiction). Comments document the calibration targets.

---

## 5. Suggested patch summary

Three lines would address the two important issues:

```diff
# physics.py — condenser
-        T_steam  = max(self.T_boiler, self.T_cond + 1.0)
+        P_cond_abs = min(sat_pressure(self.T_cond), P_ATM)
+        T_steam    = max(sat_temp(P_cond_abs), self.T_cond + 1.0)
         Q_reject = COND_K * (T_steam - self.T_cond) * dt

# physics.py — steam consumption
-        dm_consumed  = 2.0 * dm_per_rad * self.omega * dt
+        dm_consumed  = dm_per_rad * self.omega * dt
```

(After the consumption fix, you may want to roughly halve `Q_MAX_KW` or double `WATER_INIT` to keep the run-time-to-empty similar to what the simulation feels like today.)

Optional follow-ups: `c_p → c_v` in Phase 3, `P_ATM *` prefactor in `sat_pressure`, and a sub-stepped mechanics update for high-ω fidelity.
