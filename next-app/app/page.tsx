"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { PromptInputBox } from "@/components/ui/ai-prompt-box";
import { SplineOrb } from "@/components/SplineOrb";
import { Copy, Check, Trash2, ChevronDown } from "lucide-react";

const SPLINE_SCENE = process.env.NEXT_PUBLIC_SPLINE_SCENE ?? "";
const LS_KEY      = "jarvis_v2_history";
const MAX_STORED  = 80;

interface Message {
  id:   string;
  role: "user" | "jarvis";
  text: string;
  ts:   number;
}
type WsStatus = "connecting" | "online" | "offline";
type AppState = "idle" | "processing" | "speaking";

const CHIPS = [
  "What time is it?",
  "Weather update?",
  "System status",
  "Battery level",
  "Scan the network",
  "What's playing?",
];

const STATE_COLORS = {
  idle:       { glow: "59,130,246",  rim: "rgba(99,102,241,0.5)",  blob1: "#3b82f6", blob2: "#7c3aed", blob3: "#06b6d4" },
  processing: { glow: "249,115,22",  rim: "rgba(249,115,22,0.5)",  blob1: "#f97316", blob2: "#dc2626", blob3: "#fbbf24" },
  speaking:   { glow: "6,182,212",   rim: "rgba(34,211,238,0.65)", blob1: "#06b6d4", blob2: "#3b82f6", blob3: "#a78bfa" },
} as const;

// ── Ripple ring ──────────────────────────────────────────────────────────────
function Ripple({ color, delay, dur }: { color: string; delay: number; dur: number }) {
  return (
    <motion.div
      className="absolute rounded-full pointer-events-none"
      style={{ width: 170, height: 170, border: `1px solid rgba(${color},0.3)` }}
      initial={{ scale: 1, opacity: 0.5 }}
      animate={{ scale: 2.7, opacity: 0 }}
      transition={{ duration: dur, delay, repeat: Infinity, ease: "easeOut" }}
    />
  );
}

