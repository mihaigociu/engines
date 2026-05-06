import pygame
import math
import sys
import random

from physics import (
    EnginePhysics,
    CRANK_X, CRANK_Y, CRANK_R, ROD_LEN,
    X_TDC, X_BDC, STROKE_PX,
    CUTOFF,
    WATER_INIT, P_ATM,
)

# ── Window ────────────────────────────────────────────────────────────────────
WIDTH, HEIGHT = 1200, 720
FPS = 60

# ── Colours ───────────────────────────────────────────────────────────────────
BG           = (30,  30,  40)
BOILER_COL   = (160,  80,  30)
WATER_COL    = (50,  120, 200)
STEAM_COL    = (200, 210, 220)
FIRE_COL     = [(255, 200, 0), (255, 140, 0), (220, 60, 0)]
PISTON_COL   = (180, 180, 190)
ROD_COL      = (140, 140, 150)
CRANK_COL    = (200, 160,  60)
WHEEL_COL    = (100, 160, 100)
GAUGE_BG     = (50,   50,  60)
GAUGE_FG     = (220, 220, 100)
TEXT_COL     = (230, 230, 230)
SLIDER_BG    = (70,   70,  80)
COND_COLD    = (80,  140, 200)
COND_HOT     = (180, 210, 230)
PIPE_COL     = (160, 160, 170)

# ── Layout constants (visual only) ────────────────────────────────────────────
CYL_LEFT     = int(X_TDC) - 30   # aligns with piston at TDC (pin=300, body=286–314)
CYL_TOP      = 200
CYL_HEIGHT   = 80
CYL_WIDTH    = int(STROKE_PX) + 60  # 270→490: contains piston body at BDC (446–474)
PISTON_W     = 28
WHEEL_R      = 110

BOILER_RECT  = pygame.Rect(60, 460, 300, 110)

# Condenser to the right of the cylinder (cylinder ends at ~490)
COND_RECT    = pygame.Rect(520, 400, 55, 170)
COND_COILS   = 6   # number of visual coil passes


