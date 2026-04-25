"""
JARVIS HUD Overlay — ambient light indicator that shows RGB effects on screen.

Run in a separate terminal:
  uv run hud

The lights tools auto-communicate with this HUD via localhost:7424.
"""

import math
import threading
import json
import tkinter as tk
from http.server import BaseHTTPRequestHandler, HTTPServer

HUD_PORT = 7424


class HUDApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("")

        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()

        self.W, self.H = 300, 130
        x = sw - self.W - 24
        y = sh - self.H - 70
        self.root.geometry(f"{self.W}x{self.H}+{x}+{y}")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 0.92)
        self.root.configure(bg="#000510")

        self.canvas = tk.Canvas(
            self.root, width=self.W, height=self.H,
            bg="#000510", highlightthickness=0,
        )
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # Drag to move
        self.canvas.bind("<ButtonPress-1>", self._drag_start)
        self.canvas.bind("<B1-Motion>", self._drag_move)
        self._drag_x = self._drag_y = 0

        # State
        self.r, self.g, self.b = 0, 80, 220
        self.brightness = 60
        self.mode = "STANDBY"
        self.effect = "solid"
        self.phase = 0.0
        self.animating = True

        self._tick()

    # ── drag ────────────────────────────────────────────────────────────────
    def _drag_start(self, e):
        self._drag_x, self._drag_y = e.x, e.y

    def _drag_move(self, e):
        x = self.root.winfo_x() + (e.x - self._drag_x)
        y = self.root.winfo_y() + (e.y - self._drag_y)
        self.root.geometry(f"+{x}+{y}")

    # ── helpers ─────────────────────────────────────────────────────────────
    def _tk(self, r, g, b, a=1.0):
        r = max(0, min(255, int(r * a)))
        g = max(0, min(255, int(g * a)))
        b = max(0, min(255, int(b * a)))
        return f"#{r:02x}{g:02x}{b:02x}"

    # ── drawing ─────────────────────────────────────────────────────────────
    def _draw(self):
        c = self.canvas
        c.delete("all")
        W, H = self.W, self.H
        r, g, b = self.r, self.g, self.b

        pulse = 0.55 + 0.45 * math.sin(self.phase)
        glow  = pulse if self.animating else 0.75

        # Background
        c.create_rectangle(0, 0, W, H, fill="#000510", outline="")

        # Border glow (layered)
        for i, a in enumerate([0.22, 0.14, 0.07]):
            c.create_rectangle(i, i, W - i, H - i,
                               outline=self._tk(r, g, b, a), width=1)

        # ── Arc reactor (left) ─────────────────────────────────────────────
        cx, cy = 58, 65

        # Outer halos
        for radius, a in [(40, 0.06 * glow), (34, 0.12 * glow), (27, 0.18 * glow)]:
            c.create_oval(cx - radius, cy - radius,
                          cx + radius, cy + radius,
                          fill=self._tk(r, g, b, a), outline="")

        # Spokes (hex)
        for i in range(6):
            angle = math.radians(i * 60)
            x1 = cx + 7 * math.cos(angle)
            y1 = cy + 7 * math.sin(angle)
            x2 = cx + 18 * math.cos(angle)
            y2 = cy + 18 * math.sin(angle)
            c.create_line(x1, y1, x2, y2,
                          fill=self._tk(r, g, b, 0.4 * glow), width=1)

        # Ring
        c.create_oval(cx - 20, cy - 20, cx + 20, cy + 20,
                      outline=self._tk(r, g, b, 0.7 * glow), width=1, fill="")

        # Core
        core_fill = self._tk(r, g, b, 0.75 * glow)
        c.create_oval(cx - 14, cy - 14, cx + 14, cy + 14,
                      fill=core_fill, outline=self._tk(r, g, b, 0.9), width=1)

        # Bright center
        bright_r = min(255, r + 120)
        bright_g = min(255, g + 120)
        bright_b = min(255, b + 120)
        c.create_oval(cx - 5, cy - 5, cx + 5, cy + 5,
                      fill=self._tk(bright_r, bright_g, bright_b, 0.95), outline="")

        # ── Text panel (right) ─────────────────────────────────────────────
        tx = 180  # center of text area

        c.create_text(tx, 24, text="J.A.R.V.I.S.",
                      fill=self._tk(r, g, b, 0.75),
                      font=("Courier", 10, "bold"), anchor="center")

        mode_a = 0.65 + 0.35 * pulse if self.animating else 0.85
        c.create_text(tx, 52, text=self.mode.upper(),
                      fill=self._tk(r, g, b, mode_a),
                      font=("Courier", 17, "bold"), anchor="center")

        # Brightness bar
        bx, by = 100, 78
        bw, bh = 160, 5
        frac = max(0.0, min(1.0, self.brightness / 100.0))
        c.create_rectangle(bx, by, bx + bw, by + bh,
                            fill="#0a0a12", outline=self._tk(r, g, b, 0.25))
        if frac > 0:
            c.create_rectangle(bx, by, bx + int(bw * frac), by + bh,
                                fill=self._tk(r, g, b, 0.75), outline="")

        # Separator lines
        sep = self._tk(r, g, b, 0.18)
        c.create_line(10, 13, W - 10, 13, fill=sep)
        c.create_line(10, H - 28, W - 10, H - 28, fill=sep)

        # Footer
        c.create_text(
            tx, H - 14,
            text=f"RGB {r:03d} {g:03d} {b:03d}   {self.brightness}%   {self.effect}",
            fill=self._tk(r, g, b, 0.35),
            font=("Courier", 7), anchor="center",
        )

    def _tick(self):
        if self.animating:
            spd = {"breathe": 0.06, "pulse": 0.10, "blink": 0.20,
                   "rainbow": 0.04, "fire": 0.15}.get(self.effect, 0.07)
            self.phase += spd
        self._draw()
        self.root.after(50, self._tick)

    # ── public API (called from HTTP thread via root.after) ─────────────────
    def update(self, r, g, b, brightness, mode, effect):
        self.r, self.g, self.b = r, g, b
        self.brightness = brightness
        self.mode = mode
        self.effect = effect
        self.animating = effect in ("breathe", "pulse", "blink", "wave",
                                    "cylon", "fire", "rainbow", "sparkle")

    def run(self):
        self.root.mainloop()