// ── Premium liquid-energy orb ────────────────────────────────────────────────
function JarvisOrb({ appState, wsStatus }: { appState: AppState; wsStatus: WsStatus }) {
  const online = wsStatus === "online";
  const c      = STATE_COLORS[appState];
  const speed  = appState === "processing" ? 1.8 : appState === "speaking" ? 2.0 : 5;

  return (
    <div className="relative flex items-center justify-center select-none" style={{ width: 180, height: 180 }}>
      {/* Halo glow */}
      <motion.div className="absolute rounded-full pointer-events-none"
        style={{ width: 180, height: 180,
          background: `radial-gradient(circle, rgba(${c.glow},0.22) 0%, transparent 72%)`,
          filter: "blur(22px)" }}
        animate={{ opacity: [0.55, 1, 0.55], scale: [1, 1.18, 1] }}
        transition={{ duration: 3.2, repeat: Infinity, ease: "easeInOut" }}
      />

      {/* Ripples when active */}
      <AnimatePresence>
        {online && appState !== "idle" && (
          <>
            <Ripple color={c.glow} delay={0}    dur={appState === "speaking" ? 1.1 : 1.6} />
            <Ripple color={c.glow} delay={0.45} dur={appState === "speaking" ? 1.1 : 1.6} />
            <Ripple color={c.glow} delay={0.9}  dur={appState === "speaking" ? 1.1 : 1.6} />
          </>
        )}
      </AnimatePresence>

      {/* Shell */}
      <motion.div className="relative rounded-full overflow-hidden"
        style={{ width: 130, height: 130, background: "#030308",
          boxShadow: online
            ? `0 0 32px rgba(${c.glow},0.52), 0 0 64px rgba(${c.glow},0.18), inset 0 0 0 1px rgba(255,255,255,0.06)`
            : "0 0 14px rgba(255,255,255,0.03), inset 0 0 0 1px rgba(255,255,255,0.03)" }}
        animate={appState === "speaking" ? { scale: [1, 1.08, 0.95, 1.06, 1] } : { scale: [1, 1.02, 1] }}
        transition={{ duration: appState === "speaking" ? 0.68 : 4.5, repeat: Infinity, ease: "easeInOut" }}
      >
        <motion.div className="absolute rounded-full"
          style={{ width: "95%", height: "95%", top: "2%", left: "2%",
            background: `radial-gradient(circle, ${c.blob1}cc 0%, transparent 68%)`, filter: "blur(14px)" }}
          animate={{ x: [-12, 10, -6, 12, -12], y: [-10, 6, 12, -8, -10] }}
          transition={{ duration: speed, repeat: Infinity, ease: "easeInOut", repeatType: "mirror" }} />
        <motion.div className="absolute rounded-full"
          style={{ width: "85%", height: "85%", bottom: 0, right: 0,
            background: `radial-gradient(circle, ${c.blob2}bb 0%, transparent 65%)`, filter: "blur(12px)" }}
          animate={{ x: [10, -12, 8, -4, 10], y: [8, -10, 4, 12, 8] }}
          transition={{ duration: speed * 0.85, repeat: Infinity, ease: "easeInOut", repeatType: "mirror" }} />
        <motion.div className="absolute rounded-full"
          style={{ width: "60%", height: "60%", top: "20%", left: "20%",
            background: `radial-gradient(circle, ${c.blob3}aa 0%, transparent 60%)`, filter: "blur(9px)" }}
          animate={{ x: [3, -8, 10, -3, 3], y: [-8, 9, -4, 7, -8] }}
          transition={{ duration: speed * 0.7, repeat: Infinity, ease: "easeInOut", repeatType: "mirror" }} />
        <motion.div className="absolute inset-0 rounded-full"
          style={{ background: "conic-gradient(from 0deg, transparent 0%, rgba(255,255,255,0.05) 20%, transparent 45%)" }}
          animate={{ rotate: 360 }}
          transition={{ duration: 10, repeat: Infinity, ease: "linear" }} />
        <div className="absolute rounded-full pointer-events-none"
          style={{ inset: "12%",
            background: "radial-gradient(circle at 32% 28%, rgba(255,255,255,0.14) 0%, transparent 55%)" }} />
        <div className="absolute inset-0 rounded-full pointer-events-none"
          style={{ boxShadow: "inset 0 0 32px rgba(0,0,0,0.65)" }} />
      </motion.div>

      {/* Rim ring */}
      <div className="absolute rounded-full pointer-events-none"
        style={{ width: 130, height: 130,
          boxShadow: online ? `0 0 0 1px ${c.rim}` : "0 0 0 1px rgba(255,255,255,0.05)",
          transition: "box-shadow 0.8s ease" }} />
    </div>
  );
}

// ── Typing indicator ─────────────────────────────────────────────────────────
function TypingDots() {
  return (
    <div className="flex justify-start animate-[msgIn_.22s_ease]">
      <div className="px-4 py-3 rounded-2xl rounded-tl-sm bg-black/25 border border-white/[0.1] backdrop-blur-md flex items-center gap-1.5">
        {[0, 150, 300].map(d => (
          <span key={d} className="block w-1.5 h-1.5 rounded-full bg-cyan-300/65"
            style={{ animation: "typingBounce 1s ease-in-out infinite", animationDelay: `${d}ms` }} />
        ))}
      </div>
    </div>
  );
}

