# Steam Engine Quiz

> A self-check covering the physics in `steam_engine_physics.md` and the simulation in `physics.py` / `steam_engine.py`. Try to answer each question before peeking at the answer key at the bottom.

Each question is tagged:
- **[P]** = pure physics (concepts, formulas, derivations)
- **[C]** = code (how the simulation models the physics)
- **[B]** = bridge (connects a physics idea to a specific code construct)

Difficulty: ★ easy · ★★ medium · ★★★ hard.

---

## Section 1 — Work, Heat, and the First Law

### Q1 [P] ★
Starting from `dW = F · dx`, derive the expression `dW = P · dV` for a piston of area `A` pushed by gas at pressure `P`. State each substitution.

### Q2 [P] ★
The first law is `ΔU = Q − W` (with `W` = work done *by* the system). For a complete cycle, why does `Q_net = W_net`?

### Q3 [P] ★★
A gas expands isothermally from `V₁` to `V₂` at temperature `T`. Show that the work done is `W = nRT · ln(V₂/V₁)`. Why does heat input *equal* work output for this process?

### Q4 [P] ★★
Why is adiabatic expansion always cooler at the same final volume than isothermal expansion from the same starting point?

---

## Section 2 — Ideal Gas, Phase Transitions, and Steam

### Q5 [P] ★
Vaporizing 1 kg of water at 100 °C takes ~2257 kJ. Heating that same kilogram from 20 °C to 100 °C takes ~336 kJ. Why does the steam engine specifically benefit from this asymmetry?

### Q6 [P] ★★
Inside the wet-steam dome, what is the relationship between pressure and temperature? Why does this mimic an isothermal process even though heat is being absorbed?

### Q7 [P] ★★★
The doc gives `γ ≈ 1.33` for steam (vs `1.4` for air). What does `γ = C_p/C_v` represent physically, and why is it lower for steam?

---

## Section 3 — Carnot, Entropy, and Efficiency

### Q8 [P] ★
A boiler at 200 °C feeds a condenser at 30 °C. What is the Carnot efficiency? (Show your work in Kelvin.)

### Q9 [P] ★★
The Second Law says `ΔS_universe ≥ 0`. Use this inequality applied to two reservoirs (`T_H`, `T_C`) to derive `η ≤ 1 − T_C/T_H`.

### Q10 [P] ★★
On a T–S diagram, the area enclosed by a cycle equals what physical quantity? On a P–V diagram?

---

## Section 4 — Rankine Cycle

### Q11 [P] ★
List the four processes of the ideal Rankine cycle and the device responsible for each.

### Q12 [P] ★★
Why does the Rankine cycle compress *liquid* (in the pump) instead of compressing the gaseous working fluid? Give both an energetic argument and a practical one.

### Q13 [P] ★★
Given the worked example in the doc (`P_H = 3 MPa`, `P_C = 10 kPa`, saturated vapor entry), the cycle reaches ~32% efficiency vs ~37% Carnot. What is the structural reason a real Rankine cycle falls short of Carnot, even when ideal (no friction)?

---

## Section 5 — Code: Boiler Model (`physics.py`)

### Q14 [C] ★
The boiler in `_update_boiler` has three branches. What conditions trigger each, and what does each branch model physically?

### Q15 [B] ★★
The `sat_pressure(T_c)` function uses the formula:

```python
return math.exp(L_R * (1.0 / T_REF_K - 1.0 / T_K))
```

Which physical equation is this implementing? What is `L_R` (look at the constant — `L_R = 4887.0`)?

### Q16 [C] ★★
In phase 2 (the latent-heat plateau), the code does:

```python
dm = Q_net / L_VAP
self.water_kg -= dm
self.steam_kg = max(0.001, self.steam_kg + dm)
```

Why is `dm` proportional to `Q_net / L_VAP` rather than to a temperature change? What physical process is happening?

### Q17 [B] ★★★
After updating `steam_kg` in phase 2, the code recomputes pressure with `P_abs = (self.steam_kg * R_STEAM * T_K) / (BOILER_VOL * 1e5)` and *then* updates `T_boiler = sat_temp(self.P_abs)`. Why does the temperature follow the pressure (not the other way around) inside the dome?

---

## Section 6 — Code: Cylinder & Mechanics