# ── HTTP server ──────────────────────────────────────────────────────────────

class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def do_POST(self):
        # Be defensive: a malformed Content-Length header or non-JSON body
        # would otherwise raise inside the handler and kill the request with
        # a 500, which in some Python versions also closes the connection
        # mid-response. Respond with 400 instead.
        try:
            n = int(self.headers.get("Content-Length", 0) or 0)
        except (TypeError, ValueError):
            self.send_response(400)
            self.end_headers()
            return
        try:
            data = json.loads(self.rfile.read(n)) if n > 0 else {}
        except (json.JSONDecodeError, ValueError):
            self.send_response(400)
            self.end_headers()
            return
        if not isinstance(data, dict):
            data = {}
        app = self.server.hud_app
        app.root.after(0, lambda: app.update(
            data.get("r", 0), data.get("g", 0), data.get("b", 0),
            data.get("brightness", 80),
            data.get("mode", "ACTIVE"),
            data.get("effect", "solid"),
        ))
        self.send_response(200)
        self.end_headers()


def _run_server(app: HUDApp):
    srv = HTTPServer(("127.0.0.1", HUD_PORT), _Handler)
    srv.hud_app = app
    print(f"  HUD server listening on port {HUD_PORT}")
    srv.serve_forever()


def main():
    print("JARVIS HUD initialising…")
    app = HUDApp()
    t = threading.Thread(target=_run_server, args=(app,), daemon=True)
    t.start()
    print("  Drag the HUD to reposition it.")
    app.run()


if __name__ == "__main__":
    main()
