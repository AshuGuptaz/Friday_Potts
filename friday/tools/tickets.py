"""
Supabase ticketing — create, list, and update tasks/tickets.
"""

import os
import httpx
from datetime import datetime, timezone


def _headers():
    return {
        "apikey": os.getenv("SUPABASE_API_KEY", ""),
        "Authorization": f"Bearer {os.getenv('SUPABASE_API_KEY', '')}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }

def _base_url():
    return os.getenv("SUPABASE_URL", "").rstrip("/")


def register(mcp):

    @mcp.tool()
    async def create_ticket(title: str, description: str = "", priority: str = "normal") -> str:
        """Create a new task or ticket. Priority: low, normal, high."""
        url = _base_url()
        if not url or not os.getenv("SUPABASE_API_KEY"):
            return "Ticketing system offline — Supabase credentials not configured, boss."
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.post(
                    f"{url}/tickets",
                    headers=_headers(),
                    json={
                        "title": title,
                        "description": description,
                        "priority": priority,
                        "status": "open",
                        "created_at": datetime.now(timezone.utc).isoformat(),
                    }
                )
                r.raise_for_status()
                data = r.json()
                ticket_id = data[0].get("id") if isinstance(data, list) else data.get("id")
                return f"Ticket #{ticket_id} created: '{title}' — priority {priority}."
        except Exception as e:
            return f"Failed to create ticket: {e}"

    @mcp.tool()
    async def list_tickets(status: str = "open") -> str:
        """List tickets by status: open, in_progress, done."""
        url = _base_url()
        if not url or not os.getenv("SUPABASE_API_KEY"):
            return "Ticketing system offline — Supabase credentials not configured, boss."
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(
                    f"{url}/tickets",
                    headers=_headers(),
                    params={"status": f"eq.{status}", "order": "created_at.desc", "limit": "10"}
                )
                r.raise_for_status()
                tickets = r.json()
                if not tickets:
                    return f"No {status} tickets found, boss."
                lines = [f"#{t.get('id')} [{t.get('priority','?').upper()}] {t.get('title')}" for t in tickets]
                return f"{len(tickets)} {status} ticket(s):\n" + "\n".join(lines)
        except Exception as e:
            return f"Failed to fetch tickets: {e}"

    @mcp.tool()
    async def close_ticket(ticket_id: int) -> str:
        """Mark a ticket as done."""
        url = _base_url()
        if not url or not os.getenv("SUPABASE_API_KEY"):
            return "Ticketing system offline — Supabase credentials not configured, boss."
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.patch(
                    f"{url}/tickets",
                    headers=_headers(),
                    params={"id": f"eq.{ticket_id}"},
                    json={"status": "done"}
                )
                r.raise_for_status()
                return f"Ticket #{ticket_id} closed. Good work, boss."
        except Exception as e:
            return f"Failed to close ticket: {e}"
