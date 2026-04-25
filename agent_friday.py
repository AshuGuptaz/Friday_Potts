"""
FRIDAY – Voice Agent (MCP-powered)
===================================
Iron Man-style voice assistant that controls RGB lighting, runs diagnostics,
scans the network, and triggers dramatic boot sequences via an MCP server
running on the Windows host.

MCP Server URL is auto-resolved from WSL → Windows host IP.

Run:
  uv run agent_friday.py dev      – LiveKit Cloud mode
  uv run agent_friday.py console  – text-only console mode
"""

import os
import logging
import subprocess

from dotenv import load_dotenv
from livekit.agents import JobContext, WorkerOptions, cli
from livekit.agents.voice import Agent, AgentSession
from livekit.agents.llm import mcp

# Plugins
from livekit.plugins import google as lk_google, openai as lk_openai, sarvam, silero, elevenlabs
from livekit.plugins.elevenlabs import VoiceSettings

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------

STT_PROVIDER       = "sarvam"
LLM_PROVIDER       = "groq"
TTS_PROVIDER       = "elevenlabs"

GEMINI_LLM_MODEL   = "gemini-2.0-flash"
GROQ_LLM_MODEL     = "meta-llama/llama-4-scout-17b-16e-instruct"
OPENAI_LLM_MODEL   = "gpt-4o"

OPENAI_TTS_MODEL   = "tts-1"
OPENAI_TTS_VOICE   = "onyx"       # "onyx" – deep authoritative male, closest to JARVIS
TTS_SPEED           = 1.15

SARVAM_TTS_LANGUAGE = "en-IN"
SARVAM_TTS_SPEAKER  = "abhilash"

# ElevenLabs — JARVIS-style voice
# "George" — deep, authoritative British male, best free-tier JARVIS match
ELEVENLABS_VOICE_ID = "JBFqnCBsd6RMkjVDRZzb"  # George – authoritative British male

# MCP server running on Windows host
MCP_SERVER_PORT = 8000

# ---------------------------------------------------------------------------
# System prompt – F.R.I.D.A.Y.
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """
You are J.A.R.V.I.S. — Just A Rather Very Intelligent System. Tony Stark's AI. British, calm, precise, occasionally dry. You call the user "sir" or "boss".

Core rules:
- Keep responses to 2-4 sentences. You are speaking — no lists, no markdown, no bullet points.
- Call tools immediately and silently. Never announce tool names or say "I'm calling a tool".
- If a tool fails: "Systems are unresponsive at the moment, sir. Shall I try again?"

Tool routing:
- News → get_world_news, then open_world_monitor automatically.
- Weather → get_weather. Search → search_web.
- Math/conversions → calculate or convert_units.
- Timer → set_timer. Time/date → get_current_time or get_date_info.
- Network → scan_network, ping_host, or check_internet.
- Volume → set_volume, get_volume, mute, unmute.
- Music → play_music, pause_music, next_track, previous_track, get_now_playing.
- Open an app → open_app.
- Battery → get_battery_status. Screenshot → take_screenshot.
- Notifications → send_notification.
- RGB lights → set_rgb_color, set_rgb_hex, rgb_effect, rgb_off, jarvis_mode, alert_mode, party_mode.
- Boot sequence → jarvis_mode for lights.
- System info → get_system_info. Running apps → get_running_apps.
""".strip()
# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------

load_dotenv()

logger = logging.getLogger("friday-agent")
logger.setLevel(logging.INFO)


# ---------------------------------------------------------------------------
# Resolve Windows host IP from WSL
# ---------------------------------------------------------------------------

def _get_windows_host_ip() -> str:
    """Get the Windows host IP by looking at the default network route."""
    try:
        # 'ip route' is the most reliable way to find the 'default' gateway
        # which is always the Windows host in WSL.
        cmd = "ip route show default | awk '{print $3}'"
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=2
        )
        ip = result.stdout.strip()
        if ip:
            logger.info("Resolved Windows host IP via gateway: %s", ip)
            return ip
    except Exception as exc:
        logger.warning("Gateway resolution failed: %s. Trying fallback...", exc)

    # Fallback to your original resolv.conf logic if 'ip route' fails
    try:
        with open("/etc/resolv.conf", "r") as f:
            for line in f:
                if "nameserver" in line:
                    ip = line.split()[1]
                    logger.info("Resolved Windows host IP via nameserver: %s", ip)
                    return ip
    except Exception:
        pass

    return "127.0.0.1"

def _mcp_server_url() -> str:
    # host_ip = _get_windows_host_ip()
    # url = f"http://{host_ip}:{MCP_SERVER_PORT}/sse"
    # url = f"https://ongoing-colleague-samba-pioneer.trycloudflare.com/sse"
    url = f"http://127.0.0.1:{MCP_SERVER_PORT}/sse"
    logger.info("MCP Server URL: %s", url)
    return url


# ---------------------------------------------------------------------------
# Build provider instances
# ---------------------------------------------------------------------------

