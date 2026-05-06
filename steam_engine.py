import pygame
import math
import sys

# ── Window / layout ──────────────────────────────────────────────────────────
WIDTH, HEIGHT = 1100, 700
FPS = 60

# Colours
BG          = (30,  30,  40)
BOILER_COL  = (160,  80,  30)
WATER_COL   = (50,  120, 200)
STEAM_COL   = (200, 210, 220)
FIRE_COL    = [(255,200,0),(255,140,0),(220,60,0)]
PISTON_COL  = (180, 180, 190)
ROD_COL     = (140, 140, 150)
CRANK_COL   = (200, 160,  60)
WHEEL_COL   = (100, 160, 100)
GAUGE_BG    = (50,   50,  60)
GAUGE_FG    = (220, 220, 100)
TEXT_COL    = (230, 230, 230)
SLIDER_BG   = (70,   70,  80)
SLIDER_FG   = (100, 200, 120)

# ── Engine geometry (pixels) ─────────────────────────────────────────────────
CYL_LEFT    = 120          # left edge of cylinder bore
CYL_TOP     = 180
CYL_WIDTH   = 260          # stroke range + piston thickness
CYL_HEIGHT  = 80
PISTON_W    = 28
CRANK_X     = 560          # crankshaft centre x
CRANK_Y     = 260          # crankshaft centre y
CRANK_R     = 80           # crank throw (half stroke)
ROD_LEN     = 180          # connecting rod length
WHEEL_R     = 110          # flywheel radius

# Boiler sits below the cylinder area
BOILER_RECT = pygame.Rect(60, 440, 300, 120)


