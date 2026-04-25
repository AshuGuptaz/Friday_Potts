"""
One-time script to find the best available JARVIS-like voice in your ElevenLabs account
and update agent_friday.py automatically.

Run once:  python setup_jarvis_voice.py

To get the EXACT Iron Man JARVIS voice (Paul Bettany):
  1. Find a clean Iron Man clip of JARVIS speaking (no music, no SFX)
  2. Go to: https://elevenlabs.io/app/voice-lab
  3. Click "Add a new voice" → "Instant Voice Clone"
  4. Upload 1-3 minutes of clean JARVIS audio
  5. Name it "JARVIS" and save
  6. Re-run this script — it will find and apply the cloned voice automatically
"""

import os
import re
import httpx
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("ELEVEN_API_KEY", "")
HEADERS = {"xi-api-key": API_KEY, "Content-Type": "application/json"}

# Fallback voice order — best to worst JARVIS match from pre-made library
FALLBACK_VOICES = [
    ("George",    "JBFqnCBsd6RMkjVDRZzb", "Deep authoritative British male"),
    ("Harry",     "SOYHLrjzK2X1ezoPC6cr", "Refined British male"),
    ("Charlie",   "IKne3meq5aSn9XLyUdCD", "British male"),
    ("Brian",     "nPczCjzI2devNBz1zQrb", "Deep authoritative male"),
    ("Callum",    "N2lVS1w4EtoT3dr4eOWO", "British male"),
]

AGENT_FILE = os.path.join(os.path.dirname(__file__), "agent_friday.py")


def get_voices() -> list[dict]:
    try:
        resp = httpx.get("https://api.elevenlabs.io/v1/voices", headers=HEADERS, timeout=10)
        return resp.json().get("voices", [])
    except Exception as e:
        print(f"  Could not fetch voices: {e}")
        return []


def find_best_voice(voices: list[dict]) -> tuple[str, str, str]:
    """Search for a cloned JARVIS voice first, then fall back to best pre-made."""
    # Priority 1: any voice the user cloned and named "jarvis"
    for v in voices:
        if "jarvis" in v.get("name", "").lower():
            return v["name"], v["voice_id"], "Your custom JARVIS clone"

    # Priority 2: known good British male pre-made voices (if in the account)
    account_ids = {v["voice_id"] for v in voices}
    for name, vid, desc in FALLBACK_VOICES:
        if vid in account_ids:
            return name, vid, desc

    # Priority 3: any pre-made British male voice in the account
    for v in voices:
        labels  = v.get("labels", {})
        accent  = labels.get("accent", "").lower()
        gender  = labels.get("gender", "").lower()
        category = v.get("category", "")
        if "british" in accent and "male" in gender and category == "premade":
            return v["name"], v["voice_id"], "Pre-made British male"

    # Absolute fallback
    return FALLBACK_VOICES[0]


def patch_agent(name: str, voice_id: str, desc: str):
    """Rewrite the ELEVENLABS_VOICE_ID line in agent_friday.py."""
    with open(AGENT_FILE, "r") as f:
        src = f.read()

    new_line = (
        f'ELEVENLABS_VOICE_ID = "{voice_id}"'
        f'  # {name} – {desc}'
    )
    patched = re.sub(
        r'^ELEVENLABS_VOICE_ID\s*=.*$',
        new_line,
        src,
        flags=re.MULTILINE,
    )
    with open(AGENT_FILE, "w") as f:
        f.write(patched)


if __name__ == "__main__":
    if not API_KEY:
        print("ERROR: ELEVEN_API_KEY not set in .env")
        raise SystemExit(1)

    print("Fetching voices from your ElevenLabs account…")
    voices = get_voices()
    print(f"  Found {len(voices)} voice(s) in your account.")

    print("\nSearching for best JARVIS match…")
    name, vid, desc = find_best_voice(voices)
    print(f"  → {name:20} {vid}  ({desc})")

    print("\nUpdating agent_friday.py…")
    patch_agent(name, vid, desc)
    print(f"  Done. Voice set to: {name}")

    print("""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 To get the EXACT Iron Man JARVIS voice:
  1. Find a clean Iron Man JARVIS clip (no BGM)
  2. https://elevenlabs.io/app/voice-lab
     → Add Voice → Instant Voice Clone
  3. Upload 1-3 min of clean JARVIS audio
  4. Name the voice "JARVIS" and save
  5. Re-run: python setup_jarvis_voice.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")
