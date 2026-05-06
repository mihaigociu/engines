import math

# ── Physical constants (SI) ───────────────────────────────────────────────────
L_VAP       = 2257.0    # kJ/kg   latent heat of vaporisation
C_WATER     = 4.186     # kJ/(kg·K)
C_STEAM     = 2.01      # kJ/(kg·K)
R_STEAM     = 461.5     # J/(kg·K)  specific gas constant for H₂O
L_R         = 4887.0    # L/R_specific  (Clausius–Clapeyron coefficient)
T_REF_K     = 373.15    # K  (100 °C reference boiling point)
T_AMB       = 20.0      # °C ambient
GAMMA       = 1.135     # adiabatic index for steam
P_ATM       = 1.013     # bar absolute

# ── Boiler & condenser parameters ────────────────────────────────────────────
BOILER_VOL  = 0.08      # m³  steam-space volume inside boiler
WATER_INIT  = 5.0       # kg  initial liquid water
Q_MAX_KW    = 60.0      # kW  heat input at slider = 1
K_HEAT_LOSS = 0.15      # kW/°C heat loss to surroundings
COND_TEMP   = 35.0      # °C  condenser cooling-water temperature
COND_K      = 3.0       # kW/°C condenser heat-transfer coefficient

# ── Engine geometry — pixel coords (shared with drawing layer) ────────────────
CRANK_X     = 560
CRANK_Y     = 260
CRANK_R     = 80        # px  crank throw
ROD_LEN     = 180       # px  connecting rod

# ── Engine geometry — physical (SI), same proportions as pixels ──────────────
CRANK_R_M   = 0.12      # m
ROD_LEN_M   = 0.27      # m
BORE_R_M    = 0.08      # m   piston bore radius
PISTON_AREA = math.pi * BORE_R_M ** 2   # m²  ≈ 0.0201 m²

CLEARANCE   = 0.06      # clearance vol / displacement vol
CUTOFF      = 0.40      # inlet valve closes at this fraction of stroke
# Exhaust blow-down happens at stroke reversal (BDC/TDC), not mid-stroke.

I_FLYWHEEL  = 12.0      # kg·m²  effective moment of inertia

# ── Precomputed geometry (module-level) ───────────────────────────────────────
def _px_at(angle: float) -> float:
    cpx = CRANK_X + CRANK_R * math.cos(angle)
    cpy = CRANK_Y + CRANK_R * math.sin(angle)
    dy  = cpy - CRANK_Y
    return cpx - math.sqrt(max(0.0, ROD_LEN ** 2 - dy ** 2))

X_TDC     = _px_at(math.pi)   # piston leftmost  (TDC, closest to cylinder head)
X_BDC     = _px_at(0.0)       # piston rightmost (BDC)
STROKE_PX = X_BDC - X_TDC
M_PER_PX  = CRANK_R_M / CRANK_R
STROKE_M  = STROKE_PX * M_PER_PX
DISPLACEMENT = PISTON_AREA * STROKE_M   # m³  swept volume one side


# ── Thermodynamic helpers ─────────────────────────────────────────────────────

def sat_pressure(T_c: float) -> float:
    """Saturation pressure in bar absolute — Clausius–Clapeyron."""
    T_K = T_c + 273.15
    if T_K < 280:
        return 0.008
    return math.exp(L_R * (1.0 / T_REF_K - 1.0 / T_K))


def sat_temp(P_abs: float) -> float:
    """Saturation temperature in °C (inverse Clausius–Clapeyron)."""
    if P_abs <= 0.01:
        return -30.0
    T_K = L_R / (L_R / T_REF_K - math.log(max(P_abs, 0.001)))
    return T_K - 273.15


def cylinder_pressure(s: float, P_supply: float, P_exhaust: float) -> float:
    """
    Pressure on one piston face given stroke progress s (0 = TDC, 1 = BDC).
    Phases: steam admission → adiabatic expansion to BDC.
    Exhaust blow-down is instantaneous at stroke reversal (BDC/TDC).
    """
    if s <= CUTOFF:
        return P_supply
    v_cut = CLEARANCE + CUTOFF
    v_s   = CLEARANCE + s
    return max(P_exhaust, P_supply * (v_cut / v_s) ** GAMMA)


# ── Main physics class ────────────────────────────────────────────────────────