class SteamEngine:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("Watt's Workshop – Steam Engine Simulator")
        self.clock = pygame.time.Clock()
        self.font_sm = pygame.font.SysFont("Arial", 14)
        self.font_md = pygame.font.SysFont("Arial", 18, bold=True)
        self.font_lg = pygame.font.SysFont("Arial", 24, bold=True)

        # Physics state
        self.crank_angle  = math.pi / 4   # start off dead-centre so there's immediate torque
        self.omega        = 0.0      # angular velocity rad/s
        self.temperature  = 20.0     # boiler water °C
        self.pressure     = 0.0      # bar (gauge)

        # Controls  (0–1 normalised)
        self.heat_input   = 0.0
        self.load         = 0.2

        # Dragging state for sliders
        self.dragging = None

        # Particle system for steam puffs
        self.particles: list[dict] = []
        self.fire_phase = 0.0

        # Label positions for sliders
        self.slider_heat_rect  = pygame.Rect(780, 160, 200, 14)
        self.slider_load_rect  = pygame.Rect(780, 220, 200, 14)

    # ── Physics update ────────────────────────────────────────────────────────
    def update(self, dt: float):
        # Temperature rises with heat, falls with ambient losses
        boiling = 100.0
        self.temperature += self.heat_input * 120 * dt
        self.temperature -= (self.temperature - 20) * 0.02 * dt
        self.temperature = min(self.temperature, 180.0)

        # Gauge pressure (bar): only above boiling point
        excess = max(0.0, self.temperature - boiling)
        target_pressure = excess * 0.12
        self.pressure += (target_pressure - self.pressure) * 3 * dt
        self.pressure = max(0.0, self.pressure)

        # Torque from steam pressure on piston face
        torque_drive = self.pressure * 3000 * abs(math.sin(self.crank_angle))

        # Load torque has two parts:
        #   - speed-proportional drag (viscous + generator-style resistance that scales with load)
        #   - constant breakaway drag (static friction / pump head)
        # Both scale with the load slider so the effect is clearly visible at any RPM.
        torque_load = (200 + self.load * 800) * self.omega + self.load * 1000

        alpha = (torque_drive - torque_load) / 8000          # higher inertia = slower spin-up
        self.omega += alpha * dt
        self.omega = max(0.0, min(self.omega, 40.0))          # ~380 RPM ceiling, realistic for a Watt engine

        self.crank_angle += self.omega * dt
        self.crank_angle %= (2 * math.pi)

        # Steam particles when pressure is up and engine running
        self.fire_phase += dt * 8
        if self.pressure > 0.3 and len(self.particles) < 60:
            import random
            self.particles.append({
                "x": BOILER_RECT.right - 20 + random.uniform(-5, 5),
                "y": float(BOILER_RECT.top),
                "vx": random.uniform(-8, 8),
                "vy": random.uniform(-30, -60),
                "life": 1.0,
                "r": random.randint(3, 7),
            })
        for p in self.particles:
            p["x"] += p["vx"] * dt
            p["y"] += p["vy"] * dt
            p["vy"] += 10 * dt   # slight buoyancy still rises, slow
            p["life"] -= dt * 1.2
        self.particles = [p for p in self.particles if p["life"] > 0]

    # ── Geometry helpers ──────────────────────────────────────────────────────
    def crank_pin(self):
        x = CRANK_X + CRANK_R * math.cos(self.crank_angle)
        y = CRANK_Y + CRANK_R * math.sin(self.crank_angle)
        return x, y

    def piston_x(self):
        cpx, cpy = self.crank_pin()
        # Piston constrained to horizontal axis at CRANK_Y
        dx = cpx - CRANK_X
        dy = cpy - CRANK_Y
        # Distance from crank pin to piston pin along rod
        # piston pin at (px, CRANK_Y), |pin - crank_pin| = ROD_LEN
        # px - cpx = sqrt(ROD_LEN² - dy²)  (piston to left of crank)
        leg = math.sqrt(max(0.0, ROD_LEN**2 - dy**2))
        px = cpx - leg
        return px

    # ── Drawing ───────────────────────────────────────────────────────────────
    def draw(self):
        self.screen.fill(BG)
        self._draw_labels()
        self._draw_boiler()
        self._draw_cylinder()
        self._draw_crank_assembly()
        self._draw_flywheel()
        self._draw_steam_pipe()
        self._draw_particles()
        self._draw_gauges()
        self._draw_sliders()
        pygame.display.flip()

    def _draw_boiler(self):
        # Body
        pygame.draw.rect(self.screen, BOILER_COL, BOILER_RECT, border_radius=12)
        pygame.draw.rect(self.screen, (100, 50, 15), BOILER_RECT, 3, border_radius=12)
        # Water level
        water_h = int(BOILER_RECT.height * 0.55 * min(1.0, self.temperature / 160))
        water_rect = pygame.Rect(
            BOILER_RECT.left + 4,
            BOILER_RECT.bottom - 4 - water_h,
            BOILER_RECT.width - 8,
            water_h,
        )
        if water_h > 0:
            pygame.draw.rect(self.screen, WATER_COL, water_rect, border_radius=6)
        # Fire grate below boiler
        self._draw_fire()
        # Label
        lbl = self.font_sm.render(f"Boiler  {self.temperature:.0f}°C", True, TEXT_COL)
        self.screen.blit(lbl, (BOILER_RECT.left + 8, BOILER_RECT.top + 6))

    def _draw_fire(self):
        if self.heat_input < 0.01:
            return
        import random
        base_y = BOILER_RECT.bottom + 4
        for i in range(12):
            fx = BOILER_RECT.left + 20 + i * 24
            flicker = math.sin(self.fire_phase + i * 1.3) * 0.5 + 0.5
            fh = int((18 + flicker * 20) * self.heat_input)
            col = FIRE_COL[i % 3]
            pygame.draw.polygon(self.screen, col, [
                (fx, base_y),
                (fx - 7, base_y + fh),
                (fx + 7, base_y + fh),
            ])

    def _draw_steam_pipe(self):
        # Pipe from boiler top to cylinder left
        pipe_start = (BOILER_RECT.centerx, BOILER_RECT.top)
        pipe_mid   = (BOILER_RECT.centerx, CYL_TOP - 20)
        pipe_end   = (CYL_LEFT, CYL_TOP + CYL_HEIGHT // 2)
        pygame.draw.lines(self.screen, (160, 160, 170), False,
                          [pipe_start, pipe_mid, (CYL_LEFT - 10, CYL_TOP - 20), pipe_end], 6)

    def _draw_cylinder(self):
        px = self.piston_x()
        # Cylinder walls
        cyl_rect = pygame.Rect(CYL_LEFT, CYL_TOP, CYL_WIDTH, CYL_HEIGHT)
        pygame.draw.rect(self.screen, (80, 80, 90), cyl_rect)
        pygame.draw.rect(self.screen, (150, 150, 160), cyl_rect, 3)

        # Steam fill (left of piston)
        steam_w = int(px) - CYL_LEFT
        if steam_w > 0 and self.pressure > 0.05:
            alpha_val = int(min(255, self.pressure * 80))
            steam_surf = pygame.Surface((steam_w, CYL_HEIGHT - 6), pygame.SRCALPHA)
            steam_surf.fill((*STEAM_COL, alpha_val))
            self.screen.blit(steam_surf, (CYL_LEFT + 3, CYL_TOP + 3))

        # Piston
        piston_rect = pygame.Rect(int(px) - PISTON_W // 2, CYL_TOP + 2, PISTON_W, CYL_HEIGHT - 4)
        pygame.draw.rect(self.screen, PISTON_COL, piston_rect, border_radius=4)
        pygame.draw.rect(self.screen, (220, 220, 240), piston_rect, 2, border_radius=4)

        # Piston rod extending right to crank pin
        rod_start = (int(px) + PISTON_W // 2, CYL_TOP + CYL_HEIGHT // 2)
        cpx, cpy  = self.crank_pin()
        pygame.draw.line(self.screen, ROD_COL, rod_start, (int(cpx), int(cpy)), 6)
        # Pin circles
        pygame.draw.circle(self.screen, CRANK_COL, (int(px) + PISTON_W // 2, CYL_TOP + CYL_HEIGHT // 2), 6)
        pygame.draw.circle(self.screen, CRANK_COL, (int(cpx), int(cpy)), 8)

    def _draw_crank_assembly(self):
        cpx, cpy = self.crank_pin()
        # Main crank arm
        pygame.draw.line(self.screen, CRANK_COL, (CRANK_X, CRANK_Y), (int(cpx), int(cpy)), 10)
        # Main shaft
        pygame.draw.circle(self.screen, (200, 200, 210), (CRANK_X, CRANK_Y), 14)
        pygame.draw.circle(self.screen, (100, 100, 110), (CRANK_X, CRANK_Y), 14, 2)

    def _draw_flywheel(self):
        # Offset flywheel to the right of crank
        wx, wy = CRANK_X + 30, CRANK_Y
        # Spokes (8)
        for i in range(8):
            a = self.crank_angle + i * math.pi / 4
            sx = wx + int(WHEEL_R * 0.85 * math.cos(a))
            sy = wy + int(WHEEL_R * 0.85 * math.sin(a))
            pygame.draw.line(self.screen, (80, 130, 80), (wx, wy), (sx, sy), 4)
        # Rim
        pygame.draw.circle(self.screen, WHEEL_COL, (wx, wy), WHEEL_R, 8)
        # Hub
        pygame.draw.circle(self.screen, (150, 200, 150), (wx, wy), 18)
        pygame.draw.circle(self.screen, (60, 100, 60), (wx, wy), 18, 3)
        lbl = self.font_sm.render(f"{self.omega * 9.55:.0f} RPM", True, TEXT_COL)
        self.screen.blit(lbl, (wx - 30, wy + WHEEL_R + 10))

    def _draw_particles(self):
        for p in self.particles:
            alpha = int(p["life"] * 180)
            col = (*STEAM_COL, alpha)
            surf = pygame.Surface((p["r"] * 2, p["r"] * 2), pygame.SRCALPHA)
            pygame.draw.circle(surf, col, (p["r"], p["r"]), p["r"])
            self.screen.blit(surf, (int(p["x"]) - p["r"], int(p["y"]) - p["r"]))

    def _draw_gauge(self, cx, cy, radius, value, max_val, label, unit, colour):
        pygame.draw.circle(self.screen, GAUGE_BG, (cx, cy), radius)
        pygame.draw.circle(self.screen, (100, 100, 110), (cx, cy), radius, 2)
        # Arc ticks
        for i in range(11):
            a = math.radians(210 - i * 24)
            r0, r1 = radius - 10, radius - 4
            pygame.draw.line(self.screen, (180, 180, 180),
                             (cx + int(r0 * math.cos(a)), cy - int(r0 * math.sin(a))),
                             (cx + int(r1 * math.cos(a)), cy - int(r1 * math.sin(a))), 1)
        # Needle
        frac = min(1.0, value / max_val)
        needle_a = math.radians(210 - frac * 240)
        nx = cx + int((radius - 12) * math.cos(needle_a))
        ny = cy - int((radius - 12) * math.sin(needle_a))
        pygame.draw.line(self.screen, colour, (cx, cy), (nx, ny), 3)
        pygame.draw.circle(self.screen, colour, (cx, cy), 5)
        # Labels
        lbl = self.font_sm.render(label, True, TEXT_COL)
        self.screen.blit(lbl, (cx - lbl.get_width() // 2, cy + radius // 2 - 4))
        val_lbl = self.font_md.render(f"{value:.1f} {unit}", True, GAUGE_FG)
        self.screen.blit(val_lbl, (cx - val_lbl.get_width() // 2, cy - 10))

    def _draw_gauges(self):
        self._draw_gauge(860, 420, 55, self.pressure,    10.0, "Pressure", "bar", (220, 120, 80))
        self._draw_gauge(970, 420, 55, self.temperature, 180.0, "Temp",    "°C",  (200, 180, 80))

    def _draw_sliders(self):
        panel_rect = pygame.Rect(760, 100, 300, 200)
        pygame.draw.rect(self.screen, (45, 45, 55), panel_rect, border_radius=8)
        pygame.draw.rect(self.screen, (90, 90, 100), panel_rect, 1, border_radius=8)

        title = self.font_md.render("Controls", True, TEXT_COL)
        self.screen.blit(title, (panel_rect.left + 10, panel_rect.top + 10))

        self._draw_one_slider(self.slider_heat_rect, self.heat_input, "Heat Input", FIRE_COL[0])
        self._draw_one_slider(self.slider_load_rect, self.load,       "Load",       (120, 160, 220))

    def _draw_one_slider(self, rect, value, label, colour):
        lbl = self.font_sm.render(f"{label}:  {int(value*100)}%", True, TEXT_COL)
        self.screen.blit(lbl, (rect.left, rect.top - 18))
        pygame.draw.rect(self.screen, SLIDER_BG, rect, border_radius=7)
        fill = pygame.Rect(rect.left, rect.top, int(rect.width * value), rect.height)
        if fill.width > 0:
            pygame.draw.rect(self.screen, colour, fill, border_radius=7)
        pygame.draw.rect(self.screen, (140, 140, 150), rect, 1, border_radius=7)
        # Thumb
        tx = rect.left + int(rect.width * value)
        pygame.draw.circle(self.screen, (220, 220, 230), (tx, rect.centery), 9)

    def _draw_labels(self):
        title = self.font_lg.render("Watt's Workshop  —  Steam Engine Simulator", True, (200, 200, 220))
        self.screen.blit(title, (20, 12))
        hint = self.font_sm.render("Drag sliders to control heat and load.  SPACE = turn flywheel by hand.  ESC = quit.", True, (130, 130, 150))
        self.screen.blit(hint, (20, 44))

    # ── Input ─────────────────────────────────────────────────────────────────
    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); sys.exit()
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                pygame.quit(); sys.exit()
            if event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE:
                self.omega += 1.5   # manual kick, like turning the flywheel by hand

            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mx, my = event.pos
                if self.slider_heat_rect.inflate(0, 20).collidepoint(mx, my):
                    self.dragging = "heat"
                elif self.slider_load_rect.inflate(0, 20).collidepoint(mx, my):
                    self.dragging = "load"

            if event.type == pygame.MOUSEBUTTONUP:
                self.dragging = None

            if event.type == pygame.MOUSEMOTION and self.dragging:
                mx = event.pos[0]
                if self.dragging == "heat":
                    r = self.slider_heat_rect
                    self.heat_input = max(0.0, min(1.0, (mx - r.left) / r.width))
                elif self.dragging == "load":
                    r = self.slider_load_rect
                    self.load = max(0.0, min(1.0, (mx - r.left) / r.width))

    # ── Main loop ─────────────────────────────────────────────────────────────
    def run(self):
        while True:
            dt = self.clock.tick(FPS) / 1000.0
            self.handle_events()
            self.update(dt)
            self.draw()


if __name__ == "__main__":
    SteamEngine().run()