### Q18 [C] ★
What is the role of the `CUTOFF` constant (= 0.40)? In `cylinder_pressure(s, P_supply, P_exhaust)`, what happens at `s = 0.40` exactly, and why?

### Q19 [B] ★★
After cutoff, the code computes pressure as:

```python
P_supply * (v_cut / v_s) ** GAMMA
```

Which thermodynamic process does this encode? Why is `GAMMA` (not `1`) in the exponent?

### Q20 [C] ★★
Why is `CLEARANCE = 0.06` *added* to both `s` values when computing volume ratios in `cylinder_pressure`? What physical part of a real engine does it represent?

### Q21 [C] ★★
The simulation is *double-acting*. In `_update_mechanics`, there are two pressure variables `P_left` and `P_right`. Trace the logic: during the forward stroke (`π < angle ≤ 2π`), which face receives steam and which is exhausting? What about the return stroke?

### Q22 [B] ★★★
The torque is computed as:

```python
self.torque_drive = -F_net * CRANK_R_M * math.sin(angle + phi) / cos_phi
```

This is the exact slider-crank relation, not the simplified `T = F · R · sin(θ)`. What does the `+ φ` term and the `cos(φ)` denominator account for? What approximation are you making if you drop them?

### Q23 [C] ★★
Steam consumption per timestep is computed as:

```python
dm_per_rad = (DISPLACEMENT * CUTOFF * self.P_abs * 1e5) / (R_STEAM * T_K * math.pi)
dm_consumed = 2.0 * dm_per_rad * self.omega * dt
```

Where does the factor of `2.0` come from? Why does `CUTOFF` appear (rather than the full stroke)?

---

## Section 7 — Putting Physics & Code Together