class EnginePhysics:
    def __init__(self):
        # Boiler
        self.T_boiler       = T_AMB
        self.water_kg       = WATER_INIT
        self.steam_kg       = self._sat_steam_kg(T_AMB)
        self.P_abs          = sat_pressure(T_AMB)

        # Condenser
        self.cond_steam_kg  = 0.0   # steam currently in condenser loop
        self.condensate_kg  = 0.0   # liquid ready to pump back to boiler
        self.T_cond         = COND_TEMP

        # Crank / shaft
        # Start 45° into the forward (power) stroke, in full steam admission zone
        self.crank_angle    = 5 * math.pi / 4
        self.omega          = 0.0   # rad/s

        # User controls  (0–1)
        self.heat_input     = 0.0
        self.load           = 0.2

        # Diagnostics for display
        self.torque_drive   = 0.0
        self.torque_load_val = 0.0

    # ── Properties ────────────────────────────────────────────────────────────

    @property
    def pressure_gauge(self) -> float:
        return max(0.0, self.P_abs - P_ATM)

    @property
    def rpm(self) -> float:
        return self.omega * 60.0 / (2 * math.pi)

    @property
    def water_fraction(self) -> float:
        return self.water_kg / WATER_INIT

    # ── Geometry ──────────────────────────────────────────────────────────────

    def crank_pin(self):
        return (
            CRANK_X + CRANK_R * math.cos(self.crank_angle),
            CRANK_Y + CRANK_R * math.sin(self.crank_angle),
        )

    def piston_x(self) -> float:
        cpx, cpy = self.crank_pin()
        dy  = cpy - CRANK_Y
        leg = math.sqrt(max(0.0, ROD_LEN ** 2 - dy ** 2))
        return cpx - leg

    def stroke_progress(self) -> float:
        """0 at TDC, 1 at BDC for the left (steam-inlet) face."""
        return max(0.0, min(1.0, (self.piston_x() - X_TDC) / STROKE_PX))

    # ── Top-level update ──────────────────────────────────────────────────────

    def update(self, dt: float):
        self._update_boiler(dt)
        self._update_condenser(dt)
        self._update_mechanics(dt)

    # ── Boiler ────────────────────────────────────────────────────────────────

    def _sat_steam_kg(self, T_c: float) -> float:
        """Mass of steam (kg) that fills BOILER_VOL at saturation pressure for T_c."""
        P_sat = sat_pressure(T_c)
        T_K   = T_c + 273.15
        return (P_sat * 1e5 * BOILER_VOL) / (R_STEAM * T_K)

    def _update_boiler(self, dt: float):
        Q_in   = self.heat_input * Q_MAX_KW
        Q_loss = K_HEAT_LOSS * (self.T_boiler - T_AMB)
        Q_net  = (Q_in - Q_loss) * dt          # kJ this timestep

        if self.T_boiler < 99.9 and self.water_kg > 0:
            # ── Phase 1: sensible heating ──────────────────────────────────
            C_eff = max(0.01, self.water_kg * C_WATER)
            self.T_boiler = min(self.T_boiler + Q_net / C_eff, 99.9)
            # Steam mass tracks saturation equilibrium (tiny, water does not
            # noticeably decrease)
            new_steam = self._sat_steam_kg(self.T_boiler)
            delta = new_steam - self.steam_kg
            self.water_kg = max(0.0, self.water_kg - delta)
            self.steam_kg = new_steam
            self.P_abs    = sat_pressure(self.T_boiler)

        elif self.water_kg > 0.01:
            # ── Phase 2: latent-heat plateau ──────────────────────────────
            # Positive Q_net evaporates water; negative Q_net condenses steam
            # back to water, dropping pressure and temperature along the
            # saturation curve until T falls below 99.9°C → Phase 1.
            dm = Q_net / L_VAP
            dm = max(-self.steam_kg * 0.5, min(dm, self.water_kg))
            self.water_kg -= dm
            self.steam_kg = max(0.001, self.steam_kg + dm)
            T_K = self.T_boiler + 273.15
            self.P_abs = (self.steam_kg * R_STEAM * T_K) / (BOILER_VOL * 1e5)
            self.T_boiler = sat_temp(self.P_abs)

        else:
            # ── Phase 3: superheated steam (boiler has run dry) ───────────
            C_eff = max(0.01, self.steam_kg * C_STEAM)
            self.T_boiler = min(self.T_boiler + Q_net / C_eff, 300.0)
            T_K = self.T_boiler + 273.15
            self.P_abs = (self.steam_kg * R_STEAM * T_K) / (BOILER_VOL * 1e5)

        self.P_abs = max(P_ATM * 0.1, self.P_abs)

        # Condensate return: pump liquid back from condenser to boiler
        if self.condensate_kg > 0:
            flow = min(self.condensate_kg, 0.5 * dt)
            self.water_kg      += flow
            self.condensate_kg -= flow

    # ── Condenser ─────────────────────────────────────────────────────────────

    def _update_condenser(self, dt: float):
        """Cool exhaust steam back to liquid water."""
        if self.cond_steam_kg <= 0.0:
            return
        T_steam  = max(self.T_boiler, self.T_cond + 1.0)
        Q_reject = COND_K * (T_steam - self.T_cond) * dt   # kJ
        dm = max(0.0, min(Q_reject / L_VAP, self.cond_steam_kg))
        self.cond_steam_kg -= dm
        self.condensate_kg += dm

    # ── Mechanics ─────────────────────────────────────────────────────────────

    def _update_mechanics(self, dt: float):
        angle = self.crank_angle
        s     = self.stroke_progress()   # 0=TDC, 1=BDC for left face

        # Connecting rod angle φ  (exact slider-crank)
        sin_phi = max(-0.9999, min(0.9999,
                      (CRANK_R_M / ROD_LEN_M) * math.sin(angle)))
        phi     = math.asin(sin_phi)
        cos_phi = math.cos(phi)

        # Condenser (exhaust) pressure
        P_cond_abs = min(sat_pressure(self.T_cond), P_ATM)

        # Double-acting cylinder pressures
        # Forward stroke  (π < angle ≤ 2π): piston moves right toward BDC
        #   Left face  → steam from boiler (s: 0→1)
        #   Right face → exhausting to condenser
        # Return stroke (0 < angle ≤ π): piston moves left toward TDC
        #   Left face  → exhausting to condenser
        #   Right face → steam from boiler  (1-s: 0→1)
        forward = (math.pi < angle <= 2 * math.pi)

        if forward:
            P_left  = cylinder_pressure(s,       self.P_abs, P_cond_abs)
            P_right = P_cond_abs
        else:
            P_left  = P_cond_abs
            P_right = cylinder_pressure(1.0 - s, self.P_abs, P_cond_abs)

        # Net force on piston (positive = rightward)
        F_net = (P_left - P_right) * 1e5 * PISTON_AREA   # N

        # Exact slider-crank torque via virtual work:
        #   T = -F · R · sin(θ + φ) / cos(φ)
        if abs(cos_phi) > 1e-6:
            self.torque_drive = -F_net * CRANK_R_M * math.sin(angle + phi) / cos_phi
        else:
            self.torque_drive = 0.0

        # Load torque.
        # Speed-proportional drag (viscous + load-scaled resistance).
        # Constant work term ramps with speed: at omega=0 no shaft rotation
        # means no work against external load (no static stiction modelled).
        # Calibrated so at P_abs≈2 bar (avg drive ≈ 220 Nm):
        #   load=0.0 → ~286 RPM,  load=0.5 → ~115 RPM,  load=1.0 → ~48 RPM
        load_ramp = min(1.0, self.omega / 2.0)
        self.torque_load_val = (7.0 + 7.0 * self.load) * self.omega \
                               + 150.0 * self.load * load_ramp

        alpha      = (self.torque_drive - self.torque_load_val) / I_FLYWHEEL
        self.omega = max(0.0, min(self.omega + alpha * dt, 45.0))
        self.crank_angle = (self.crank_angle + self.omega * dt) % (2 * math.pi)

        # Steam consumption: each radian sweeps DISPLACEMENT·CUTOFF of steam
        # from the active face; ×2 for double-acting.
        T_K = self.T_boiler + 273.15
        dm_per_rad   = (DISPLACEMENT * CUTOFF * self.P_abs * 1e5) \
                       / (R_STEAM * T_K * math.pi)
        dm_consumed  = 2.0 * dm_per_rad * self.omega * dt
        dm_consumed  = max(0.0, min(dm_consumed, self.steam_kg * 0.3))

        self.steam_kg      -= dm_consumed
        self.cond_steam_kg += dm_consumed
        self.steam_kg       = max(0.001, self.steam_kg)
