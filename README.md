# engines

A collection of small, self-contained simulations of mechanical engines — built to learn the underlying physics by modelling it.

## Projects

| Folder | What it is |
|--------|------------|
| [`steam-engine/`](steam-engine/) | Interactive pygame simulation of a double-acting reciprocating steam engine: boiler, cylinder with cutoff and adiabatic expansion, slider-crank, flywheel, condenser, and a closed steam loop. |

More engines may land here over time (internal combustion, Stirling, etc.).

## Setup

```bash
python3 -m venv venv
./venv/bin/pip install pygame pytest
```

The `venv/` lives at the repo root and is shared across projects.

## Running the steam-engine simulation

```bash
./venv/bin/python steam-engine/steam_engine.py
```

Controls: heat-input and load sliders in the side panel; `SPACE` nudges the flywheel; `ESC` quits.

## Running tests

```bash
./venv/bin/pytest steam-engine/tests/ -v
```

## Inside `steam-engine/`

- `physics.py` — pure simulation: thermodynamics, slider-crank kinematics, torque, integration. No pygame.
- `steam_engine.py` — rendering, input, particles. Owns an `EnginePhysics` and calls `update(dt)` each frame.
- `steam_engine_physics.md` — deep-dive on the physics (work/heat, ideal gas, Carnot, Rankine, phase transitions).
- `steam_engine_quiz.md` — self-check quiz spanning the physics doc and the code.
- `tests/` — pytest suite covering pure functions, geometry, conservation invariants, phase model, mechanics, and bug regressions.
