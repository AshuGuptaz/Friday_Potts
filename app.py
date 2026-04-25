"""
JARVIS Local Server — custom UI, no LiveKit required.

Start:  uv run jarvis
Open:   http://localhost:8080
"""
from __future__ import annotations

import asyncio
import base64
import inspect
import json
import os
from pathlib import Path
from typing import Callable, get_type_hints

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.websockets import WebSocketState

load_dotenv()

ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ELEVEN_KEY    = os.getenv("ELEVEN_API_KEY", "")
SARVAM_KEY    = os.getenv("SARVAM_API_KEY", "")
VOICE_ID      = os.getenv("JARVIS_VOICE_ID", "JBFqnCBsd6RMkjVDRZzb")
CLAUDE_MODEL        = "claude-haiku-4-5-20251001"
CLAUDE_THINK_MODEL  = "claude-sonnet-4-6"   # extended thinking requires Sonnet+
ELEVEN_MODEL        = "eleven_flash_v2_5"

SYSTEM_PROMPT = """
You are J.A.R.V.I.S. (Just A Rather Very Intelligent System) — Tony Stark's personal AI.
Personality: highly intelligent, calm, dry British wit, precise. Always address the user as "sir."

Speaking rules (you are voice output — never use any of the following):
- No markdown, asterisks, bullet points, numbered lists, headers, or code blocks.
- No filler phrases like "Certainly!", "Of course!", "Great question!", or "Absolutely!"
- Speak naturally as if having a conversation. Use contractions.

Response length:
- One sentence for simple facts (time, battery, volume).
- Two to four sentences for most queries.
- Up to a short paragraph for complex explanations — never longer.

Tool rules:
- Call tools instantly and silently. Never announce that you are calling a tool.
- Run multiple tools in parallel when a request needs more than one.
- If a tool returns an error, say: "That system isn't responding at the moment, sir."
- Never invent data. If unsure, use a tool or say you don't know.

Context:
- Remember everything from earlier in this conversation.
- If the user refers to something said before, connect it naturally.
""".strip()

MAX_HISTORY = 24  # max user/assistant turns to keep (prevents token overflow)


# ── Tool collection (no MCP server needed) ──────────────────────────────────

class _Collector:
    def __init__(self):
        self.fns: dict[str, Callable] = {}

    def tool(self):
        def dec(fn):
            self.fns[fn.__name__] = fn
            return fn
        return dec

_col = _Collector()
try:
    from friday.tools import lights, macos, network, system, utils, web
    for _mod in (web, system, utils, network, macos, lights):
        _mod.register(_col)
    print(f"  Loaded {len(_col.fns)} tools: {', '.join(_col.fns)}")
except Exception as _e:
    print(f"  Warning: could not load tools — {_e}")

TOOLS: dict[str, Callable] = _col.fns

# Build Anthropic tool definitions from function signatures
_JTYPE = {str: "string", int: "integer", float: "number", bool: "boolean"}

def _claude_tool_def(fn) -> dict:
    sig = inspect.signature(fn)
    try:
        hints = get_type_hints(fn)
    except Exception:
        hints = {}
    props, req = {}, []
    for name, param in sig.parameters.items():
        props[name] = {"type": _JTYPE.get(hints.get(name, str), "string")}
        if param.default is inspect.Parameter.empty:
            req.append(name)
    desc = (fn.__doc__ or "").strip().split("\n")[0][:200] or fn.__name__
    return {
        "name": fn.__name__,
        "description": desc,
        "input_schema": {"type": "object", "properties": props, "required": req},
    }

CLAUDE_TOOLS = [_claude_tool_def(fn) for fn in TOOLS.values()]


# ── Pipeline helpers ─────────────────────────────────────────────────────────

async def _call_tool(name: str, args: dict) -> str:
    fn = TOOLS.get(name)
    if not fn:
        return f"Tool '{name}' not found."
    try:
        if inspect.iscoroutinefunction(fn):
            return str(await fn(**args))
        return str(await asyncio.to_thread(fn, **args))
    except Exception as e:
        return f"Tool error: {e}"