class SteamEngine:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("Watt's Workshop – Steam Engine Simulator")
        self.clock  = pygame.time.Clock()
        self.font_sm = pygame.font.SysFont("Arial", 13)
        self.font_md = pygame.font.SysFont("Arial", 17, bold=True)
        self.font_lg = pygame.font.SysFont("Arial", 23, bold=True)

        self.engine = EnginePhysics()

        # Steam-puff particles
        self.particles: list[dict] = []
        self.fire_phase = 0.0

        # Condensate drip animation
        self.drips: list[dict] = []
        self.drip_timer = 0.0

        # Slider rects
        self.sl_heat = pygame.Rect(870, 170, 220, 14)
        self.sl_load = pygame.Rect(870, 235, 220, 14)
        self.dragging = None

    # ── Main loop ─────────────────────────────────────────────────────────────

    def run(self):
        while True:
            dt = min(self.clock.tick(FPS) / 1000.0, 0.05)
            self._handle_events()
            self._update(dt)
            self._draw()

    # ── Input ─────────────────────────────────────────────────────────────────

    def _handle_events(self):
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                pygame.quit(); sys.exit()
            if ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_ESCAPE:
                    pygame.quit(); sys.exit()
                if ev.key == pygame.K_SPACE:
                    self.engine.omega += 1.5

            if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                mx, my = ev.pos
                if self.sl_heat.inflate(0, 22).collidepoint(mx, my):
                    self.dragging = "heat"
                elif self.sl_load.inflate(0, 22).collidepoint(mx, my):
                    self.dragging = "load"

            if ev.type == pygame.MOUSEBUTTONUP:
                self.dragging = None

            if ev.type == pygame.MOUSEMOTION and self.dragging:
                mx = ev.pos[0]
                if self.dragging == "heat":
                    self.engine.heat_input = max(0.0, min(1.0,
                        (mx - self.sl_heat.left) / self.sl_heat.width))
                else:
                    self.engine.load = max(0.0, min(1.0,
                        (mx - self.sl_load.left) / self.sl_load.width))

    # ── Simulation update ─────────────────────────────────────────────────────

    def _update(self, dt: float):
        self.engine.update(dt)
        self.fire_phase += dt * 8

        # Steam puffs from exhaust pipe (above condenser)
        if self.engine.cond_steam_kg > 0.02 and len(self.particles) < 50:
            ex, ey = COND_RECT.centerx, COND_RECT.top - 5
            self.particles.append({
                "x": ex + random.uniform(-6, 6),
                "y": float(ey),
                "vx": random.uniform(-12, 12),
                "vy": random.uniform(-40, -70),
                "life": 1.0,
                "r": random.randint(3, 7),
            })

        for p in self.particles:
            p["x"] += p["vx"] * dt
            p["y"] += p["vy"] * dt
            p["vy"] += 8 * dt
            p["life"] -= dt * 1.0
        self.particles = [p for p in self.particles if p["life"] > 0]

        # Condensate drips at the bottom of the condenser
        self.drip_timer += dt
        drip_rate = self.engine.condensate_kg * 2.0 + 0.1
        if self.drip_timer > 1.0 / max(drip_rate, 0.1) and self.engine.condensate_kg > 0:
            self.drip_timer = 0.0
            self.drips.append({
                "x": float(COND_RECT.centerx),
                "y": float(COND_RECT.bottom),
                "vy": 40.0,
                "life": 1.0,
            })

        for d in self.drips:
            d["y"] += d["vy"] * dt
            d["vy"] += 60 * dt
            d["life"] -= dt * 1.8
        self.drips = [d for d in self.drips if d["life"] > 0]

    # ── Drawing ───────────────────────────────────────────────────────────────

    def _draw(self):
        self.screen.fill(BG)
        self._draw_labels()
        self._draw_pipes()
        self._draw_boiler()
        self._draw_condenser()
        self._draw_cylinder()
        self._draw_crank_assembly()
        self._draw_flywheel()
        self._draw_particles()
        self._draw_drips()
        self._draw_gauges()
        self._draw_sliders()
        pygame.display.flip()

    def _draw_labels(self):
        t = self.font_lg.render(
            "Watt's Workshop  —  Steam Engine Simulator", True, (200, 200, 220))
        self.screen.blit(t, (20, 12))
        h = self.font_sm.render(
            "SPACE = nudge flywheel    ESC = quit", True, (120, 120, 140))
        self.screen.blit(h, (20, 42))

    # ── Pipes connecting everything ───────────────────────────────────────────

    def _draw_pipes(self):
        # Steam pipe: boiler top → cylinder left (up then across)
        bx = BOILER_RECT.left + 60
        by = BOILER_RECT.top
        cx, cy = CYL_LEFT, CYL_TOP + CYL_HEIGHT // 2
        pygame.draw.lines(self.screen, PIPE_COL, False,
                          [(bx, by), (bx, CYL_TOP - 30),
                           (CYL_LEFT - 10, CYL_TOP - 30), (cx, cy)], 6)

        # Exhaust pipe: cylinder right → condenser top (right then straight down)
        ex = CYL_LEFT + CYL_WIDTH
        ey = CYL_TOP + CYL_HEIGHT // 2
        pygame.draw.lines(self.screen, (130, 130, 140), False,
                          [(ex, ey), (COND_RECT.centerx, ey),
                           (COND_RECT.centerx, COND_RECT.top)], 5)

        # Condensate return: condenser bottom → boiler (down then across)
        pygame.draw.lines(self.screen, WATER_COL, False,
                          [(COND_RECT.centerx, COND_RECT.bottom),
                           (COND_RECT.centerx, BOILER_RECT.top + 40),
                           (BOILER_RECT.right - 20, BOILER_RECT.top + 40)], 3)

    # ── Boiler ────────────────────────────────────────────────────────────────

    def _draw_boiler(self):
        eng = self.engine
        pygame.draw.rect(self.screen, BOILER_COL, BOILER_RECT, border_radius=10)
        pygame.draw.rect(self.screen, (100, 50, 15), BOILER_RECT, 3, border_radius=10)

        # Water level (fraction of remaining water)
        frac = eng.water_fraction
        wh   = int((BOILER_RECT.height - 8) * min(frac, 1.0))
        if wh > 0:
            wr = pygame.Rect(BOILER_RECT.left + 4,
                             BOILER_RECT.bottom - 4 - wh,
                             BOILER_RECT.width - 8, wh)
            pygame.draw.rect(self.screen, WATER_COL, wr, border_radius=6)

        # Phase label inside boiler
        if eng.T_boiler < 99.5:
            phase = f"Heating  {eng.T_boiler:.0f}°C"
        elif eng.water_fraction > 0.02:
            phase = f"Boiling  {eng.T_boiler:.0f}°C"
        else:
            phase = f"Superheated  {eng.T_boiler:.0f}°C"
        lbl = self.font_sm.render(phase, True, TEXT_COL)
        self.screen.blit(lbl, (BOILER_RECT.left + 6, BOILER_RECT.top + 6))

        # Water level text
        wlbl = self.font_sm.render(
            f"Water: {eng.water_kg:.1f} kg", True, TEXT_COL)
        self.screen.blit(wlbl, (BOILER_RECT.left + 6, BOILER_RECT.top + 22))

        self._draw_fire()

    def _draw_fire(self):
        if self.engine.heat_input < 0.01:
            return
        base_y = BOILER_RECT.bottom + 4
        for i in range(12):
            fx      = BOILER_RECT.left + 18 + i * 23
            flicker = math.sin(self.fire_phase + i * 1.3) * 0.5 + 0.5
            fh      = int((16 + flicker * 18) * self.engine.heat_input)
            col     = FIRE_COL[i % 3]
            pygame.draw.polygon(self.screen, col, [
                (fx, base_y),
                (fx - 7, base_y + fh),
                (fx + 7, base_y + fh),
            ])

    # ── Condenser ─────────────────────────────────────────────────────────────

    def _draw_condenser(self):
        eng = self.engine
        # Background housing
        pygame.draw.rect(self.screen, (40, 60, 90), COND_RECT, border_radius=8)
        pygame.draw.rect(self.screen, (80, 110, 150), COND_RECT, 2, border_radius=8)

        # Fill level representing steam+condensate in condenser
        total = eng.cond_steam_kg + eng.condensate_kg
        max_vis = 0.003
        fill_frac = min(1.0, total / max_vis)
        if fill_frac > 0:
            fh = int((COND_RECT.height - 6) * fill_frac)
            fr = pygame.Rect(COND_RECT.left + 3,
                             COND_RECT.bottom - 3 - fh,
                             COND_RECT.width - 6, fh)
            # Colour blends hot steam (top) → cold condensate (bottom)
            steam_frac = eng.cond_steam_kg / max(total, 0.001)
            col = tuple(int(COND_COLD[i] + (COND_HOT[i] - COND_COLD[i]) * steam_frac)
                        for i in range(3))
            pygame.draw.rect(self.screen, col, fr, border_radius=5)

        # Coil lines (decorative but shows it's a heat exchanger)
        for i in range(COND_COILS):
            cy = COND_RECT.top + 12 + i * (COND_RECT.height - 20) // COND_COILS
            pygame.draw.line(self.screen, (60, 90, 130),
                             (COND_RECT.left + 4, cy),
                             (COND_RECT.right - 4, cy), 2)

        # Label
        lbl = self.font_sm.render("Condenser", True, (150, 180, 220))
        self.screen.blit(lbl, (COND_RECT.left - 5, COND_RECT.top - 16))
        t_lbl = self.font_sm.render(f"{eng.T_cond:.0f}°C", True, (150, 180, 220))
        self.screen.blit(t_lbl, (COND_RECT.left + 4, COND_RECT.bottom + 4))

    # ── Cylinder ──────────────────────────────────────────────────────────────

    def _draw_cylinder(self):
        eng = self.engine
        px  = eng.piston_x()
        s   = eng.stroke_progress()

        cyl_rect = pygame.Rect(CYL_LEFT, CYL_TOP, CYL_WIDTH, CYL_HEIGHT)
        pygame.draw.rect(self.screen, (70, 70, 80), cyl_rect)
        pygame.draw.rect(self.screen, (150, 150, 160), cyl_rect, 3)

        # Annotate valve states
        if s <= CUTOFF:
            vstatus = "ADMIT"
            vcol    = (80, 220, 80)
        else:
            vstatus = "EXPAND"
            vcol    = (220, 200, 60)
        vl = self.font_sm.render(vstatus, True, vcol)
        self.screen.blit(vl, (CYL_LEFT + 4, CYL_TOP - 18))

        # Steam fill on active face — bounded by piston faces, not piston centre
        forward = (math.pi < eng.crank_angle <= 2 * math.pi)
        if forward and eng.pressure_gauge > 0.05:
            # Left face: cylinder left wall → piston left face
            steam_x = CYL_LEFT + 3
            steam_w = (int(px) - PISTON_W // 2) - steam_x
            if steam_w > 2:
                alpha_val = int(min(200, eng.pressure_gauge * 40))
                ss = pygame.Surface((steam_w, CYL_HEIGHT - 6), pygame.SRCALPHA)
                ss.fill((*STEAM_COL, alpha_val))
                self.screen.blit(ss, (steam_x, CYL_TOP + 3))
        elif not forward and eng.pressure_gauge > 0.05:
            # Right face: piston right face → cylinder right wall
            steam_x = int(px) + PISTON_W // 2
            steam_w = (CYL_LEFT + CYL_WIDTH - 3) - steam_x
            if steam_w > 2:
                alpha_val = int(min(200, eng.pressure_gauge * 40))
                ss = pygame.Surface((steam_w, CYL_HEIGHT - 6), pygame.SRCALPHA)
                ss.fill((*STEAM_COL, alpha_val))
                self.screen.blit(ss, (steam_x, CYL_TOP + 3))

        # Piston
        pr = pygame.Rect(int(px) - PISTON_W // 2, CYL_TOP + 2,
                         PISTON_W, CYL_HEIGHT - 4)
        pygame.draw.rect(self.screen, PISTON_COL, pr, border_radius=4)
        pygame.draw.rect(self.screen, (220, 220, 240), pr, 2, border_radius=4)

        # Connecting rod
        cpx, cpy = eng.crank_pin()
        rod_start = (int(px) + PISTON_W // 2, CYL_TOP + CYL_HEIGHT // 2)
        pygame.draw.line(self.screen, ROD_COL, rod_start,
                         (int(cpx), int(cpy)), 6)
        pygame.draw.circle(self.screen, CRANK_COL, rod_start, 6)
        pygame.draw.circle(self.screen, CRANK_COL, (int(cpx), int(cpy)), 8)

    # ── Crank ─────────────────────────────────────────────────────────────────

    def _draw_crank_assembly(self):
        cpx, cpy = self.engine.crank_pin()
        pygame.draw.line(self.screen, CRANK_COL,
                         (CRANK_X, CRANK_Y), (int(cpx), int(cpy)), 10)
        pygame.draw.circle(self.screen, (200, 200, 210), (CRANK_X, CRANK_Y), 14)
        pygame.draw.circle(self.screen, (100, 100, 110), (CRANK_X, CRANK_Y), 14, 2)

    # ── Flywheel ──────────────────────────────────────────────────────────────

    def _draw_flywheel(self):
        wx, wy = CRANK_X + 30, CRANK_Y
        a0 = self.engine.crank_angle
        for i in range(8):
            a  = a0 + i * math.pi / 4
            sx = wx + int(WHEEL_R * 0.85 * math.cos(a))
            sy = wy + int(WHEEL_R * 0.85 * math.sin(a))
            pygame.draw.line(self.screen, (80, 130, 80), (wx, wy), (sx, sy), 4)
        pygame.draw.circle(self.screen, WHEEL_COL, (wx, wy), WHEEL_R, 8)
        pygame.draw.circle(self.screen, (150, 200, 150), (wx, wy), 18)
        pygame.draw.circle(self.screen, (60, 100, 60), (wx, wy), 18, 3)
        rpm_lbl = self.font_sm.render(f"{self.engine.rpm:.0f} RPM", True, TEXT_COL)
        self.screen.blit(rpm_lbl, (wx - 28, wy + WHEEL_R + 10))

    # ── Particles & drips ────────────────────────────────────────────────────

    def _draw_particles(self):
        for p in self.particles:
            alpha = int(p["life"] * 160)
            surf  = pygame.Surface((p["r"] * 2, p["r"] * 2), pygame.SRCALPHA)
            pygame.draw.circle(surf, (*STEAM_COL, alpha), (p["r"], p["r"]), p["r"])
            self.screen.blit(surf, (int(p["x"]) - p["r"], int(p["y"]) - p["r"]))

    def _draw_drips(self):
        for d in self.drips:
            alpha = int(d["life"] * 200)
            surf  = pygame.Surface((6, 6), pygame.SRCALPHA)
            pygame.draw.circle(surf, (*WATER_COL, alpha), (3, 3), 3)
            self.screen.blit(surf, (int(d["x"]) - 3, int(d["y"]) - 3))

    # ── Gauges ────────────────────────────────────────────────────────────────

    def _draw_gauge(self, cx, cy, radius, value, max_val, label, unit, col):
        pygame.draw.circle(self.screen, GAUGE_BG, (cx, cy), radius)
        pygame.draw.circle(self.screen, (100, 100, 110), (cx, cy), radius, 2)
        for i in range(11):
            a  = math.radians(210 - i * 24)
            r0, r1 = radius - 10, radius - 4
            pygame.draw.line(self.screen, (180, 180, 180),
                             (cx + int(r0 * math.cos(a)), cy - int(r0 * math.sin(a))),
                             (cx + int(r1 * math.cos(a)), cy - int(r1 * math.sin(a))), 1)
        frac     = min(1.0, value / max_val)
        needle_a = math.radians(210 - frac * 240)
        nx = cx + int((radius - 12) * math.cos(needle_a))
        ny = cy - int((radius - 12) * math.sin(needle_a))
        pygame.draw.line(self.screen, col, (cx, cy), (nx, ny), 3)
        pygame.draw.circle(self.screen, col, (cx, cy), 5)
        ll = self.font_sm.render(label, True, TEXT_COL)
        self.screen.blit(ll, (cx - ll.get_width() // 2, cy + radius // 2 - 2))
        vl = self.font_md.render(f"{value:.1f} {unit}", True, GAUGE_FG)
        self.screen.blit(vl, (cx - vl.get_width() // 2, cy - 10))

    def _draw_gauges(self):
        eng = self.engine
        self._draw_gauge(920, 460, 55, eng.pressure_gauge, 2.0,
                         "Pressure", "bar", (220, 120,  80))
        self._draw_gauge(1040, 460, 55, eng.T_boiler, 200.0,
                         "Temp", "°C", (200, 180,  80))
        self._draw_gauge(920, 570, 45, eng.rpm, 350.0,
                         "Speed", "RPM", (100, 200, 140))
        self._draw_gauge(1040, 570, 45, eng.water_fraction * 100, 100.0,
                         "Water", "%", (80, 140, 220))

    # ── Sliders ───────────────────────────────────────────────────────────────

    def _draw_sliders(self):
        panel = pygame.Rect(850, 110, 320, 220)
        pygame.draw.rect(self.screen, (42, 42, 52), panel, border_radius=8)
        pygame.draw.rect(self.screen, (85, 85, 98), panel, 1, border_radius=8)
        title = self.font_md.render("Controls", True, TEXT_COL)
        self.screen.blit(title, (panel.left + 10, panel.top + 10))

        # Phase indicator
        eng = self.engine
        if eng.T_boiler < 99.5:
            phase_text = "Phase 1 — Heating water"
            phase_col  = (150, 180, 220)
        elif eng.water_fraction > 0.02:
            phase_text = "Phase 2 — Latent heat (boiling)"
            phase_col  = (220, 200,  80)
        else:
            phase_text = "Phase 3 — Superheated steam"
            phase_col  = (220, 130,  80)
        pl = self.font_sm.render(phase_text, True, phase_col)
        self.screen.blit(pl, (panel.left + 10, panel.top + 32))

        self._draw_one_slider(self.sl_heat, eng.heat_input,
                              "Heat Input", FIRE_COL[0])
        self._draw_one_slider(self.sl_load, eng.load,
                              "Load", (120, 160, 220))

        # Torque readout
        tq = self.font_sm.render(
            f"Drive: {eng.torque_drive:+.0f} N·m   Load: {eng.torque_load_val:.0f} N·m",
            True, (160, 160, 180))
        self.screen.blit(tq, (panel.left + 10, panel.bottom - 22))

    def _draw_one_slider(self, rect, value, label, colour):
        lbl = self.font_sm.render(f"{label}:  {int(value * 100)}%", True, TEXT_COL)
        self.screen.blit(lbl, (rect.left, rect.top - 17))
        pygame.draw.rect(self.screen, SLIDER_BG, rect, border_radius=7)
        fw = int(rect.width * value)
        if fw > 0:
            fr = pygame.Rect(rect.left, rect.top, fw, rect.height)
            pygame.draw.rect(self.screen, colour, fr, border_radius=7)
        pygame.draw.rect(self.screen, (140, 140, 150), rect, 1, border_radius=7)
        tx = rect.left + int(rect.width * value)
        pygame.draw.circle(self.screen, (220, 220, 230), (tx, rect.centery), 9)


if __name__ == "__main__":
    SteamEngine().run()
