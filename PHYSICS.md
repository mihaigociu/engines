# Steam Engine Simulation — Physics Review

A layer-by-layer walkthrough of the physics modelled in `steam_engine.py`, with notes on accuracy, simplifications, and known gaps.

---

## 1. Heat → Temperature (`update`, lines 75–78)

```python
self.temperature += self.heat_input * 120 * dt
self.temperature -= (self.temperature - 20) * 0.02 * dt
self.temperature = min(self.temperature, 180.0)
```

### Physics

Two competing differential terms:

- **Heating:** `dT/dt = Q_in / (m·c)` — heat power divided by thermal mass raises temperature. The constant `120` is a lumped proxy for `Q / (m·c)`.
- **Cooling:** Newton's Law of Cooling — `dT/dt = -k·(T − T_ambient)`. The constant `0.02` is the cooling rate; ambient is fixed at 20 °C.

### What is correct

The two-term balance (heating vs. ambient loss) is the right structure for a lumped thermal model.

### What is wrong / missing

The **latent heat of vaporisation** at 100 °C is completely absent. In reality, temperature *stays flat at 100 °C* while water converts to steam, because the energy goes into breaking molecular bonds rather than raising temperature. It takes 2260 kJ/kg before the temperature climbs again. The simulation blazes straight through this plateau.

This is also one of the most teachable moments in thermodynamics: students expect temperature to keep rising when you add heat, and the flat plateau is surprising and counterintuitive. Adding it would make the boiler gauge much more educational.

---

## 2. Steam Pressure (`update`, lines 80–84)

```python
excess = max(0.0, self.temperature - boiling)
target_pressure = excess * 0.12
self.pressure += (target_pressure - self.pressure) * 3 * dt
```

### Physics

Steam pressure only builds above the boiling point — correct. The relationship `P ∝ (T − 100)` is a linear approximation of the **saturation curve**, properly described by the Antoine equation or steam tables.

The line `pressure += (target − pressure) * 3 * dt` is a first-order lag (exponential approach to the target), modelling the finite time for pressure to equilibrate inside the boiler volume.

### How close is the linear approximation?

| Temperature | Real saturation pressure | Simulated pressure |
|---|---|---|
| 100 °C | 1.0 bar (abs) / 0 bar gauge | 0 bar |
| 120 °C | ~2.0 bar gauge | 2.4 bar |
| 150 °C | ~3.8 bar gauge | 6.0 bar |
| 180 °C | ~9.0 bar gauge | 9.6 bar |

Reasonable at low temperatures, diverges above 150 °C. For educational purposes the order of magnitude is right.

### What is wrong / missing

**Steam consumption is not modelled.** When the engine runs fast it uses steam quickly, which should lower boiler pressure. Pressure is currently driven only by temperature and is completely blind to engine speed. This breaks the feedback loop that a real boiler operator would manage: open throttle → pressure drops → add more fuel.

---

## 3. Slider-Crank Geometry (`crank_pin`, `piston_x`, lines 122–137)

```python
def crank_pin(self):
    x = CRANK_X + CRANK_R * math.cos(self.crank_angle)
    y = CRANK_Y + CRANK_R * math.sin(self.crank_angle)

def piston_x(self):
    dy = cpy - CRANK_Y
    leg = math.sqrt(ROD_LEN**2 - dy**2)
    px = cpx - leg
```

### Physics

This is geometrically exact. The derivation:

1. Crank pin traces a circle of radius `R` around the crankshaft centre.
2. The piston is constrained to move horizontally at `y = CRANK_Y`.
3. The connecting rod of length `L` rigidly links crank pin to piston pin.
4. Therefore: `px = cpx − sqrt(L² − dy²)`

### What is correct

The piston motion is **non-sinusoidal**, which is physically accurate. Because the connecting rod has finite length, the piston moves faster through the middle of the stroke than at the ends, and the power stroke is slightly quicker than the return stroke. This asymmetry is visible if you watch the piston closely: it lingers near BDC (far end) longer than near TDC (cylinder head end).

This part of the simulation is solid and needs no correction.

---

## 4. Drive Torque (`update`, line 87)

```python
torque_drive = self.pressure * 3000 * abs(math.sin(self.crank_angle))
```

### Physics

Torque = Force × moment arm.  
Force = pressure × piston area.  
Moment arm = `R · sin(θ)` (the component of the crank radius perpendicular to the connecting rod force).  
The constant `3000` is a lumped scalar combining piston area and unit conversions.

### What is wrong

