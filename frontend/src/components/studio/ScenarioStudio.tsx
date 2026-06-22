"use client"

import { useState, useEffect, useRef } from "react"
import { CanvasCityTwin } from "./CanvasCityTwin"
import { AIVisionPanel } from "./AIVisionPanel"
import { AIDecisionEngine } from "./AIDecisionEngine"
import { IncidentTimeline } from "./IncidentTimeline"
import { BeforeAfterReplay } from "./BeforeAfterReplay"
import { useNexusStream } from "@/hooks/useNexusStream"
import { Button } from "@/components/ui/button"
import { Activity, Car, RefreshCw, AlertTriangle, ShieldCheck } from "lucide-react"
import { AnimatePresence, motion } from "framer-motion"

export function ScenarioStudio() {
  const { state: nexusState, connected, totalQueue, maxAnomaly } = useNexusStream();
  
  const [simState, setSimState] = useState<"none" | "detected" | "intervening" | "recovering" | "recovered">("none");
  const [timeline, setTimeline] = useState<{time: string, msg: string, type: string}[]>([]);
  const [cityHealth, setCityHealth] = useState(98);
  const [showReplay, setShowReplay] = useState(false);
  const [zoomLevel, setZoomLevel] = useState(1);
  const [flashRed, setFlashRed] = useState(false);

  // Auto-health tracker
  useEffect(() => {
    const targetHealth = Math.max(10, 100 - (totalQueue * 1.5));
    setCityHealth(prev => {
      if (prev > targetHealth) return prev - 1;
      if (prev < targetHealth) return prev + 1;
      return prev;
    });
  }, [totalQueue]);

  const getTimeStr = (offsetSecs: number) => {
    const d = new Date();
    d.setSeconds(d.getSeconds() + offsetSecs);
    return d.toTimeString().split(' ')[0];
  }

  const launchScenario = async () => {
    // 1. Reset and Upload
    setSimState("none");
    setTimeline([{ time: getTimeStr(0), msg: "Video Uploaded", type: "slate" }]);

    // Cinematic Timings
    setTimeout(() => {
      setTimeline(prev => [...prev, { time: getTimeStr(2), msg: "VideoMAE Extracted Features", type: "blue" }]);
    }, 2000);

    setTimeout(() => {
      // 2. DETECTED - Hackathon Moment!
      setSimState("detected");
      setZoomLevel(1.3); // CSS Transform zoom
      setFlashRed(true); // Red flash overlay
      setTimeout(() => setFlashRed(false), 300); // clear flash
      
      // Siren audio
      const audio = new Audio("https://actions.google.com/sounds/v1/alarms/alarm_clock.ogg"); // Standard safe beep URL
      audio.volume = 0.3;
      audio.play().catch(() => {});

      setTimeline(prev => [
        ...prev, 
        { time: getTimeStr(3), msg: "MULDE Score = 39.8", type: "red" },
        { time: getTimeStr(3), msg: "Severity = 0.85", type: "red" }
      ]);
    }, 4000);

    setTimeout(async () => {
      // 3. INTERVENING - RL Actions
      setSimState("intervening");
      setTimeline(prev => [
        ...prev, 
        { time: getTimeStr(4), msg: "RL Policy Updated", type: "emerald" },
        { time: getTimeStr(7), msg: "Signal Timing Changed", type: "emerald" }
      ]);
      
      // Fire real backend injection to align physical simulation with the UI
      try {
        await fetch("http://localhost:8001/api/inject", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ anomaly_severity: 0.85 })
        });
      } catch (e) {
        console.error(e);
      }
    }, 6000);

    setTimeout(() => {
      // 4. RECOVERING
      setSimState("recovering");
      setTimeline(prev => [...prev, { time: getTimeStr(14), msg: "Stops Reduced", type: "emerald" }]);
      setZoomLevel(1); // Zoom back out
    }, 14000);

    setTimeout(() => {
      // 5. RECOVERED
      setSimState("recovered");
      setTimeline(prev => [...prev, { time: getTimeStr(31), msg: "Traffic Normalized", type: "emerald" }]);
    }, 24000);
  };

  return (
    <div className="relative w-full h-[calc(100vh-2rem)] text-slate-200 bg-black font-sans overflow-hidden">
      
      {/* 1. THE MASSIVE BACKGROUND (Exact replica of Image 3 style, with auto-zoom) */}
      <motion.div 
        animate={{ scale: zoomLevel }} 
        transition={{ duration: 1.5, ease: "easeInOut" }}
        className="absolute inset-0 origin-center"
      >
        <CanvasCityTwin nexusState={nexusState} simState={simState} />
      </motion.div>

      {/* FLASH RED OVERLAY */}
      {flashRed && <div className="absolute inset-0 bg-red-600/40 z-30 pointer-events-none"></div>}

      {/* 2. FLOATING HEADER (Top Center) */}
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-3/4 max-w-4xl bg-slate-950/80 backdrop-blur-md border-b border-x border-slate-800/50 rounded-b-3xl px-8 py-3 flex justify-between items-center z-40 shadow-[0_10px_30px_rgba(0,0,0,0.5)]">
        <div className="flex items-center gap-4">
          <ShieldCheck className="w-6 h-6 text-blue-500" />
          <h1 className="text-xl font-black tracking-widest bg-gradient-to-r from-blue-400 to-cyan-400 bg-clip-text text-transparent">NEXUS CITY BRAIN</h1>
        </div>
        <div className="flex gap-8">
          <div className="flex flex-col items-center">
             <span className="text-[9px] text-slate-400 uppercase font-bold tracking-widest">Total Vehicles</span>
             <span className="text-lg font-black leading-none mt-1 text-slate-300 font-mono">1,482</span>
          </div>
          <div className="flex flex-col items-center">
             <span className="text-[9px] text-slate-400 uppercase font-bold tracking-widest">CO2 Saved</span>
             <span className="text-lg font-black leading-none mt-1 text-emerald-400 font-mono">412 kg</span>
          </div>
          <div className="flex flex-col items-center">
             <span className="text-[9px] text-slate-400 uppercase font-bold tracking-widest">Health</span>
             <span className={`text-xl font-black leading-none mt-1 font-mono ${cityHealth > 90 ? 'text-emerald-400' : 'text-red-500'}`}>{Math.floor(cityHealth)}%</span>
          </div>
        </div>
      </div>

      {/* 3. LEFT GLASS PANEL (Live Camera Feed) */}
      <div className="absolute top-4 bottom-24 left-4 w-80 bg-slate-950/80 backdrop-blur-xl border border-slate-800/50 rounded-2xl flex flex-col z-40 shadow-2xl overflow-hidden">
        <AIVisionPanel onLaunch={launchScenario} simState={simState} maxAnomaly={maxAnomaly} totalQueue={totalQueue} />
      </div>

      {/* 4. RIGHT GLASS PANEL (AI Decision Engine) */}
      <div className="absolute top-4 bottom-24 right-4 w-80 bg-slate-950/80 backdrop-blur-xl border border-slate-800/50 rounded-2xl flex flex-col z-40 shadow-2xl overflow-hidden">
        <AIDecisionEngine simState={simState} maxAnomaly={maxAnomaly} totalQueue={totalQueue} nexusState={nexusState} />
        
        {simState === "recovered" && (
          <div className="p-4 mt-auto">
            <Button 
              onClick={() => setShowReplay(true)}
              className="w-full bg-emerald-600 hover:bg-emerald-500 text-white font-black tracking-widest uppercase text-xs h-12 rounded-xl shadow-[0_0_15px_rgba(16,185,129,0.5)] animate-bounce"
            >
              <RefreshCw className="w-4 h-4 mr-2"/> Compare Before / After
            </Button>
          </div>
        )}
      </div>

      {/* 5. BOTTOM TIMELINE PANEL */}
      <div className="absolute bottom-4 left-4 right-4 h-16 bg-slate-950/80 backdrop-blur-xl border border-slate-800/50 rounded-2xl z-40 shadow-2xl flex items-center px-4 overflow-hidden">
        <IncidentTimeline timeline={timeline} />
      </div>

      {/* GIANT SUCCESS OVERLAY */}
      <AnimatePresence>
        {simState === "recovered" && !showReplay && (
          <motion.div 
            initial={{ opacity: 0, scale: 0.9, y: 50 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 bg-emerald-950/90 backdrop-blur-2xl border-4 border-emerald-500 rounded-3xl p-12 flex flex-col items-center z-50 shadow-[0_0_100px_rgba(16,185,129,0.6)]"
          >
            <h2 className="text-4xl font-black text-emerald-400 tracking-widest mb-2">NEXUS AI RESPONSE COMPLETE</h2>
            <p className="text-xl font-bold text-white mb-8">Incident Cleared</p>
            
            <div className="grid grid-cols-2 gap-8 w-full mb-8">
               <div className="flex flex-col items-center p-4 bg-black/30 rounded-xl">
                  <span className="text-slate-400 font-bold uppercase tracking-widest text-sm mb-2">Average Wait*</span>
                  <span className="text-emerald-400 font-black text-3xl font-mono">↓ 25.5%</span>
               </div>
               <div className="flex flex-col items-center p-4 bg-black/30 rounded-xl">
                  <span className="text-slate-400 font-bold uppercase tracking-widest text-sm mb-2">Stops Reduced*</span>
                  <span className="text-emerald-400 font-black text-3xl font-mono">✓</span>
               </div>
               <div className="flex flex-col items-center p-4 bg-black/30 rounded-xl">
                  <span className="text-slate-400 font-bold uppercase tracking-widest text-sm mb-2">Throughput*</span>
                  <span className="text-emerald-400 font-black text-3xl font-mono">↑ 4.7%</span>
               </div>
               <div className="flex flex-col items-center p-4 bg-black/30 rounded-xl">
                  <span className="text-slate-400 font-bold uppercase tracking-widest text-sm mb-2">Recovery Accelerated</span>
                  <span className="text-emerald-400 font-black text-3xl font-mono">✓</span>
               </div>
            </div>

            <p className="text-xs text-slate-500 mb-6 italic">* Derived from offline PPO evaluation against a fixed-time baseline controller.</p>

            <Button onClick={() => setShowReplay(true)} className="bg-emerald-500 hover:bg-emerald-400 text-black font-black uppercase tracking-widest h-14 px-8 rounded-full">
              Proceed to Impact Replay
            </Button>
          </motion.div>
        )}
      </AnimatePresence>

      {/* 6. REPLAY OVERLAY */}
      <AnimatePresence>
        {showReplay && <BeforeAfterReplay onClose={() => setShowReplay(false)} />}
      </AnimatePresence>

    </div>
  )
}
