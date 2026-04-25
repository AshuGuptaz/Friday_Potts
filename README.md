# J.A.R.V.I.S. — Tony Stark's AI Assistant

> *"Just A Rather Very Intelligent System"*  
> Built by **Ashutosh Gupta**

A production-grade, Tony Stark–inspired AI assistant with voice I/O, a premium 3D UI, real tool execution, and extended thinking — running entirely on your local machine.

---

## Demo

![JARVIS UI](https://prod.spline.design/8aFNsvAPw0cZmjY9/scene.splinecode)

> **Live preview:** `http://localhost:3000` after running `uv run jarvis`

---

## What it does

You type or speak → JARVIS thinks using Claude AI → responds with voice (ElevenLabs TTS) → a Spline 3D blob pulses as it speaks.

Behind the scenes it can:

| Capability | Detail |
|---|---|
| **Web search** | DuckDuckGo search + URL fetch |
| **System info** | Time, battery, volume, uptime |
| **macOS control** | Open apps, set volume, control music |
| **Network scan** | List devices on your local network |
| **Smart lights** | WLED / Philips Hue control |
| **Extended thinking** | Prefix `[Think: ...]` for deep Claude Sonnet reasoning |
| **Vision** | Attach an image — JARVIS can see and describe it |
| **Voice input** | Browser Web Speech API (no mic server needed) |

---

## Architecture

```
Browser (Next.js 16)
  │  WebSocket
  ▼
FastAPI Server  ──►  Claude Haiku / Sonnet (Anthropic)
  │                        │
  │                    Tool calls
  │                  ┌─────┴──────────────────┐
  │              web.py  system.py  macos.py  network.py  lights.py
  │
  └──► ElevenLabs TTS  →  base64 audio  →  Browser AudioContext
```

```
next-app/          # Next.js 16 + React 19 + Tailwind 4 + Framer Motion
app.py             # FastAPI WebSocket server — LLM + TTS + STT + tools
friday/tools/      # JARVIS tool modules
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Frontend** | Next.js 16, React 19, Tailwind CSS 4, Framer Motion |
| **3D UI** | Spline (`@splinetool/react-spline`) |
| **Backend** | FastAPI + Uvicorn |
| **LLM** | Claude Haiku 4.5 (fast) / Claude Sonnet 4.6 (thinking) |
| **TTS** | ElevenLabs Flash v2.5 |
| **STT** | Browser Web Speech API + Sarvam AI fallback |
| **Package manager** | `uv` (Python) + `npm` (Node) |

---

## Quick Start

### Prerequisites

| Tool | Install |
|---|---|
| Python ≥ 3.11 | [python.org](https://python.org) |
| Node.js ≥ 18 | [nodejs.org](https://nodejs.org) |
| `uv` | `pip install uv` |

### 1 — Clone & install

```bash
git clone https://github.com/AshuGuptaz/Friday_Potts.git
cd Friday_Potts

# Python deps
uv sync

# Next.js deps
cd next-app && npm install && cd ..
```

### 2 — Environment variables

```bash
cp .env.example .env
```

Open `.env` and fill in:

| Variable | Required | Where to get it |
|---|---|---|
| `ANTHROPIC_API_KEY` | ✅ | [console.anthropic.com](https://console.anthropic.com) |
| `ELEVEN_API_KEY` | ✅ | [elevenlabs.io](https://elevenlabs.io) → Profile → API Keys |
| `SARVAM_API_KEY` | optional | [dashboard.sarvam.ai](https://dashboard.sarvam.ai) — for server-side STT fallback |
| `JARVIS_VOICE_ID` | optional | ElevenLabs voice ID (default: British male) |

For the Next.js app, create `next-app/.env.local`:

```bash
cp next-app/.env.local.example next-app/.env.local
```

Optionally add a Spline scene URL for the 3D blob:

```env
NEXT_PUBLIC_SPLINE_SCENE=https://prod.spline.design/XXXXXXXXXXXXXXXX/scene.splinecode
```

### 3 — Run

```bash
uv run jarvis
```

This starts both servers simultaneously:
- **API** → `http://localhost:8080`
- **App** → `http://localhost:3000`

Open `http://localhost:3000` in your browser.

---

## Project Structure

```
Friday_Potts/
├── app.py                  # FastAPI server — WebSocket, LLM loop, TTS, STT
├── pyproject.toml          # Python project + uv scripts
├── .env.example            # Environment variable template
│
├── friday/
│   └── tools/
│       ├── web.py          # search_web, fetch_url, news
│       ├── system.py       # time, battery, volume, timer
│       ├── macos.py        # open apps, control music, set volume
│       ├── network.py      # scan LAN, ping, speedtest
│       ├── lights.py       # WLED / Philips Hue
│       └── utils.py        # calculate, unit convert
│
└── next-app/               # Next.js frontend
    ├── app/
    │   ├── page.tsx        # Main chat + welcome UI
    │   ├── layout.tsx
    │   └── globals.css
    ├── components/
    │   ├── SplineOrb.tsx   # Spline 3D scene wrapper
    │   └── ui/
    │       └── ai-prompt-box.tsx  # Input box with voice, attachments, think mode
    └── .env.local.example
```

---

## Features

### Chat UI
- **Premium glassmorphism** design with Iron Man HUD aesthetic
- **Spline 3D blob** pulses when JARVIS speaks (configure your own scene URL)
- **Persistent history** — conversations saved to localStorage across sessions
- **Copy messages** — hover any bubble to copy
- **Clear conversation** — trash icon in header
- **Scroll-to-bottom** button appears when scrolled up
- Fully **responsive** — works on mobile, tablet, desktop

### Input Modes
| Mode | How to use |
|---|---|
| **Text** | Type and press Enter or click send |
| **Voice** | Click the mic button → speak → auto-transcribes |
| **Image** | Attach or paste an image → JARVIS describes/analyses it |
| **Think** | Click the 🧠 Think button → uses Claude Sonnet with extended reasoning |

### JARVIS Personality
- Addresses you as *"sir"*
- Dry British wit, precise and calm
- No markdown in spoken responses
- Short answers for simple facts, paragraphs only when needed

---

## Adding a New Tool

1. Create `friday/tools/mytool.py`:

```python
def register(col):
    @col.tool()
    def my_tool(param: str) -> str:
        """One-line description shown to Claude."""
        return f"result for {param}"
```

2. Import it in `app.py`:

```python
from friday.tools import mytool
for _mod in (web, system, utils, network, macos, lights, mytool):
    _mod.register(_col)
```

That's it — Claude will automatically discover and call it.

---

## Environment Variables Reference

```env
# Required
ANTHROPIC_API_KEY=sk-ant-...
ELEVEN_API_KEY=sk_...

# Optional
SARVAM_API_KEY=sk_...          # Server-side STT fallback
JARVIS_VOICE_ID=JBFqnCBsd6R... # ElevenLabs voice ID

# Smart lights (optional)
WLED_IP=192.168.1.50           # WLED LED strip IP
HUE_BRIDGE_IP=192.168.1.2      # Philips Hue bridge IP
HUE_USERNAME=...               # Hue API username

# Ticketing (optional)
SUPABASE_URL=https://...
SUPABASE_API_KEY=...
```

---

## Scripts

```bash
uv run jarvis        # Start everything (backend + Next.js)
uv run friday        # MCP tool server only (SSE on :8000)
uv run hud           # Standalone HUD display
```

---

## License

MIT — built with ❤️ by [Ashutosh Gupta](https://github.com/AshuGuptaz)