**1. `abs(sin(θ))` applies steam on both strokes equally.**  
A *single-acting* engine (Newcomen, early Watt) only drives on one stroke; a *double-acting* engine (later Watt) drives on both strokes but with steam admitted from opposite sides of the piston. Neither matches what the code does. The current formula is best described as a phantom always-in-power-stroke engine.

**2. The connecting rod angle is ignored.**  
The exact torque formula for a slider-crank is:

```
T = F · R · (sin θ + (R/2L) · sin 2θ)
```

or equivalently via the rod angle φ where `sin φ = (R/L) · sin θ`:

```
T = F · R · sin(θ + φ) / cos φ
```

With `R/L = 80/180 ≈ 0.44`, the correction is not negligible: the torque peak shifts, and the power stroke and return stroke become asymmetric in a way the `sin θ` approximation does not capture.

**3. No valve cutoff.**  
Watt's great improvement over Newcomen was closing the steam inlet valve at 30–50% of the stroke and letting the steam **expand adiabatically** for the rest. This does more work per unit of steam and is the foundation of thermodynamic efficiency in steam engines. The simulation delivers full boiler pressure all the way to BDC, which is physically wrong and eliminates the most important efficiency lesson of the machine.

---

## 5. Load Torque (`update`, line 93)

```python
torque_load = (200 + self.load * 800) * self.omega + self.load * 1000
```

### Physics

Two physically distinct resistance terms:

- **`(200 + self.load * 800) · ω` — viscous drag**, proportional to speed. The `200` is always-on bearing and cylinder friction. `self.load * 800` is load-dependent speed-proportional resistance — the correct model for generators, centrifugal pumps, and fans, where resistance increases with shaft speed.
- **`self.load * 1000` — constant breakaway drag**, independent of speed. Correct model for positive-displacement pumps, lifting a weight, or static friction that must be overcome regardless of how fast the shaft turns.

### What is correct

The combined two-term model is how real industrial loads are characterised. It correctly produces the behaviour that a light load shifts the equilibrium RPM up, and a heavy load shifts it down or stalls the engine.

### What is missing

**Compression on the non-steam side of the piston.** On the return stroke the trapped exhaust steam (or air) in front of the piston is compressed back toward the inlet. This acts as a spring, returning some energy to the shaft and partially buffering the torque reversal. It is not modelled.

---

## 6. Rotational Dynamics (`update`, lines 95–100)

```python
alpha = (torque_drive - torque_load) / 8000
self.omega += alpha * dt
self.omega = max(0.0, min(self.omega, 40.0))
self.crank_angle += self.omega * dt
```

### Physics

Newton's 2nd law for rotation: `α = ΣT / I`.  
The `8000` is the effective moment of inertia, dominated by the flywheel mass.  
Integration uses the forward Euler method: `ω += α · dt`, then `θ += ω · dt`.

### What is correct

The structure is physically correct. The flywheel's role is accurately represented: high inertia smooths out the pulsed torque from the piston so the shaft turns at roughly constant speed between strokes.

### The hard RPM cap is a hack

The `min(self.omega, 40.0)` ceiling (~380 RPM) is not physical. In a real engine the speed limit emerges naturally from the load torque matching the drive torque at equilibrium. The cap exists because the baseline viscous term (`200`) is too small to produce equilibrium below 380 RPM at full boiler pressure — without the cap, the engine would reach ~1400 RPM at maximum heat and zero load. The correct fix is to increase the viscous coefficient, but doing so would noticeably slow down spin-up at low power and require re-tuning the whole torque balance.

### Euler integration error

The forward Euler method accumulates error proportional to `dt`. At 60 FPS, `dt ≈ 0.017 s`, which is fine for this simulation. If the timestep were variable or large, a Runge-Kutta integrator (RK4) would be more stable.

---

## Summary table

| Physics layer | Code location | Accuracy |
|---|---|---|
| Slider-crank geometry | `crank_pin`, `piston_x` (ll. 122–137) | **Exact** |
| Newton's 2nd law (rotation) | `update` ll. 95–100 | **Correct** (Euler integration) |
| Newton's Law of Cooling | `update` l. 77 | **Correct** |
| Pressure vs. temperature | `update` ll. 80–84 | Approximate, order-of-magnitude right |
| Load torque model | `update` l. 93 | Reasonable two-term model |
| Latent heat plateau at 100 °C | — | **Missing** |
| Steam consumption by engine | — | **Missing** |
| Valve timing / cutoff | — | **Missing** |
| Exact torque (connecting rod angle) | `update` l. 87 | Simplified |
| Single vs. double acting | `update` l. 87 | Simplified |
| Hard RPM ceiling | `update` l. 97 | Hack — should emerge from physics |
| Compression on return stroke | — | Missing |
