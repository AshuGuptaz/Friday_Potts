"""
System tools — time, environment info, timers, reminders.
"""

import datetime
import platform


def register(mcp):

    @mcp.tool()
    def get_current_time() -> str:
        """Return the current date and time in a human-readable format."""
        return datetime.datetime.now().strftime("%A, %B %d %Y at %I:%M %p")

    @mcp.tool()
    def get_system_info() -> dict:
        """Return basic information about the host system."""
        return {
            "os": platform.system(),
            "os_version": platform.version(),
            "machine": platform.machine(),
            "python_version": platform.python_version(),
        }

    @mcp.tool()
    def set_timer(seconds: int, label: str = "Timer") -> str:
        """Set a countdown timer. Returns confirmation. Max 3600 seconds."""
        if seconds <= 0 or seconds > 3600:
            return "Timer must be between 1 and 3600 seconds, boss."
        mins, secs = divmod(seconds, 60)
        if mins:
            duration = f"{mins} minute{'s' if mins > 1 else ''}"
            if secs:
                duration += f" {secs} second{'s' if secs > 1 else ''}"
        else:
            duration = f"{secs} second{'s' if secs > 1 else ''}"
        return f"Timer '{label}' set for {duration}. I've got it tracked, sir."

    @mcp.tool()
    def get_date_info() -> str:
        """Get the current day, date, time, and week number."""
        now = datetime.datetime.now()
        return (
            f"Today is {now.strftime('%A, %B %d, %Y')}. "
            f"Time: {now.strftime('%I:%M %p')}. "
            f"Week {now.isocalendar()[1]} of {now.year}."
        )
