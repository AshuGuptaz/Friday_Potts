"""
RGB lighting control.

Visual output (no hardware needed):
  • JARVIS HUD overlay (run `uv run hud` in a separate terminal)
  • macOS desktop background changes to the selected color

Hardware support (optional):
  • WLED  — set WLED_IP=192.168.x.x in .env
  • Philips Hue — set HUE_BRIDGE_IP + HUE_USERNAME in .env
"""

import os
import struct
import subprocess
import zlib

import httpx

WLED_IP    = os.getenv("WLED_IP", "")
HUE_BRIDGE = os.getenv("HUE_BRIDGE_IP", "")
HUE_USER   = os.getenv("HUE_USERNAME", "")
HUD_URL    = "http://127.0.0.1:7424/color"

# Named color palette
PALETTE: dict[str, list[int]] = {
    "red":         [255, 0, 0],
    "green":       [0, 220, 0],
    "blue":        [0, 80, 255],
    "white":       [255, 255, 255],
    "warm white":  [255, 200, 100],
    "yellow":      [255, 200, 0],
    "purple":      [150, 0, 230],
    "cyan":        [0, 220, 255],
    "orange":      [255, 110, 0],
    "pink":        [255, 0, 140],
    "off":         [0, 0, 0],
    # Stark-themed presets
    "iron man":    [200, 40, 0],
    "arc reactor": [80, 160, 255],
    "jarvis":      [0, 100, 255],
    "alert":       [255, 0, 0],
    "standby":     [0, 0, 50],
    "analysis":    [0, 180, 255],
    "stealth":     [10, 10, 40],
    "mark v":      [180, 200, 220],
}

WLED_FX: dict[str, int] = {
    "solid": 0, "blink": 1, "breathe": 2, "wipe": 3,
    "rainbow": 9, "fire": 66, "sparkle": 46,
    "wave": 31, "pulse": 2, "cylon": 25,
}


# ── desktop background ───────────────────────────────────────────────────────

def _make_png(r: int, g: int, b: int) -> bytes:
    """Build a 1×1 solid-colour PNG in pure Python (no Pillow needed)."""
    def chunk(tag: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(tag + data) & 0xFFFF_FFFF
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)

    ihdr = chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
    raw  = b"\x00" + bytes([r, g, b])          # filter-none + 1 RGB pixel
    idat = chunk(b"IDAT", zlib.compress(raw))
    iend = chunk(b"IEND", b"")
    return b"\x89PNG\r\n\x1a\n" + ihdr + idat + iend


def _set_desktop(r: int, g: int, b: int) -> bool:
    if r == g == b == 0:
        return False          # skip turning desktop black
    try:
        path = "/tmp/jarvis_ambient.png"
        with open(path, "wb") as f:
            f.write(_make_png(r, g, b))
        script = f'''tell application "System Events"
    tell every desktop
        set picture to "{path}"
    end tell
end tell'''
        result = subprocess.run(["osascript", "-e", script],
                                capture_output=True, timeout=5)
        return result.returncode == 0
    except Exception:
        return False


# ── HUD overlay ──────────────────────────────────────────────────────────────

def _notify_hud(r: int, g: int, b: int, brightness: int,
                mode: str, effect: str) -> None:
    try:
        httpx.post(HUD_URL, json={
            "r": r, "g": g, "b": b,
            "brightness": brightness, "mode": mode, "effect": effect,
        }, timeout=0.5)
    except Exception:
        pass  # HUD not running — that's fine


# ── hardware ─────────────────────────────────────────────────────────────────

def _wled(rgb: list[int], bri: int, fx: int = 0) -> bool:
    if not WLED_IP:
        return False
    try:
        payload = {"on": rgb != [0, 0, 0], "bri": bri,
                   "seg": [{"col": [rgb], "fx": fx}]}
        resp = httpx.post(f"http://{WLED_IP}/json/state",
                          json=payload, timeout=3.0)
        return resp.status_code == 200
    except Exception:
        return False


def _hue(rgb: list[int], bri: int) -> bool:
    if not HUE_BRIDGE or not HUE_USER:
        return False
    try:
        r, g, b = [x / 255.0 for x in rgb]
        X = r * 0.664511 + g * 0.154324 + b * 0.162028
        Y = r * 0.283881 + g * 0.668433 + b * 0.047685
        Z = r * 0.000088 + g * 0.072310 + b * 0.986039
        t = X + Y + Z or 1
        payload = {"on": rgb != [0, 0, 0], "bri": bri, "xy": [X / t, Y / t]}
        resp = httpx.put(
            f"http://{HUE_BRIDGE}/api/{HUE_USER}/groups/0/action",
            json=payload, timeout=3.0,
        )
        return resp.status_code == 200
    except Exception:
        return False