def _build_stt():
    if STT_PROVIDER == "sarvam":
        logger.info("STT → Sarvam Saaras v3")
        return sarvam.STT(
            language="unknown",
            model="saaras:v3",
            mode="transcribe",
            flush_signal=True,
            sample_rate=16000,
        )
    elif STT_PROVIDER == "whisper":
        logger.info("STT → OpenAI Whisper")
        return lk_openai.STT(model="whisper-1")
    else:
        raise ValueError(f"Unknown STT_PROVIDER: {STT_PROVIDER!r}")


def _build_llm():
    if LLM_PROVIDER == "openai":
        logger.info("LLM → OpenAI (%s)", OPENAI_LLM_MODEL)
        return lk_openai.LLM(model=OPENAI_LLM_MODEL)
    elif LLM_PROVIDER == "gemini":
        logger.info("LLM → Google Gemini (%s)", GEMINI_LLM_MODEL)
        return lk_google.LLM(model=GEMINI_LLM_MODEL, api_key=os.getenv("GOOGLE_API_KEY"))
    elif LLM_PROVIDER == "groq":
        logger.info("LLM → Groq (%s)", GROQ_LLM_MODEL)
        return lk_openai.LLM(
            model=GROQ_LLM_MODEL,
            base_url="https://api.groq.com/openai/v1",
            api_key=os.getenv("GROQ_API_KEY"),
        )
    else:
        raise ValueError(f"Unknown LLM_PROVIDER: {LLM_PROVIDER!r}")


def _build_tts():
    if TTS_PROVIDER == "sarvam":
        logger.info("TTS → Sarvam Bulbul v3")
        return sarvam.TTS(
            target_language_code=SARVAM_TTS_LANGUAGE,
            model="bulbul:v2",
            speaker=SARVAM_TTS_SPEAKER,
            pace=TTS_SPEED,
        )
    elif TTS_PROVIDER == "openai":
        logger.info("TTS → OpenAI TTS (%s / %s)", OPENAI_TTS_MODEL, OPENAI_TTS_VOICE)
        return lk_openai.TTS(model=OPENAI_TTS_MODEL, voice=OPENAI_TTS_VOICE, speed=TTS_SPEED)
    elif TTS_PROVIDER == "elevenlabs":
        logger.info("TTS → ElevenLabs (George — British male)")
        return elevenlabs.TTS(
            voice_id=ELEVENLABS_VOICE_ID,
            model="eleven_multilingual_v2",
            api_key=os.getenv("ELEVEN_API_KEY"),
            language="en",
            voice_settings=VoiceSettings(
                stability=0.88,        # JARVIS never wavers — maximum consistency
                similarity_boost=0.90, # High fidelity to the voice character
                style=0.05,            # Minimal emotion — precise, digital delivery
                speed=0.90,            # Measured, deliberate — never rushed
            ),
        )
    else:
        raise ValueError(f"Unknown TTS_PROVIDER: {TTS_PROVIDER!r}")


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

class FridayAgent(Agent):
    """
    F.R.I.D.A.Y. – Iron Man-style voice assistant.
    All tools are provided via the MCP server on the Windows host.
    """

    def __init__(self, stt, llm, tts) -> None:
        super().__init__(
            instructions=SYSTEM_PROMPT,
            stt=stt,
            llm=llm,
            tts=tts,
            vad=silero.VAD.load(),
            mcp_servers=[
                mcp.MCPServerHTTP(
                    url=_mcp_server_url(),
                    transport_type="sse",
                    client_session_timeout_seconds=30,
                ),
            ],
        )

    async def on_enter(self) -> None:
        """JARVIS boot sequence greeting."""
        await self.session.generate_reply(
            instructions=(
                "Deliver the JARVIS boot sequence: "
                "'All systems online. J.A.R.V.I.S. is fully operational. "
                "Good to have you back, sir. How may I assist you today?' "
                "Speak with calm authority, like the real JARVIS."
            )
        )


# ---------------------------------------------------------------------------
# LiveKit entry point
# ---------------------------------------------------------------------------

def _turn_detection() -> str:
    return "stt" if STT_PROVIDER == "sarvam" else "vad"


def _endpointing_delay() -> float:
    return {"sarvam": 0.07, "whisper": 0.3}.get(STT_PROVIDER, 0.1)


async def entrypoint(ctx: JobContext) -> None:
    logger.info(
        "FRIDAY online – room: %s | STT=%s | LLM=%s | TTS=%s",
        ctx.room.name, STT_PROVIDER, LLM_PROVIDER, TTS_PROVIDER,
    )

    stt = _build_stt()
    llm = _build_llm()
    tts = _build_tts()

    session = AgentSession(
        turn_detection=_turn_detection(),
        min_endpointing_delay=_endpointing_delay(),
    )

    await session.start(
        agent=FridayAgent(stt=stt, llm=llm, tts=tts),
        room=ctx.room,
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))

def dev():
    """Wrapper to run the agent in dev mode automatically."""
    import sys
    # If no command was provided, inject 'dev'
    if len(sys.argv) == 1:
        sys.argv.append("dev")
    main()

if __name__ == "__main__":
    main()