def _trim(messages: list) -> list:
    """Keep system prompt + last MAX_HISTORY user/assistant messages."""
    system = [m for m in messages if m["role"] == "system"]
    rest   = [m for m in messages if m["role"] != "system"]
    return system + rest[-MAX_HISTORY:]


async def _think(messages: list, use_thinking: bool = False) -> str:
    """Claude tool-call loop → final text response."""
    system = next((m["content"] for m in messages if m["role"] == "system"), "")
    conv = [{"role": m["role"], "content": m["content"]}
            for m in _trim(messages) if m["role"] in ("user", "assistant")]

    model = CLAUDE_THINK_MODEL if use_thinking else CLAUDE_MODEL

    async with httpx.AsyncClient() as c:
        for _ in range(8):
            payload: dict = {
                "model": model,
                "system": system,
                "messages": conv,
                "max_tokens": 16000 if use_thinking else 1024,
            }
            if use_thinking:
                payload["thinking"] = {"type": "enabled", "budget_tokens": 10000}
            if CLAUDE_TOOLS:
                payload["tools"] = CLAUDE_TOOLS

            try:
                r = await c.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": ANTHROPIC_KEY,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    },
                    json=payload,
                    timeout=60.0 if use_thinking else 30.0,
                )
                if r.status_code != 200:
                    print(f"[LLM] {r.status_code}: {r.text[:400]}")
                    r.raise_for_status()
            except httpx.TimeoutException:
                return "The request timed out, sir. Please try again."

            data      = r.json()
            blocks    = data.get("content") or []
            stop_reason = data.get("stop_reason", "")
            tool_uses = [b for b in blocks if b["type"] == "tool_use"]

            if stop_reason == "end_turn" or not tool_uses:
                text = " ".join(b["text"] for b in blocks if b["type"] == "text").strip()
                return text or "I'm afraid I didn't catch that, sir. Could you rephrase?"

            conv.append({"role": "assistant", "content": blocks})
            tool_results = await asyncio.gather(*[
                _call_tool(tu["name"], tu.get("input", {})) for tu in tool_uses
            ])
            conv.append({"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": tu["id"], "content": res}
                for tu, res in zip(tool_uses, tool_results)
            ]})

    return "That took longer than expected, sir. Shall I try again?"


async def _tts(text: str) -> bytes:
    async with httpx.AsyncClient() as c:
        r = await c.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}",
            headers={"xi-api-key": ELEVEN_KEY},
            json={
                "text": text,
                "model_id": ELEVEN_MODEL,
                "voice_settings": {
                    "stability": 0.88,
                    "similarity_boost": 0.90,
                    "style": 0.05,
                    "use_speaker_boost": True,
                    "speed": 0.90,
                },
            },
            timeout=30.0,
        )
        r.raise_for_status()
        return r.content


async def _stt_sarvam(audio_bytes: bytes) -> str:
    """Fallback STT via Sarvam HTTP endpoint."""
    try:
        async with httpx.AsyncClient() as c:
            r = await c.post(
                "https://api.sarvam.ai/speech-to-text",
                headers={"api-subscription-key": SARVAM_KEY},
                files={"file": ("audio.webm", audio_bytes, "audio/webm")},
                data={"model": "saaras:v3", "language_code": "en-IN"},
                timeout=30.0,
            )
            return r.json().get("transcript", "")
    except Exception:
        return ""


# ── FastAPI ──────────────────────────────────────────────────────────────────

app = FastAPI(title="JARVIS")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

STATIC_DIR = Path(__file__).parent / "static"

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
async def root():
    index = STATIC_DIR / "index.html"
    if not index.exists():
        return HTMLResponse(
            "<h1>J.A.R.V.I.S.</h1>"
            "<p>Static UI not found. Use the Next.js app at "
            "<a href='http://localhost:3000'>localhost:3000</a>.</p>"
        )
    return HTMLResponse(index.read_text(encoding="utf-8"))


