"""
macOS system controls — volume, brightness, apps, music, battery, notifications, screenshots.
All commands use osascript or native macOS CLI tools.
"""

import os
import subprocess


def _run(cmd: list[str] | str, shell: bool = False) -> tuple[str, int]:
    result = subprocess.run(
        cmd, shell=shell, capture_output=True, text=True, timeout=5
    )
    return result.stdout.strip(), result.returncode


def register(mcp):

    @mcp.tool()
    def set_volume(level: int) -> str:
        """Set system volume (0–100)."""
        level = max(0, min(100, level))
        _run(["osascript", "-e", f"set volume output volume {level}"])
        return f"Volume set to {level}%, sir."

    @mcp.tool()
    def get_volume() -> str:
        """Get current system volume level."""
        out, _ = _run(["osascript", "-e", "output volume of (get volume settings)"])
        return f"Current volume is {out}%, sir."

    @mcp.tool()
    def mute() -> str:
        """Mute system audio."""
        _run(["osascript", "-e", "set volume with output muted"])
        return "Audio muted, sir."

    @mcp.tool()
    def unmute() -> str:
        """Unmute system audio."""
        _run(["osascript", "-e", "set volume without output muted"])
        return "Audio restored, sir."

    @mcp.tool()
    def open_app(app_name: str) -> str:
        """Open a macOS application by name. Examples: Safari, Spotify, Calculator, Terminal, Finder, Xcode."""
        out, code = _run(["open", "-a", app_name])
        if code == 0:
            return f"Opening {app_name}, sir."
        return f"Application '{app_name}' not found on this system, sir."

    @mcp.tool()
    def get_battery_status() -> str:
        """Get battery charge percentage and charging status."""
        out, _ = _run(["pmset", "-g", "batt"])
        lines = [l.strip() for l in out.splitlines() if "%" in l]
        return lines[0] if lines else "Battery information unavailable, sir."

    @mcp.tool()
    def take_screenshot() -> str:
        """Capture a screenshot and save it to the Desktop."""
        path = os.path.expanduser("~/Desktop/jarvis_capture.png")
        _run(["screencapture", "-x", path])
        return "Screenshot captured and saved to Desktop as jarvis_capture.png, sir."

    @mcp.tool()
    def send_notification(title: str, message: str) -> str:
        """Send a macOS desktop notification with a title and message."""
        def _esc(s: str) -> str:
            return (s.replace("\\", "\\\\")
                     .replace('"', '\\"')
                     .replace("\r", "")
                     .replace("\n", " "))
        script = f'display notification "{_esc(message)}" with title "{_esc(title)}"'
        _run(["osascript", "-e", script])
        return "Notification dispatched, sir."

    @mcp.tool()
    def play_music() -> str:
        """Play music in Spotify (or Apple Music if Spotify is unavailable)."""
        out, code = _run(["osascript", "-e", 'tell application "Spotify" to play'])
        if code != 0:
            _run(["osascript", "-e", 'tell application "Music" to play'])
        return "Music playing, sir."

    @mcp.tool()
    def pause_music() -> str:
        """Pause the currently playing music in Spotify or Apple Music."""
        _run(["osascript", "-e", 'tell application "Spotify" to pause'])
        return "Music paused, sir."

    @mcp.tool()
    def next_track() -> str:
        """Skip to the next track in Spotify."""
        _run(["osascript", "-e", 'tell application "Spotify" to next track'])
        return "Skipping to next track, sir."

    @mcp.tool()
    def previous_track() -> str:
        """Go back to the previous track in Spotify."""
        _run(["osascript", "-e", 'tell application "Spotify" to previous track'])
        return "Going back to previous track, sir."

    @mcp.tool()
    def get_now_playing() -> str:
        """Get the currently playing track and artist from Spotify."""
        script = """
        tell application "Spotify"
            if it is running then
                return (name of current track) & " — " & (artist of current track)
            else
                return "not_running"
            end if
        end tell
        """
        out, code = _run(["osascript", "-e", script])
        if code != 0 or out == "not_running":
            return "Spotify is not running, sir."
        return f"Currently playing: {out}, sir."

    @mcp.tool()
    def lock_screen() -> str:
        """Lock the macOS screen immediately."""
        _run(["pmset", "displaysleepnow"])
        return "Screen locked, sir."

    @mcp.tool()
    def empty_trash() -> str:
        """Empty the macOS Trash."""
        _run(["osascript", "-e", 'tell app "Finder" to empty trash'])
        return "Trash emptied, sir."

    @mcp.tool()
    def get_wifi_name() -> str:
        """Get the name of the currently connected Wi-Fi network."""
        out, code = _run(
            ["/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport", "-I"]
        )
        if code != 0:
            out, _ = _run(["networksetup", "-getairportnetwork", "en0"])
        return out or "Wi-Fi network name unavailable, sir."

    @mcp.tool()
    def get_running_apps() -> str:
        """List all currently running applications."""
        script = 'tell application "System Events" to get name of every process whose background only is false'
        out, _ = _run(["osascript", "-e", script])
        apps = [a.strip() for a in out.split(",") if a.strip()]
        if not apps:
            return "Could not retrieve running applications, sir."
        return "Currently running: " + ", ".join(apps) + "."
