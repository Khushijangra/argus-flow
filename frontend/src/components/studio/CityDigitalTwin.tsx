"use client"

import { useEffect, useState } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { NexusState } from "@/hooks/useNexusStream"

interface CityDigitalTwinProps {
  nexusState: NexusState | null;
  simState: "none" | "detected" | "intervening" | "recovering" | "recovered";
  isReplayMode?: boolean;
}

type Vehicle = {
  id: number;
  path: string;
  duration: number;
  type: "car" | "truck" | "ambulance" | "police";
  color: string;
}

// 9-Junction Grid Coordinates
// J1 (20,20)   J2 (50,20)   J3 (80,20)
// J4 (20,50)   J5 (50,50)   J6 (80,50)  <-- J5 is the LIVE RL Junction
// J7 (20,80)   J8 (50,80)   J9 (80,80)

export function CityDigitalTwin({ nexusState, simState, isReplayMode = false }: CityDigitalTwinProps) {
  const [vehicles, setVehicles] = useState<Vehicle[]>([])

  // Live J5 Data
  const queueLengthN = nexusState?.traffic.queue?.North || 0;
  const severityN = nexusState?.anomalies?.North || 0.0;
  const currentPhase = nexusState?.signals || "NS_GREEN";
  const totalQueue = Object.values(nexusState?.traffic.queue || {}).reduce((a, b) => a + b, 0);

  // Vehicle Generation Heuristics
  useEffect(() => {
    if (isReplayMode) return; // Replay mode uses static snapshot
    
    let vId = 0;
    const generateVehicle = () => {
      vId++;
      
      // We will define a few major arterial routes through the city
      const routes = [
        // Main N-S Arterial passing through J5 (50, y)
        "M 52 0 L 52 100", // North to South
        "M 48 100 L 48 0", // South to North
        
        // Main E-W Arterial passing through J5 (x, 50)
        "M 0 48 L 100 48", // West to East
        "M 100 52 L 0 52", // East to West

        // Outer ambient routes
        "M 22 0 L 22 100", // J1-J4-J7 NS
        "M 18 100 L 18 0",
        "M 0 18 L 100 18", // J1-J2-J3 EW
        "M 100 22 L 0 22",

        "M 82 0 L 82 100", // J3-J6-J9 NS
        "M 78 100 L 78 0",
        "M 0 78 L 100 78", // J7-J8-J9 EW
        "M 100 82 L 0 82",
      ];

      const path = routes[Math.floor(Math.random() * routes.length)];
      
      // Central bottleneck logic
      const isCentralRoute = path.includes("52") || path.includes("48");
      
      // If AI hasn't intervened yet, cars stop spawning / get stuck on central route
      if (isCentralRoute && (simState === "detected" || simState === "none") && totalQueue > 30 && Math.random() > 0.2) return;

      let type: "car" | "truck" = Math.random() > 0.85 ? "truck" : "car";
      let color = type === "truck" ? "#475569" : "#cbd5e1";
      
      // Speed dynamics
      let duration = 12 + Math.random() * 5; // Ambient slow movement across large city
      if (isCentralRoute && simState === "recovering") duration = duration * 0.6; // FAST flush
      if (isCentralRoute && simState === "detected") duration = duration * 2.5; // SLOW crawl

      setVehicles(prev => [...prev.slice(-60), { id: vId, path, duration, type, color }]);
    };

    const interval = setInterval(generateVehicle, (simState === "intervening" || simState === "recovering") ? 200 : 500);
    return () => clearInterval(interval);
  }, [totalQueue, currentPhase, simState, isReplayMode]);

  // Inject Emergency Vehicles during incident
  useEffect(() => {
    if (simState === "detected" && severityN > 0.3) {
      setVehicles(prev => [...prev, 
        { id: 8888, path: "M 52 0 L 52 42", duration: 4, type: "police", color: "#3b82f6" },
        { id: 9999, path: "M 52 0 L 52 45", duration: 5, type: "ambulance", color: "#ffffff" }
      ]);
    }
  }, [simState, severityN]);

  // Congestion Heatmap colors
  const getCentralHeat = () => {
    if (simState === "recovering" || simState === "intervening") return "#166534"; // Healing
    if (totalQueue < 10) return "#1e293b"; // Normal
    if (totalQueue < 25) return "#ca8a04"; // Yellow
    if (totalQueue < 50) return "#ea580c"; // Orange
    return "#dc2626"; // Red Incident
  };

  const getVehicleSVG = (v: Vehicle) => {
    if (v.type === "car") {
      return (
        <g>
          <rect x="-0.8" y="-1.5" width="1.6" height="3" fill={v.color} rx="0.3" />
          <rect x="-0.5" y="-0.8" width="1" height="1.5" fill="#0f172a" rx="0.1" /> 
        </g>
      )
    }
    if (v.type === "truck") {
      return (
        <g>
          <rect x="-1" y="-2" width="2" height="4" fill={v.color} rx="0.3" />
          <rect x="-0.8" y="-1.8" width="1.6" height="1" fill="#94a3b8" /> 
        </g>
      )
    }
    if (v.type === "ambulance") {
      return (
        <g>
          <rect x="-1" y="-2" width="2" height="4" fill="#ffffff" rx="0.3" />
          <rect x="-0.2" y="-1" width="0.4" height="2" fill="#ef4444" /> 
          <rect x="-0.8" y="-0.2" width="1.6" height="0.4" fill="#ef4444" /> 
          <circle cx="0" cy="-1.8" r="0.4" fill="#ef4444" className="animate-pulse" /> 
        </g>
      )
    }
    if (v.type === "police") {
      return (
        <g>
          <rect x="-0.8" y="-1.5" width="1.6" height="3" fill="#0f172a" rx="0.3" />
          <rect x="-0.8" y="-0.5" width="1.6" height="1" fill="#ffffff" /> 
          <circle cx="-0.4" cy="-0.8" r="0.3" fill="#ef4444" className="animate-pulse" /> 
          <circle cx="0.4" cy="-0.8" r="0.3" fill="#3b82f6" className="animate-[pulse_1s_infinite_100ms]" /> 
        </g>
      )
    }
  }

  // Helper for drawing junctions
  const Junction = ({ x, y, isLive = false }: { x: number, y: number, isLive?: boolean }) => {
    const isNSGreen = isLive ? (currentPhase.includes("NS") || currentPhase.includes("G")) : Math.random() > 0.5;
    const isEWGreen = isLive ? (currentPhase.includes("EW") || currentPhase.includes("r")) : !isNSGreen;

    return (
      <g transform={`translate(${x}, ${y})`}>
        <rect x="-4" y="-4" width="8" height="8" fill="#1e293b" />
        
        {/* Lights */}
        {/* North */}
        <circle cx="-1" cy="-3.5" r="0.6" fill={isNSGreen ? "#22c55e" : "#ef4444"} className="shadow-lg" />
        {/* South */}
        <circle cx="1" cy="3.5" r="0.6" fill={isNSGreen ? "#22c55e" : "#ef4444"} />
        {/* East */}
        <circle cx="3.5" cy="-1" r="0.6" fill={isEWGreen ? "#22c55e" : "#ef4444"} />
        {/* West */}
        <circle cx="-3.5" cy="1" r="0.6" fill={isEWGreen ? "#22c55e" : "#ef4444"} />

        {/* Live Queue Buildup Animation on J5 */}
        {isLive && queueLengthN > 0 && Array.from({ length: Math.min(15, Math.floor(queueLengthN)) }).map((_, i) => (
          <g key={`q-n-${i}`} transform={`translate(2, ${-6 - i * 3.5})`}>
            <rect x="-0.8" y="-1.5" width="1.6" height="3" fill="#ef4444" rx="0.3" />
            <rect x="-0.5" y="-0.8" width="1" height="1.5" fill="#0f172a" rx="0.1" /> 
          </g>
        ))}

        {/* Live Incident Overlays */}
        {isLive && simState === "detected" && (
          <g transform="translate(2, -15)">
            <motion.circle cx="0" cy="0" r="5" fill="none" stroke="#ef4444" strokeWidth="0.5" initial={{ scale: 0, opacity: 1 }} animate={{ scale: 3, opacity: 0 }} transition={{ repeat: Infinity, duration: 1.5 }} />
            <motion.circle cx="0" cy="0" r="2.5" fill="none" stroke="#ef4444" strokeWidth="1" initial={{ scale: 0, opacity: 1 }} animate={{ scale: 2, opacity: 0 }} transition={{ repeat: Infinity, duration: 1.5, delay: 0.5 }} />
            <text x="0" y="0" fontSize="4" textAnchor="middle" dominantBaseline="central" className="animate-pulse drop-shadow-xl">💥</text>
          </g>
        )}
      </g>
    )
  }

  return (
    <div className="relative w-full h-full bg-slate-950 overflow-hidden rounded-2xl shadow-2xl border border-slate-800">
      <svg viewBox="0 0 100 100" className="absolute inset-0 w-full h-full">
        {/* Ground grid */}
        <pattern id="grid" width="10" height="10" patternUnits="userSpaceOnUse">
          <path d="M 10 0 L 0 0 0 10" fill="none" stroke="#0f172a" strokeWidth="0.2"/>
        </pattern>
        <rect width="100%" height="100%" fill="url(#grid)" />

        {/* --- HEATMAP UNDERLAYS --- */}
        {/* Central N-S Arterial Heatmap */}
        <rect x="46" y="0" width="8" height="100" fill={getCentralHeat()} style={{ transition: 'fill 2s ease' }} opacity="0.3"/>
        {/* Central E-W Arterial Heatmap */}
        <rect x="0" y="46" width="100" height="8" fill={getCentralHeat()} style={{ transition: 'fill 2s ease' }} opacity="0.3"/>

        {/* --- ROADS --- */}
        {/* N-S Roads */}
        <rect x="16" y="0" width="8" height="100" fill="#1e293b" />
        <rect x="46" y="0" width="8" height="100" fill="#1e293b" />
        <rect x="76" y="0" width="8" height="100" fill="#1e293b" />
        {/* E-W Roads */}
        <rect x="0" y="16" width="100" height="8" fill="#1e293b" />
        <rect x="0" y="46" width="100" height="8" fill="#1e293b" />
        <rect x="0" y="76" width="100" height="8" fill="#1e293b" />

        {/* Centerlines */}
        <path d="M 20 0 L 20 100 M 50 0 L 50 100 M 80 0 L 80 100 M 0 20 L 100 20 M 0 50 L 100 50 M 0 80 L 100 80" stroke="#fbbf24" strokeWidth="0.2" strokeDasharray="1 1" fill="none" />

        {/* --- 9 JUNCTIONS --- */}
        <Junction x={20} y={20} />
        <Junction x={50} y={20} />
        <Junction x={80} y={20} />
        
        <Junction x={20} y={50} />
        <Junction x={50} y={50} isLive={true} /> {/* J5 - The Core RL Junction */}
        <Junction x={80} y={50} />
        
        <Junction x={20} y={80} />
        <Junction x={50} y={80} />
        <Junction x={80} y={80} />

        {/* --- MOVING VEHICLES --- */}
        {vehicles.map(v => (
          <motion.g
            key={`${v.id}`}
            style={{ offsetPath: `path('${v.path}')`, offsetRotate: 'auto' }}
            initial={{ offsetDistance: '0%' }}
            animate={{ offsetDistance: '100%' }}
            transition={{ duration: v.duration, ease: "linear" }}
          >
            {getVehicleSVG(v)}
          </motion.g>
        ))}

        {/* LIVE RL Overlay Tag on J5 */}
        <g transform="translate(56, 44)">
           <rect x="0" y="0" width="12" height="4" fill="#3b82f6" rx="0.5" />
           <text x="6" y="2" fill="white" fontSize="2" fontWeight="bold" textAnchor="middle" dominantBaseline="central">LIVE AI J5</text>
        </g>
      </svg>
    </div>
  )
}