// ── Copy button (visible on hover) ───────────────────────────────────────────
function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {}
  }, [text]);

  return (
    <button
      onClick={handleCopy}
      className="opacity-0 group-hover:opacity-100 focus:opacity-100 transition-all duration-150 p-1 rounded hover:bg-white/10 text-white/30 hover:text-white/70 flex-shrink-0"
      title="Copy message"
      aria-label="Copy message"
    >
      {copied
        ? <Check className="w-3.5 h-3.5 text-green-400" />
        : <Copy className="w-3.5 h-3.5" />}
    </button>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────
export default function Page() {
  const [messages,   setMessages]   = useState<Message[]>([]);
  const [isLoading,  setIsLoading]  = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [wsStatus,   setWsStatus]   = useState<WsStatus>("connecting");
  const [isAtBottom, setIsAtBottom] = useState(true);

  const wsRef            = useRef<WebSocket | null>(null);
  const audioCtxRef      = useRef<AudioContext | null>(null);
  const msgsEndRef       = useRef<HTMLDivElement>(null);
  const msgsContainerRef = useRef<HTMLDivElement>(null);
  const loadingTimerRef  = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pendingBootAudio = useRef<string | null>(null);
  const atBottomRef      = useRef(true);

  const appState: AppState = isSpeaking ? "speaking" : isLoading ? "processing" : "idle";
  const chatStarted = messages.length > 0;

  // ── Persist to localStorage ───────────────────────────────────────────────
  useEffect(() => {
    try {
      const saved = localStorage.getItem(LS_KEY);
      if (saved) {
        const parsed: Message[] = JSON.parse(saved);
        if (Array.isArray(parsed) && parsed.length) setMessages(parsed);
      }
    } catch {}
  }, []);

  useEffect(() => {
    if (!messages.length) return;
    try {
      localStorage.setItem(LS_KEY, JSON.stringify(messages.slice(-MAX_STORED)));
    } catch {}
  }, [messages]);

  // ── Scroll tracking ───────────────────────────────────────────────────────
  useEffect(() => {
    const el = msgsContainerRef.current;
    if (!el) return;
    const onScroll = () => {
      const near = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
      atBottomRef.current = near;
      setIsAtBottom(near);
    };
    el.addEventListener("scroll", onScroll, { passive: true });
    return () => el.removeEventListener("scroll", onScroll);
  }, [chatStarted]);

  useEffect(() => {
    if (atBottomRef.current) msgsEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  const scrollToBottom = useCallback(() => {
    msgsEndRef.current?.scrollIntoView({ behavior: "smooth" });
    setIsAtBottom(true);
  }, []);

  // ── Helpers ───────────────────────────────────────────────────────────────
  function clearLoadingTimer() {
    if (loadingTimerRef.current) clearTimeout(loadingTimerRef.current);
    loadingTimerRef.current = null;
  }

  function uid() {
    return `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
  }

  // ── Audio ─────────────────────────────────────────────────────────────────
  const playAudio = useCallback(async (b64: string, onDone?: () => void) => {
    try {
      if (!audioCtxRef.current) audioCtxRef.current = new AudioContext();
      const ctx = audioCtxRef.current;
      if (ctx.state === "suspended") await ctx.resume();
      const raw = Uint8Array.from(atob(b64), c => c.charCodeAt(0));
      const buf = await ctx.decodeAudioData(raw.buffer.slice(0));
      const src = ctx.createBufferSource();
      src.buffer = buf;
      src.connect(ctx.destination);
      setIsSpeaking(true);
      src.onended = () => { setIsSpeaking(false); clearLoadingTimer(); onDone?.(); };
      src.start(0);
    } catch {
      setIsSpeaking(false);
      clearLoadingTimer();
      onDone?.();
    }
  }, []);

  // ── WebSocket ─────────────────────────────────────────────────────────────
  useEffect(() => {
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;

    function connect() {
      const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
      const host  = window.location.hostname;
      const wsUrl = process.env.NEXT_PUBLIC_WS_URL ?? `${proto}//${host}:8080/ws`;
      const ws    = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen  = () => setWsStatus("online");
      ws.onclose = () => {
        setWsStatus("offline");
        setIsLoading(false);
        setIsSpeaking(false);
        reconnectTimer = setTimeout(connect, 2500);
      };
      ws.onerror = () => setWsStatus("offline");

      ws.onmessage = async (e) => {
        let d: Record<string, unknown>;
        try { d = JSON.parse(e.data); } catch { return; }

        // ── boot ──────────────────────────────────────────────────────────
        if (d.type === "boot") {
          setMessages(prev => {
            // Don't add boot greeting if history was already loaded
            if (prev.length > 0) return prev;
            return [{
              id:   `boot-${uid()}`,
              role: "jarvis",
              text: "J.A.R.V.I.S. online. Good to have you back, sir.",
              ts:   Date.now(),
            }];
          });
          if (typeof d.audio === "string") pendingBootAudio.current = d.audio;
          return;
        }

        // ── state ─────────────────────────────────────────────────────────
        if (d.type === "state") {
          // Server no longer sends "idle" — but guard anyway
          if (d.state === "idle") return;
          const loading = d.state === "processing" || d.state === "speaking";
          setIsLoading(loading);
          clearLoadingTimer();
          if (loading) loadingTimerRef.current = setTimeout(() => setIsLoading(false), 30_000);
          return;
        }

        // ── response ──────────────────────────────────────────────────────
        if (d.type === "response") {
          const text = typeof d.text === "string" ? d.text : "";
          setMessages(prev => [...prev, { id: `j-${uid()}`, role: "jarvis", text, ts: Date.now() }]);
          if (typeof d.audio === "string") {
            await playAudio(d.audio, () => setIsLoading(false));
          } else {
            clearLoadingTimer();
            setIsLoading(false);
          }
          return;
        }

        // ── error ─────────────────────────────────────────────────────────
        if (d.type === "error") {
          const text = typeof d.message === "string" ? d.message : "An error occurred, sir.";
          setMessages(prev => [...prev, { id: `err-${uid()}`, role: "jarvis", text, ts: Date.now() }]);
          clearLoadingTimer();
          setIsLoading(false);
        }
      };
    }

    connect();
    return () => {
      if (reconnectTimer) clearTimeout(reconnectTimer);
      clearLoadingTimer();
      wsRef.current?.close();
    };
  }, [playAudio]);

  // ── Send message ──────────────────────────────────────────────────────────
  const handleSend = useCallback((message: string, files?: File[]) => {
    const ws = wsRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN) return;

    // Unlock AudioContext on first user gesture; play pending boot audio
    if (!audioCtxRef.current) audioCtxRef.current = new AudioContext();
    const ctx        = audioCtxRef.current;
    const ensureReady = ctx.state === "suspended" ? ctx.resume() : Promise.resolve();
    ensureReady.then(() => {
      if (pendingBootAudio.current) {
        const audio = pendingBootAudio.current;
        pendingBootAudio.current = null;
        playAudio(audio).catch(() => {});
      }
    });

    setMessages(prev => [...prev, { id: `u-${uid()}`, role: "user", text: message, ts: Date.now() }]);

    if (files && files.length > 0) {
      const file = files[0];
      const reader = new FileReader();
      reader.onload = ev => {
        const url  = ev.target?.result as string;
        const mime = url.split(";")[0].replace("data:", "") || "image/jpeg";
        const b64  = url.split(",")[1];
        ws.send(JSON.stringify({ type: "text", text: message, image: b64, image_mime: mime }));
      };
      reader.readAsDataURL(file);
    } else {
      ws.send(JSON.stringify({ type: "text", text: message }));
    }
    setIsLoading(true);
  }, [playAudio]);

  // ── Clear conversation ────────────────────────────────────────────────────
  const handleClear = useCallback(() => {
    setMessages([]);
    try { localStorage.removeItem(LS_KEY); } catch {}
  }, []);

  // ── Derived display values ────────────────────────────────────────────────
  const statusLabel =
    wsStatus !== "online"       ? wsStatus
    : appState === "processing" ? "Processing"
    : appState === "speaking"   ? "Speaking"
    : "Ready";

  const statusDotClass =
    wsStatus === "online"
      ? appState === "speaking"   ? "bg-cyan-400 shadow-[0_0_8px_rgba(34,211,238,0.9)]"
      : appState === "processing" ? "bg-orange-400 shadow-[0_0_8px_rgba(251,146,60,0.9)] animate-pulse"
      : "bg-green-400 shadow-[0_0_6px_#4ade80]"
    : wsStatus === "offline"      ? "bg-red-400/70"
    : "bg-white/30 animate-pulse";

  const titleGlow =
    appState === "speaking"   ? "0 0 32px rgba(34,211,238,0.8),  0 2px 24px rgba(0,0,0,.3)" :
    appState === "processing" ? "0 0 28px rgba(251,146,60,0.8),  0 2px 24px rgba(0,0,0,.3)" :
                                "0 0 18px rgba(148,201,233,0.4), 0 2px 24px rgba(0,0,0,.25)";

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <div className="relative flex w-full h-screen overflow-hidden bg-[radial-gradient(125%_125%_at_50%_101%,rgba(245,87,2,1)_10.5%,rgba(245,120,2,1)_16%,rgba(245,140,2,1)_17.5%,rgba(245,170,100,1)_25%,rgba(238,174,202,1)_40%,rgba(202,179,214,1)_65%,rgba(148,201,233,1)_100%)] justify-center">

      {/* Spline — always mounted so scene stays loaded; opacity transitions on speaking */}
      {SPLINE_SCENE && (
        <motion.div
          className="absolute inset-0 z-0 pointer-events-none"
          animate={{ opacity: appState === "speaking" ? 1 : 0 }}
          transition={{ duration: 0.5, ease: "easeInOut" }}
        >
          <SplineOrb scene={SPLINE_SCENE} appState={appState} className="w-full h-full" />
        </motion.div>
      )}

      {/* HUD dot-grid overlay */}
      <div
        className="absolute inset-0 pointer-events-none opacity-30"
        style={{
          backgroundImage: "radial-gradient(rgba(255,255,255,0.07) 1px, transparent 1px)",
          backgroundSize:  "28px 28px",
        }}
      />

      {/* Scanline */}
      <div className="absolute inset-0 pointer-events-none overflow-hidden">
        <div
          className="absolute left-0 right-0 h-px bg-gradient-to-r from-transparent via-white/18 to-transparent"
          style={{ animation: "scanline 8s linear infinite" }}
        />
      </div>

      {/* ── Content column ── */}
      <div className="relative z-10 flex flex-col w-full max-w-[720px] px-4 sm:px-6 h-screen">

        {/* ── Header ─────────────────────────────────────────────────────── */}
        <header className="flex-shrink-0 flex items-center justify-between py-4 sm:py-5 animate-[fadeUp_.35s_ease]">
          <div>
            <h1
              className="text-xl sm:text-[22px] font-bold tracking-[.12em] text-white/90 transition-all duration-700 select-none"
              style={{ textShadow: titleGlow }}
            >
              J.A.R.V.I.S.
            </h1>
            <p className="text-[8px] text-white/25 tracking-[.2em] uppercase mt-0.5 hidden sm:block select-none">
              Just A Rather Very Intelligent System
            </p>
          </div>

          <div className="flex items-center gap-3">
            {/* Clear button — only in chat mode */}
            {chatStarted && (
              <button
                onClick={handleClear}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-full border border-white/15 bg-white/[0.06] text-white/40 text-[11px] tracking-[.04em] hover:bg-white/[0.12] hover:text-white/70 hover:border-white/30 active:scale-95 transition-all duration-200 backdrop-blur-sm"
                title="Clear conversation"
              >
                <Trash2 className="w-3 h-3" />
                <span className="hidden sm:inline">Clear</span>
              </button>
            )}

            {/* Status */}
            <div className="flex items-center gap-1.5">
              <div className={`w-1.5 h-1.5 rounded-full transition-all duration-500 ${statusDotClass}`} />
              <span className="text-[9px] tracking-[.18em] text-white/35 uppercase select-none">
                {statusLabel}
              </span>
            </div>
          </div>
        </header>

        {/* ── Welcome view ────────────────────────────────────────────────── */}
        {!chatStarted ? (
          <div className="flex-1 flex flex-col min-h-0 pb-5">
            {/* Centre — orb or prompt */}
            <div className="flex-1 flex items-center justify-center">
              {!SPLINE_SCENE ? (
                /* No Spline: always show CSS orb */
                <JarvisOrb appState={appState} wsStatus={wsStatus} />
              ) : (
                /* Spline configured: show CSS orb only while processing; idle = subtle text */
                <AnimatePresence mode="wait">
                  {appState === "processing" && (
                    <motion.div key="proc-orb"
                      initial={{ opacity: 0, scale: 0.8 }}
                      animate={{ opacity: 1, scale: 1 }}
                      exit={{ opacity: 0, scale: 0.8 }}
                      transition={{ duration: 0.3 }}
                    >
                      <JarvisOrb appState="processing" wsStatus={wsStatus} />
                    </motion.div>
                  )}
                  {appState === "speaking" && (
                    /* Spline handles this via full-screen opacity, nothing to show here */
                    <motion.div key="speaking-orb"
                      initial={{ opacity: 0, scale: 0.8 }}
                      animate={{ opacity: 1, scale: 1 }}
                      exit={{ opacity: 0, scale: 0.8 }}
                      transition={{ duration: 0.3 }}
                    >
                      <JarvisOrb appState="speaking" wsStatus={wsStatus} />
                    </motion.div>
                  )}
                  {appState === "idle" && (
                    <motion.div key="idle-hint"
                      initial={{ opacity: 0, y: 8 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: -4 }}
                      transition={{ duration: 0.5 }}
                      className="text-center select-none"
                    >
                      <p className="text-white/22 text-[13px] tracking-[.28em] uppercase">
                        How may I assist you, sir?
                      </p>
                    </motion.div>
                  )}
                </AnimatePresence>
              )}
            </div>

            {/* Chips + input */}
            <div className="flex-shrink-0 flex flex-col items-center gap-3">
              <div className="flex flex-wrap justify-center gap-2">
                {CHIPS.map(chip => (
                  <button
                    key={chip}
                    onClick={() => handleSend(chip)}
                    className="px-3.5 py-1.5 rounded-full border border-white/20 bg-white/[0.07] backdrop-blur-sm text-white/55 text-[11px] tracking-[.04em] hover:bg-white/[0.16] hover:border-white/45 hover:text-white/90 hover:scale-[1.04] active:scale-95 transition-all duration-200"
                  >
                    {chip}
                  </button>
                ))}
              </div>
              <div className="w-full">
                <PromptInputBox
                  onSend={handleSend}
                  isLoading={isLoading}
                  placeholder="Ask JARVIS anything…"
                />
              </div>
            </div>
          </div>

        ) : (
          /* ── Chat view ──────────────────────────────────────────────────── */
          <div className="flex-1 flex flex-col min-h-0 pb-4 relative">
            {/* Messages */}
            <div
              ref={msgsContainerRef}
              className="flex-1 overflow-y-auto flex flex-col gap-2.5 min-h-0 pb-2 pr-0.5 [scrollbar-width:thin] [scrollbar-color:rgba(255,255,255,0.1)_transparent]"
            >
              {messages.map(msg => (
                <div
                  key={msg.id}
                  className={`group flex animate-[msgIn_.22s_ease] ${
                    msg.role === "user" ? "justify-end" : "justify-start"
                  }`}
                >
                  <div className={`flex items-end gap-1 max-w-[84%] sm:max-w-[76%] ${
                    msg.role === "user" ? "flex-row-reverse" : "flex-row"
                  }`}>
                    {/* Bubble */}
                    <div className={`px-3.5 py-2.5 rounded-2xl text-[13.5px] leading-relaxed backdrop-blur-md break-words ${
                      msg.role === "jarvis"
                        ? "bg-black/25 border border-white/[0.1]  text-white/90 rounded-tl-sm"
                        : "bg-white/[0.13] border border-white/[0.2] text-white/88 rounded-tr-sm"
                    }`}>
                      {msg.text}
                    </div>

                    {/* Copy */}
                    <div className="self-end mb-1 flex-shrink-0">
                      <CopyButton text={msg.text} />
                    </div>
                  </div>
                </div>
              ))}

              {/* Typing indicator */}
              {isLoading && !isSpeaking && <TypingDots />}
              <div ref={msgsEndRef} />
            </div>

            {/* Scroll-to-bottom button */}
            <AnimatePresence>
              {!isAtBottom && (
                <motion.button
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: 6 }}
                  transition={{ duration: 0.18 }}
                  onClick={scrollToBottom}
                  className="absolute right-3 bottom-[4.5rem] sm:bottom-20 z-20 p-2 rounded-full bg-black/40 border border-white/15 backdrop-blur-sm text-white/50 hover:text-white/85 hover:bg-black/60 active:scale-95 transition-all shadow-lg"
                  aria-label="Scroll to bottom"
                >
                  <ChevronDown className="w-4 h-4" />
                </motion.button>
              )}
            </AnimatePresence>

            {/* Input */}
            <div className="flex-shrink-0 pt-1.5">
              <PromptInputBox
                onSend={handleSend}
                isLoading={isLoading}
                placeholder="Ask JARVIS anything…"
              />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
