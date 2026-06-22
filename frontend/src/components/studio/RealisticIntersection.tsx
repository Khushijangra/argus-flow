"use client"

import { useEffect, useState } from "react"
import { motion } from "framer-motion"
import { NexusState } from "@/hooks/useNexusStream"

interface RealisticIntersectionProps {
  nexusState: NexusState | null;
  simState: "none" | "detected" | "intervening" | "recovering" | "recovered";
}

export function RealisticIntersection({ nexusState, simState }: RealisticIntersectionProps) {
  
  const queueN = nexusState?.traffic.queue?.North || 0;
  const queueS = nexusState?.traffic.queue?.South || 0;
  const queueE = nexusState?.traffic.queue?.East || 0;
  const queueW = nexusState?.traffic.queue?.West || 0;
  const currentPhase = nexusState?.signals || "NS_GREEN";
  
  const isNSGreen = currentPhase.includes("NS") || currentPhase.includes("G");
  const isEWGreen = currentPhase.includes("EW") || currentPhase.includes("r");

  const [nsTimer, setNsTimer] = useState(15);
  const [ewTimer, setEwTimer] = useState(45);

  // Fake countdown timers that react to the "intervening" state
  useEffect(() => {
    if (simState === "intervening") {
      setNsTimer(38); // AI Extended!
    } else if (simState === "recovering") {
      setNsTimer(12);
    }
  }, [simState]);

  useEffect(() => {
    const int = setInterval(() => {
      setNsTimer(p => p > 0 ? p - 1 : (isNSGreen ? 45 : 15));
      setEwTimer(p => p > 0 ? p - 1 : (isEWGreen ? 45 : 15));
    }, 1000);
    return () => clearInterval(int);
  }, [isNSGreen, isEWGreen]);

  const getQueueColor = (q: number) => {
    if (simState === "recovering" || simState === "intervening") return "url(#grad-green)";
    if (q > 30) return "url(#grad-red)";
    if (q > 15) return "url(#grad-orange)";
    if (q > 5) return "url(#grad-yellow)";
    return "transparent";
  }

  const CarShape = ({ x, y, rotation, color = "#cc0000", isMoving = false }: { x: number, y: number, rotation: number, color?: string, isMoving?: boolean }) => (
    <motion.g 
      initial={{ x, y }} 
      animate={isMoving ? { x: x + (rotation === 0 ? 0 : rotation === 180 ? 0 : rotation === 90 ? -100 : 100), y: y + (rotation === 0 ? 100 : rotation === 180 ? -100 : 0) } : { x, y }}
      transition={isMoving ? { duration: 2 + Math.random(), repeat: Infinity, ease: "linear" } : {}}
      transform={`rotate(${rotation})`}
    >
      <rect x="-3" y="-6" width="6" height="12" fill={color} rx="1" className="drop-shadow-lg" />
      <rect x="-2.5" y="-4" width="5" height="3" fill="#111" rx="0.5" />
      <rect x="-2.5" y="1" width="5" height="4" fill="#111" rx="0.5" />
    </motion.g>
  );

  const renderQueue = (length: number, startX: number, startY: number, dx: number, dy: number, rotation: number, isGreen: boolean) => {
    const cars = [];
    // If it's recovering and green, cars are flushing (fewer visible, moving fast)
    const activeLength = (isGreen && (simState === "recovering" || simState === "recovered")) ? Math.floor(length * 0.3) : length;
    const numCars = Math.min(25, Math.floor(activeLength));
    
    for (let i = 0; i < numCars; i++) {
      const rx = (Math.random() - 0.5) * 1.5;
      const ry = (Math.random() - 0.5) * 1.5;
      const color = Math.random() > 0.8 ? "#333333" : (Math.random() > 0.5 ? "#ffffff" : "#cc0000");
      cars.push(<CarShape key={i} x={startX + i * dx + rx} y={startY + i * dy + ry} rotation={rotation} color={color} isMoving={isGreen && simState !== "detected"} />);
    }
    return cars;
  }

  return (
    <div className="absolute inset-0 w-full h-full bg-[#111625] overflow-hidden">
      
      {/* DISTRICT HONESTY TAG */}
      <div className="absolute top-24 left-1/2 -translate-x-1/2 flex gap-4 z-10 pointer-events-none">
         <div className="bg-slate-900/80 border border-slate-700 backdrop-blur px-4 py-1.5 rounded-full flex items-center gap-2 shadow-xl">
           <span className="text-[10px] font-black tracking-widest text-slate-300 uppercase">Smart Corridor Pilot</span>
         </div>
         <div className="bg-blue-900/80 border border-blue-500 backdrop-blur px-4 py-1.5 rounded-full flex items-center gap-2 shadow-[0_0_15px_rgba(59,130,246,0.5)]">
           <div className="w-2 h-2 rounded-full bg-blue-400 animate-pulse"></div>
           <span className="text-[10px] font-black tracking-widest text-blue-100 uppercase">J5 Live AI Control</span>
         </div>
      </div>

      <svg viewBox="0 0 1000 800" preserveAspectRatio="xMidYMid slice" className="w-full h-full">
        <defs>
          <linearGradient id="grad-red" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="rgba(239, 68, 68, 0.8)" />
            <stop offset="100%" stopColor="rgba(239, 68, 68, 0.0)" />
          </linearGradient>
          <linearGradient id="grad-orange" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="rgba(249, 115, 22, 0.8)" />
            <stop offset="100%" stopColor="rgba(249, 115, 22, 0.0)" />
          </linearGradient>
          <linearGradient id="grad-yellow" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="rgba(234, 179, 8, 0.6)" />
            <stop offset="100%" stopColor="rgba(234, 179, 8, 0.0)" />
          </linearGradient>
          <linearGradient id="grad-green" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="rgba(34, 197, 94, 0.6)" />
            <stop offset="100%" stopColor="rgba(34, 197, 94, 0.0)" />
          </linearGradient>
          
          <pattern id="grass" width="20" height="20" patternUnits="userSpaceOnUse">
             <rect width="20" height="20" fill="#1b2e24"/>
             <circle cx="10" cy="10" r="1" fill="#1e3a2b"/>
          </pattern>
        </defs>

        <g transform="translate(500, 420) scale(1.1, 0.65) rotate(45)">
          
          <rect x="-2000" y="-2000" width="4000" height="4000" fill="url(#grass)" />

          <rect x="-80" y="-1000" width="160" height="2000" fill="#2a2e39" />
          <rect x="-1000" y="-80" width="2000" height="160" fill="#2a2e39" />
          <rect x="-80" y="-80" width="160" height="160" fill="#2a2e39" />

          <path d="M 80 -150 Q 150 -150 150 -80 L 170 -80 Q 170 -170 80 -170 Z" fill="#2a2e39" />
          <path d="M 80 150 Q 150 150 150 80 L 170 80 Q 170 170 80 170 Z" fill="#2a2e39" />
          <path d="M -80 -150 Q -150 -150 -150 -80 L -170 -80 Q -170 -170 -80 -170 Z" fill="#2a2e39" />
          <path d="M -80 150 Q -150 150 -150 80 L -170 80 Q -170 170 -80 170 Z" fill="#2a2e39" />

          <rect x="-4" y="-1000" width="8" height="900" fill="#1e222b" />
          <rect x="-4" y="100" width="8" height="900" fill="#1e222b" />
          <rect x="-1000" y="-4" width="900" height="8" fill="#1e222b" />
          <rect x="100" y="-4" width="900" height="8" fill="#1e222b" />

          <g stroke="#ffffff" strokeWidth="2" strokeDasharray="10 15" opacity="0.4">
            <line x1="-40" y1="-1000" x2="-40" y2="-100" />
            <line x1="40" y1="-1000" x2="40" y2="-100" />
            <line x1="-40" y1="100" x2="-40" y2="1000" />
            <line x1="40" y1="100" x2="40" y2="1000" />
            
            <line x1="-1000" y1="-40" x2="-100" y2="-40" />
            <line x1="-1000" y1="40" x2="-100" y2="40" />
            <line x1="100" y1="-40" x2="1000" y2="-40" />
            <line x1="100" y1="40" x2="1000" y2="40" />
          </g>

          <g stroke="#ffffff" strokeWidth="6" strokeDasharray="8 8" opacity="0.8">
            <line x1="-80" y1="-90" x2="80" y2="-90" />
            <line x1="-80" y1="90" x2="80" y2="90" />
            <line x1="-90" y1="-80" x2="-90" y2="80" />
            <line x1="90" y1="-80" x2="90" y2="80" />
          </g>

          <rect x="-76" y="-500" width="72" height="400" fill={getQueueColor(queueN)} transform="rotate(180 0 -300)" opacity="0.8" style={{ transition: 'fill 1s ease' }}/>
          <rect x="4" y="100" width="72" height="400" fill={getQueueColor(queueS)} opacity="0.8" style={{ transition: 'fill 1s ease' }}/>
          <rect x="100" y="-76" width="400" height="72" fill={getQueueColor(queueE)} transform="rotate(90 300 0)" opacity="0.8" style={{ transition: 'fill 1s ease' }}/>
          <rect x="-500" y="4" width="400" height="72" fill={getQueueColor(queueW)} transform="rotate(-90 -300 0)" opacity="0.8" style={{ transition: 'fill 1s ease' }}/>

          <g>
            {renderQueue(queueN, -60, -120, 0, -20, 180, isNSGreen)}
            {renderQueue(queueN * 0.8, -20, -130, 0, -22, 180, isNSGreen)}
          </g>
          <g>
            {renderQueue(queueS, 20, 120, 0, 20, 0, isNSGreen)}
            {renderQueue(queueS * 0.6, 60, 140, 0, 24, 0, isNSGreen)}
          </g>
          <g>
            {renderQueue(queueE, 120, -60, 20, 0, -90, isEWGreen)}
            {renderQueue(queueE * 0.9, 130, -20, 22, 0, -90, isEWGreen)}
          </g>
          <g>
            {renderQueue(queueW, -120, 20, -20, 0, 90, isEWGreen)}
            {renderQueue(queueW * 0.5, -140, 60, -25, 0, 90, isEWGreen)}
          </g>

          {simState === "detected" && (
             <g transform="translate(-40, -150)">
               <motion.circle cx="0" cy="0" r="50" fill="none" stroke="#ef4444" strokeWidth="4" initial={{ scale: 0, opacity: 1 }} animate={{ scale: 3, opacity: 0 }} transition={{ repeat: Infinity, duration: 2 }} />
               <motion.circle cx="0" cy="0" r="25" fill="none" stroke="#ef4444" strokeWidth="8" initial={{ scale: 0, opacity: 1 }} animate={{ scale: 2, opacity: 0 }} transition={{ repeat: Infinity, duration: 2, delay: 0.5 }} />
               <rect x="-30" y="-10" width="60" height="20" fill="#ef4444" rx="4" transform="rotate(-45)" />
               <text x="0" y="0" fill="white" fontSize="12" fontWeight="black" textAnchor="middle" dominantBaseline="central" transform="rotate(-45)">SEVERITY 0.85</text>
             </g>
          )}

          {/* Glowing Target during Intervention */}
          {(simState === "intervening" || simState === "recovering") && (
            <motion.rect x="-80" y="-80" width="160" height="160" fill="none" stroke="#06b6d4" strokeWidth="4" initial={{ opacity: 0 }} animate={{ opacity: [0, 1, 0] }} transition={{ repeat: Infinity, duration: 1.5 }} />
          )}

          {/* Floating Signals with Countdowns */}
          <g transform="translate(-100, -100) rotate(-45)">
            <rect x="-30" y="-15" width="60" height="30" fill="#1e293b" rx="5" />
            <circle cx="-15" cy="0" r="8" fill={isNSGreen ? "#22c55e" : "#ef4444"} className="shadow-2xl" />
            <text x="10" y="0" fill="white" fontSize="16" fontWeight="bold" textAnchor="middle" dominantBaseline="central">{nsTimer}s</text>
            {simState === "intervening" && <text x="10" y="-20" fill="#22c55e" fontSize="12" fontWeight="black" textAnchor="middle" className="animate-bounce">+23s</text>}
          </g>

        </g>
      </svg>
    </div>
  )
}
