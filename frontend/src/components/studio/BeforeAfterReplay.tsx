"use client"

import { useState } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { CanvasCityTwin } from "./CanvasCityTwin"
import { Button } from "@/components/ui/button"

interface BeforeAfterReplayProps {
  onClose: () => void;
}

export function BeforeAfterReplay({ onClose }: BeforeAfterReplayProps) {
  const [sliderPos, setSliderPos] = useState(50); // 0 to 100

  // Mock states to visually show the difference
  const mockWithoutAIState = {
    traffic: { queue: { North: 45, South: 40, East: 10, West: 10 } },
    anomalies: { North: 0.85, South: 0, East: 0, West: 0 },
    signals: "NS_RED",
    rl: null
  };

  const mockWithAIState = {
    traffic: { queue: { North: 15, South: 12, East: 5, West: 5 } },
    anomalies: { North: 0.0, South: 0, East: 0, West: 0 },
    signals: "NS_GREEN",
    rl: null
  };

  const handleDrag = (e: React.ChangeEvent<HTMLInputElement>) => {
    setSliderPos(Number(e.target.value));
  }

  return (
    <motion.div 
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="absolute inset-0 z-50 bg-slate-950 flex flex-col items-center justify-center p-8 backdrop-blur-md"
    >
      <div className="flex justify-between items-center w-full mb-6">
        <h2 className="text-2xl font-black text-white tracking-widest uppercase">Scenario Replay</h2>
        <Button onClick={onClose} className="bg-slate-800 hover:bg-slate-700 text-white font-bold">Return to Live Dashboard</Button>
      </div>

      <div className="relative w-full flex-1 rounded-2xl overflow-hidden shadow-2xl border-4 border-slate-800 select-none">
        
        {/* Layer 1: WITH AI (Background) */}
        <div className="absolute inset-0">
          <CanvasCityTwin nexusState={mockWithAIState as any} simState="recovered" />
          <div className="absolute top-6 right-6 bg-emerald-950/80 border border-emerald-500/50 backdrop-blur px-4 py-2 rounded-lg shadow-[0_0_20px_rgba(16,185,129,0.3)]">
            <span className="text-emerald-400 font-black tracking-widest text-lg uppercase">With NEXUS AI</span>
            <div className="flex gap-4 mt-2">
               <div className="flex flex-col"><span className="text-[10px] text-emerald-200 uppercase font-bold">Queue</span><span className="text-white font-mono text-xl">27</span></div>
               <div className="flex flex-col"><span className="text-[10px] text-emerald-200 uppercase font-bold">Wait</span><span className="text-white font-mono text-xl">92s</span></div>
            </div>
          </div>
        </div>

        {/* Layer 2: WITHOUT AI (Foreground Clipped) */}
        <div 
          className="absolute inset-0 pointer-events-none"
          style={{ clipPath: `polygon(0 0, ${sliderPos}% 0, ${sliderPos}% 100%, 0 100%)` }}
        >
          <CanvasCityTwin nexusState={mockWithoutAIState as any} simState="none" />
          <div className="absolute top-6 left-6 bg-red-950/80 border border-red-500/50 backdrop-blur px-4 py-2 rounded-lg shadow-[0_0_20px_rgba(239,68,68,0.3)] pointer-events-auto">
            <span className="text-red-400 font-black tracking-widest text-lg uppercase">Without AI</span>
            <div className="flex gap-4 mt-2">
               <div className="flex flex-col"><span className="text-[10px] text-red-200 uppercase font-bold">Queue</span><span className="text-white font-mono text-xl">85</span></div>
               <div className="flex flex-col"><span className="text-[10px] text-red-200 uppercase font-bold">Wait</span><span className="text-white font-mono text-xl">210s</span></div>
            </div>
          </div>
        </div>

        {/* The Slider Control */}
        <input 
          type="range" 
          min="0" max="100" 
          value={sliderPos}
          onChange={handleDrag}
          className="absolute inset-0 w-full h-full opacity-0 cursor-ew-resize z-20" 
        />

        {/* Visual Slider Line */}
        <div 
          className="absolute top-0 bottom-0 w-1 bg-white shadow-[0_0_10px_rgba(255,255,255,0.8)] z-10 pointer-events-none"
          style={{ left: `calc(${sliderPos}% - 2px)` }}
        >
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-8 h-8 bg-white rounded-full shadow-lg flex items-center justify-center">
            <div className="flex gap-1">
              <div className="w-1 h-3 bg-slate-300 rounded-full"></div>
              <div className="w-1 h-3 bg-slate-300 rounded-full"></div>
            </div>
          </div>
        </div>

      </div>
    </motion.div>
  )
}