### Q24 [B] ★★
The doc says the Rankine cycle is "compress as liquid, expand as gas — that's the genius." Where in `physics.py` do you see this asymmetry expressed? (Hint: compare what's modelled in `_update_boiler`'s condensate-return block vs. what's modelled in `cylinder_pressure`.)

### Q25 [B] ★★★
A user pushes the heat slider to maximum. Predict (using both the physics and the code) the *sequence* of events: what happens to `T_boiler`, `P_abs`, `water_kg`, `steam_kg`, RPM, and eventually phase? Where in the code does each transition fire?

### Q26 [P + B] ★★★
The simulation never explicitly enforces the Second Law — there is no entropy variable. Yet the code still respects it implicitly. Identify *two* places in `physics.py` where the Second Law is "baked in" through the model structure (e.g. one-way energy flow, irreversibility built into a calculation).

---

## Answer Key

<details>
<summary>Click to reveal answers</summary>

### A1
- `dW = F · dx` (definition of work)
- `F = P · A` (pressure is force/area, so force on the piston face is `P · A`)
- `A · dx = dV` (the piston sweeps out a thin slab of volume as it moves `dx`)
- Combining: `dW = P · A · dx = P · dV`.

### A2
A complete cycle returns to its starting state, so `ΔU = 0`. The first law then gives `0 = Q_net − W_net`, hence `Q_net = W_net`. All net heat absorbed becomes net work.

### A3
For an ideal gas at constant `T`: `P = nRT/V`. So `W = ∫(V₁→V₂) P dV = nRT ∫ dV/V = nRT ln(V₂/V₁)`. Heat equals work because `ΔU = nC_v ΔT = 0` (constant `T`), so by the first law `Q = W`.

### A4
In adiabatic expansion no heat enters, so the work done by the gas comes directly out of internal energy `U`. Since `U ∝ T` for an ideal gas, the gas cools. Isothermal expansion is propped up by heat input from a reservoir, so `T` (and hence `P` at the same `V`) stays higher. On a P–V diagram, the adiabat is steeper than the isotherm.

### A5
The phase transition lets water *absorb* huge amounts of heat at constant temperature in the boiler and *release* huge amounts at constant temperature in the condenser. These near-isothermal heat exchanges at the hot and cold ends are exactly what an ideal Carnot-like cycle wants. The 7× energy multiplier means tiny mass flows carry enormous energy, which is why steam is mechanically practical.

### A6
Inside the wet-steam dome, pressure and temperature are *not independent* — they are locked together by the saturation curve `P_sat(T)`. Adding heat at fixed pressure converts liquid to vapor at constant `T` (isobaric *and* isothermal simultaneously), which is exactly what an ideal heat-engine cycle wants on its hot leg.

### A7
`γ = C_p/C_v` is the ratio of heat capacities at constant pressure vs constant volume — equivalently, how steeply `P` falls during adiabatic expansion. It depends on molecular degrees of freedom: more "ways to store energy" (vibrations, rotations) → higher `C_v` → lower `γ`. Water (H₂O) is a triatomic, bent molecule with rotational and vibrational modes, while air is mostly diatomic — so steam has more internal modes and `γ ≈ 1.33` rather than `1.4`.

### A8
`T_H = 473 K`, `T_C = 303 K`. `η_Carnot = 1 − 303/473 = 1 − 0.640 = 0.360 = 36.0%`.

### A9
Hot reservoir loses entropy `Q_H/T_H`; cold reservoir gains `Q_C/T_C`. Net entropy change ≥ 0:
- `Q_C/T_C − Q_H/T_H ≥ 0`
- → `Q_C/Q_H ≥ T_C/T_H`
- → `η = 1 − Q_C/Q_H ≤ 1 − T_C/T_H`.

### A10
- T–S diagram: enclosed area = net heat absorbed (= net work, by the first law).
- P–V diagram: enclosed area = net work done by the system per cycle.

### A11
1. Pump — isentropic compression of liquid (1→2)
2. Boiler — isobaric heat addition, water → steam (2→3)
3. Turbine — isentropic expansion of steam, work output (3→4)
4. Condenser — isobaric heat rejection, steam → liquid (4→1)

### A12
- **Energetic:** liquids are nearly incompressible, so the work to raise pressure (`w = v · ΔP`) is tiny because specific volume `v` is small. Compressing a gas to the same pressure ratio costs orders of magnitude more work.
- **Practical:** liquid pumps are simple, robust, and small. A gas compressor doing the same job would be a major energy parasite — wiping out most of the turbine's output.

### A13
The Rankine cycle's heat addition includes a sensible-heating leg (warming compressed liquid up to saturation), which happens at a *range* of temperatures below `T_H`. Carnot requires *all* heat to be added at exactly `T_H`. Lowering the average temperature of heat addition lowers efficiency. Superheating helps but doesn't eliminate this; reheat and regeneration partially compensate.

### A14
- Phase 1 (`T_boiler < 99.9` and `water_kg > 0`): sensible heating of liquid water — temperature rises proportional to `Q_net / (m · C_water)`.
- Phase 2 (`water_kg > 0.01`): latent-heat plateau — at boiling, `T` stays put while heat converts water to steam (or back).
- Phase 3 (otherwise — boiler ran dry): superheated steam — only steam left, so heat raises its temperature according to `C_steam`.

### A15
This is the **Clausius–Clapeyron equation**, integrated under the assumption that latent heat is roughly constant over the temperature range. `L_R = L_v / R_specific` — the latent heat of vaporization divided by the specific gas constant for water vapor — gives the equation in dimensionless temperature form.

### A16
This is the latent-heat phase change: in the wet-steam region, every joule of heat added (`Q_net`) goes into breaking molecular bonds (turning liquid into vapor) rather than into temperature. The mass converted is `dm = Q_net / L_VAP` because `L_VAP` is the energy per kg required for the phase change. Conversely, when `Q_net` is negative, steam condenses back to water.

### A17
Inside the dome, `P` and `T` are not independent — they're tied by the saturation curve. The code's logic: more steam mass in fixed boiler volume → higher `P` (ideal-gas relation `PV = mR_specific T`); but `T` must satisfy the saturation condition `T = T_sat(P)`. So the *steam mass* is the truly independent state variable, pressure is computed from it, and temperature is then read off the saturation curve.

### A18
`CUTOFF` is the *cutoff fraction* — the point during the stroke where the inlet (admission) valve closes. Before cutoff (`s ≤ 0.40`), the cylinder is connected to the boiler and pressure equals `P_supply`. After cutoff, the trapped steam expands adiabatically. Cutoff is a key design parameter for efficiency: short cutoff → more expansion, more efficient but lower power; long cutoff → more power but wastes steam.

### A19
This is **adiabatic expansion**: `P · V^γ = constant`. The exponent `γ` (rather than 1) reflects that the temperature drops during expansion — a cooler gas at larger volume has lower pressure than the isothermal case (`P · V = const`). Since the steam is suddenly cut off from the boiler, no heat is added during expansion, so `γ` (not 1) is correct.

### A20
**Clearance volume** — the dead space at the end of the cylinder where the piston cannot reach (housing the valves and ports). Even at "TDC" the cylinder isn't empty. So real volumes are `V = (CLEARANCE + s) · displacement`. Without it, `s = 0` would mean zero volume, which would give infinite pressure ratios — physically unreal.

### A21
- **Forward stroke** (`π < angle ≤ 2π`, piston moving right): left face is connected to boiler steam (admission, then expansion); right face is exhausting to the condenser. So `P_left = cylinder_pressure(s, P_supply, P_exhaust)` and `P_right = P_cond_abs`.
- **Return stroke** (`0 < angle ≤ π`, piston moving left): roles flip. Right face now receives steam (with its own stroke progress `1 − s`); left face exhausts. This is what makes the engine "double-acting" — power is produced on every stroke, not just every other.

### A22
The slider-crank mechanism converts the piston's linear force into shaft torque, but the connecting rod is at angle `φ` to the cylinder axis (not parallel). The force along the rod is `F_net / cos(φ)`, and only the component perpendicular to the crank arm produces torque — that's the `sin(angle + φ)` factor.

The simplified `T = F · R · sin(θ)` assumes an *infinitely long* rod (so `φ ≈ 0`). With a real-length rod, the simplified form errs by a few percent and produces an asymmetric (non-sinusoidal) torque curve in reality — exactly what the slider-crank correction captures.

### A23
- **Factor of 2.0**: double-acting — steam fills the active cylinder face *twice* per crank revolution (once on each side).
- **`CUTOFF`**: only the volume admitted *before* the inlet valve closes counts as "consumed" steam (drawn from the boiler at supply pressure). After cutoff, the trapped steam just expands; no new mass is drawn. So total mass per radian is proportional to `displacement × CUTOFF` (the volume admitted), times the steam density `P/(R·T)`.

### A24
- **Liquid compression** (cheap): the condensate-return block in `_update_boiler` is essentially free — `flow = min(self.condensate_kg, 0.5 * dt)` just moves liquid mass back without consuming any meaningful energy.
- **Gas expansion** (productive): `cylinder_pressure` models steam expanding adiabatically against the piston, doing work that becomes torque on the crank. The pressure-volume curve in the cylinder is what produces the entire mechanical output.

### A25
1. `heat_input → 1.0`, so `Q_in = 60 kW`. Phase 1 fires: water temp climbs (~`Q_net / (5 kg · 4.186 kJ/kg·K)` ≈ a few °C/sec).
2. When `T_boiler` hits 99.9 °C, code transitions to phase 2 (latent-heat plateau).
3. In phase 2, water mass falls (`dm = Q_net / L_VAP`), steam mass grows, pressure rises along the saturation curve, temperature follows pressure.
4. With more steam mass and pressure, `cylinder_pressure` returns higher values → bigger `F_net` → bigger torque → higher RPM (load permitting).
5. Eventually `water_kg < 0.01` → phase 3 (superheated): all liquid gone, remaining steam heats further beyond saturation; temperature can climb past the boiling point of the current pressure.
6. Each phase transition is a different `if`/`elif` branch in `_update_boiler` — explicit conditions on `T_boiler` and `water_kg`.

### A26
Two examples (any two are acceptable):
- **One-way condenser flow**: `_update_condenser` only moves steam → condensate (`dm` is non-negative, clamped via `max(0.0, …)`), never the reverse. Cold water doesn't spontaneously become hot vapor.
- **Adiabatic expansion floor**: `cylinder_pressure` clamps the post-cutoff pressure with `max(P_exhaust, …)`. Steam can do work on the piston by expanding, but it can't drop below the exhaust pressure and re-absorb work — the exhaust valve enforces irreversibility.
- **Heat-loss term**: `Q_loss = K_HEAT_LOSS * (T_boiler - T_AMB)` is always positive (when boiler hotter than ambient). Heat leaks downhill, never the reverse.
- **Condenser heat rejection**: `Q_reject = COND_K * (T_steam − T_cond) * dt` flows from hot steam to cold water, never reversed.

</details>

---

*Got a question wrong? Read the relevant section of `steam_engine_physics.md` and find the corresponding code in `physics.py`. Re-running the simulation while watching gauges is also a great way to build intuition.*