class _SttRequest(BaseModel):
    audio: str = ""


@app.post("/stt")
async def stt_endpoint(body: _SttRequest):
    """Sarvam STT endpoint (fallback for browsers without Web Speech API)."""
    if not body.audio:
        return JSONResponse({"transcript": ""})
    transcript = await _stt_sarvam(base64.b64decode(body.audio))
    return JSONResponse({"transcript": transcript})


@app.websocket("/ws")
async def ws_handler(ws: WebSocket):
    await ws.accept()
    messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]

    async def send(tp: str, **kw):
        await ws.send_text(json.dumps({"type": tp, **kw}))

    async def respond(text: str):
        """Send LLM reply with audio; falls back to text-only if TTS fails."""
        await send("state", state="speaking")
        try:
            audio = await _tts(text)
            await send("response", text=text, audio=base64.b64encode(audio).decode())
        except Exception as tts_err:
            print(f"[TTS] error: {tts_err}")
            # Client will set idle after showing text-only response
            await send("response", text=text)

    try:
        # Boot: fire-and-forget so message loop starts immediately
        boot = "J.A.R.V.I.S. online. Good to have you back, sir."
        messages.append({"role": "assistant", "content": boot})
        async def _boot():
            try:
                audio = await _tts(boot)
                if ws.client_state == WebSocketState.CONNECTED:
                    await send("boot", audio=base64.b64encode(audio).decode())
            except Exception:
                pass
        asyncio.create_task(_boot())

        while True:
            raw = await ws.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue

            msg_type = data.get("type", "")

            if msg_type == "text":
                user_text = data.get("text", "").strip()
                if not user_text:
                    continue

                use_thinking = user_text.startswith("[Think:")
                if use_thinking:
                    user_text = user_text[user_text.index(":")+1:].rstrip("]").strip()

                await send("state", state="processing")

                image_b64  = data.get("image")
                image_mime = data.get("image_mime", "image/jpeg")
                if image_b64:
                    user_content: list | str = [
                        {"type": "image", "source": {"type": "base64", "media_type": image_mime, "data": image_b64}},
                        {"type": "text", "text": user_text},
                    ]
                else:
                    user_content = user_text
                messages.append({"role": "user", "content": user_content})

                try:
                    reply = await _think(messages, use_thinking=use_thinking)
                except Exception as e:
                    print(f"[Think] {e}")
                    reply = "I ran into an issue processing that, sir. Please try again."

                messages.append({"role": "assistant", "content": reply})
                await respond(reply)

            elif msg_type == "audio":
                await send("state", state="processing")
                audio_bytes = base64.b64decode(data.get("audio", ""))
                transcript  = await _stt_sarvam(audio_bytes)
                if not transcript.strip():
                    await send("state", state="idle")
                    continue

                await send("transcript", text=transcript)
                messages.append({"role": "user", "content": transcript})
                try:
                    reply = await _think(messages)
                except Exception as e:
                    print(f"[Think] {e}")
                    reply = "I ran into an issue processing that, sir. Please try again."

                messages.append({"role": "assistant", "content": reply})
                await respond(reply)

    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"[WS] {e}")
        try:
            await send("error", message="Something went wrong, sir. Reconnecting.")
        except Exception:
            pass


def main():
    import uvicorn, subprocess, atexit
    from pathlib import Path

    next_dir = Path(__file__).parent / "next-app"
    next_proc = None
    if next_dir.exists():
        next_proc = subprocess.Popen(["npm", "run", "dev"], cwd=next_dir)
        atexit.register(lambda: next_proc.terminate())

    print("\n  J.A.R.V.I.S.")
    print("  ─────────────────────────────")
    print("  API :  http://localhost:8080")
    if next_proc:
        print("  App :  http://localhost:3000")
    print()

    try:
        uvicorn.run("app:app", host="0.0.0.0", port=8080, reload=False)
    finally:
        if next_proc:
            next_proc.terminate()


if __name__ == "__main__":
    main()