# ── main apply ───────────────────────────────────────────────────────────────

def _apply(rgb: list[int], brightness: int, mode: str,
           effect: str = "solid") -> str:
    bri_255 = max(0, min(255, int(brightness * 2.55)))
    fx_id   = WLED_FX.get(effect, 0)

    _notify_hud(*rgb, brightness, mode, effect)
    desktop_ok = _set_desktop(*rgb)
    hw_ok = _wled(rgb, bri_255, fx_id) or _hue(rgb, bri_255)

    if hw_ok:
        return "hardware+screen"
    if desktop_ok:
        return "screen"
    return "hud"


# ── tool registration ─────────────────────────────────────────────────────────

def register(mcp):

    @mcp.tool()
    def set_rgb_color(color: str, brightness: int = 80) -> str:
        """
        Set RGB lights to a named color.
        Colors: red, green, blue, white, warm white, yellow, purple, cyan,
        orange, pink, off, iron man, arc reactor, jarvis, alert, standby,
        analysis, stealth, mark v.
        Brightness 0-100.
        """
        key = color.lower().strip()
        if key not in PALETTE:
            matches = [k for k in PALETTE if key in k or k in key]
            key = matches[0] if matches else None
        if key is None:
            return f"Color '{color}' not in palette, sir. Try: {', '.join(PALETTE)}."

        rgb = PALETTE[key]
        if rgb == [0, 0, 0]:
            _apply(rgb, 0, "OFF", "solid")
            return "Lights powered down, sir."

        mode_applied = _apply(rgb, brightness, key.upper())
        hex_str = "#{:02X}{:02X}{:02X}".format(*rgb)
        return (
            f"Ambient lighting set to {key.title()} {hex_str} "
            f"at {brightness}% — {mode_applied} updated, sir."
        )

    @mcp.tool()
    def set_rgb_hex(hex_color: str, brightness: int = 80) -> str:
        """Set RGB lights to an exact hex color code, e.g. FF4500. Brightness 0-100."""
        hx = hex_color.strip("#").upper()
        if len(hx) != 6:
            return "Please provide a 6-digit hex code, sir. E.g. FF4500."
        try:
            rgb = [int(hx[i:i + 2], 16) for i in (0, 2, 4)]
        except ValueError:
            return "Invalid hex code, sir."
        _apply(rgb, brightness, f"#{hx}")
        return f"RGB lights set to #{hx} at {brightness}%, sir."

    @mcp.tool()
    def rgb_effect(effect: str, color: str = "jarvis") -> str:
        """
        Set an animated lighting effect.
        Effects: breathe, pulse, blink, rainbow, fire, sparkle, wave, cylon, solid.
        """
        rgb = PALETTE.get(color.lower(), PALETTE["jarvis"])
        _apply(rgb, 80, f"{effect.upper()}", effect)
        return f"Lighting effect '{effect}' engaged in {color} tone, sir."

    @mcp.tool()
    def rgb_off() -> str:
        """Turn off all RGB lights."""
        _apply([0, 0, 0], 0, "OFF", "solid")
        return "All ambient lighting powered down, sir."

    @mcp.tool()
    def jarvis_mode() -> str:
        """Activate JARVIS ambient lighting — soft pulsing blue arc reactor glow."""
        _apply(PALETTE["jarvis"], 65, "JARVIS", "breathe")
        return "JARVIS ambient lighting engaged. Arc reactor pulse active, sir."

    @mcp.tool()
    def alert_mode() -> str:
        """Activate red alert — flashing emergency lighting."""
        _apply(PALETTE["alert"], 100, "ALERT", "blink")
        return "Red alert activated. All non-essential systems on standby, sir."

    @mcp.tool()
    def party_mode() -> str:
        """Activate party mode — full rainbow cycling."""
        _apply([0, 200, 255], 100, "PARTY", "rainbow")
        return "Party mode engaged, sir. You clearly know how to celebrate."

    @mcp.tool()
    def get_rgb_status() -> str:
        """Get current RGB lighting hardware status."""
        if WLED_IP:
            try:
                resp = httpx.get(f"http://{WLED_IP}/json/state", timeout=2.0)
                s = resp.json()
                on  = s.get("on", False)
                bri = round(s.get("bri", 0) / 2.55)
                return (
                    f"WLED at {WLED_IP}: {'on' if on else 'off'}, "
                    f"{bri}% brightness, sir."
                )
            except Exception:
                return f"WLED device at {WLED_IP} is unreachable, sir."
        parts = []
        if HUE_BRIDGE:
            parts.append("Hue bridge configured")
        parts.append("Desktop ambient mode active")
        return (
            "RGB status: " + ", ".join(parts) + ". "
            "Run `uv run hud` in a terminal for the JARVIS HUD overlay, sir."
        )
