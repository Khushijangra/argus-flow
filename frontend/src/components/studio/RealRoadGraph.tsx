"use client"

import { useEffect, useState } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { NexusState } from "@/hooks/useNexusStream"

interface RealRoadGraphProps {
  nexusState: NexusState | null;
  scenarioType: "accident" | "ambulance";
  simState: "none" | "detected" | "intervening" | "recovering" | "recovered";
}

type VehicleType = "car" | "truck" | "ambulance" | "police";

interface Vehicle {
  id: number;
  path: string;
  duration: number;
  type: VehicleType;
  color: string;
}

export function RealRoadGraph({ nexusState, scenarioType, simState }: RealRoadGraphProps) {
  const [vehicles, setVehicles] = useState<Vehicle[]>([])

  const queueLengthN = nexusState?.traffic.queue?.North || 0;
  const queueLengthS = nexusState?.traffic.queue?.South || 0;
  const queueLengthE = nexusState?.traffic.queue?.East || 0;
  const queueLengthW = nexusState?.traffic.queue?.West || 0;
  
  const totalQueue = queueLengthN + queueLengthS + queueLengthE + queueLengthW;
  
  const severityN = nexusState?.anomalies?.North || 0.0;
  const severityS = nexusState?.anomalies?.South || 0.0;
  const maxSeverity = Math.max(severityN, severityS, 0.0);

  const currentPhase = nexusState?.signals || "NS_GREEN";
  
  // A heuristic simulation of cars based on real queue
  useEffect(() => {
    let vId = 0;
    const generateVehicle = () => {
      vId++;
      const paths = [
        "M 53 -20 L 53 120", // North to South
        "M 47 120 L 47 -20", // South to North
        "M -20 47 L 120 47", // West to East
        "M 120 53 L -20 53"  // East to West
      ];
      const path = paths[Math.floor(Math.random() * paths.length)];
      
      // Stop spawning if severely congested in that specific simState
      if ((simState === "detected" || simState === "none") && totalQueue > 40 && Math.random() > 0.3) return;

      const rand = Math.random();
      let type: VehicleType = "car";
      let color = "#cbd5e1"; // default car color
      let duration = 6 + Math.random() * 4;

      if (rand > 0.85) {
        type = "truck";
        color = "#475569";
        duration += 2; // trucks are slower
      }

      if (simState === "recovering" && currentPhase.includes("NS")) {
          duration = duration * 0.5; // moving faster during recovery
      } else if (simState === "detected") {
          duration = duration * 2; // moving slower when accident detected
      }

      const newV: Vehicle = {
        id: vId,
        path,
        duration,
        type,
        color
      };
      
      setVehicles(prev => [...prev.slice(-30), newV]);
    };

    const interval = setInterval(generateVehicle, (simState === "intervening" || simState === "recovering") ? 300 : 800);
    return () => clearInterval(interval);
  }, [totalQueue, currentPhase, simState]);

  // Inject Emergency Vehicles
  useEffect(() => {
    if (simState === "detected" && maxSeverity > 0.3) {
      // Add Police
      setVehicles(prev => [...prev, {
        id: 8888,
        path: "M 53 -20 L 53 35", // stops at incident
        duration: 3,
        type: "police",
        color: "#3b82f6"
      }]);
      // Add Ambulance
      setTimeout(() => {
        setVehicles(prev => [...prev, {
          id: 9999,
          path: "M 53 -20 L 53 38", // stops slightly behind
          duration: 4,
          type: "ambulance",
          color: "#ffffff"
        }]);
      }, 1500);
    }
  }, [simState, maxSeverity]);

  // Density Color based on real queue
  const getRoadColor = () => {
    if (simState === "recovering" || simState === "intervening") return "#166534"; // Healing Green
    if (totalQueue < 5) return "#334155"; // Normal dark gray
    if (totalQueue < 15) return "#ca8a04"; // Yellow
    if (totalQueue < 30) return "#ea580c"; // Orange
    return "#dc2626"; // Red
  };

  const roadGlow = getRoadColor();

  const getVehicleSVG = (v: Vehicle) => {
    if (v.type === "car") {
      return (
        <g>
          <rect x="-1.5" y="-3" width="3" height="6" fill={v.color} rx="0.5" />
          <rect x="-1" y="-1.5" width="2" height="3" fill="#1e293b" rx="0.2" /> {/* Roof/windows */}
        </g>
      )
    }
    if (v.type === "truck") {
      return (
        <g>
          <rect x="-2" y="-4" width="4" height="8" fill={v.color} rx="0.5" />
          <rect x="-1.5" y="-3.5" width="3" height="2" fill="#94a3b8" /> {/* Cab */}
        </g>
      )
    }
    if (v.type === "ambulance") {
      return (
        <g>
          <rect x="-2" y="-4" width="4" height="8" fill="#ffffff" rx="0.5" />
          <rect x="-0.5" y="-2" width="1" height="4" fill="#ef4444" /> {/* Red cross V */}
          <rect x="-1.5" y="-0.5" width="3" height="1" fill="#ef4444" /> {/* Red cross H */}
          <circle cx="0" cy="-3.5" r="0.8" fill="#ef4444" className="animate-pulse" /> {/* Siren */}
        </g>
      )
    }
    if (v.type === "police") {
      return (
        <g>
          <rect x="-1.5" y="-3" width="3" height="6" fill="#1e293b" rx="0.5" />
          <rect x="-1.5" y="-1" width="3" height="2" fill="#ffffff" /> {/* White doors */}
          <circle cx="-0.8" cy="-1.5" r="0.6" fill="#ef4444" className="animate-pulse" /> {/* Red siren */}
          <circle cx="0.8" cy="-1.5" r="0.6" fill="#3b82f6" className="animate-[pulse_1s_infinite_100ms]" /> {/* Blue siren */}
        </g>
      )
    }
  }

  return (
    <div className="relative w-full h-full bg-slate-950 overflow-hidden">
      {/* Background City Grid */}
      <svg viewBox="0 0 100 100" className="absolute inset-0 w-full h-full opacity-30">
        <pattern id="grid" width="20" height="20" patternUnits="userSpaceOnUse">
          <path d="M 20 0 L 0 0 0 20" fill="none" stroke="#334155" strokeWidth="0.5"/>
        </pattern>
        <rect width="100%" height="100%" fill="url(#grid)" />
        
        {/* Abstract Buildings */}
        <rect x="10" y="10" width="25" height="25" fill="#0f172a" stroke="#1e293b" />
        <rect x="65" y="10" width="25" height="25" fill="#0f172a" stroke="#1e293b" />
        <rect x="10" y="65" width="25" height="25" fill="#0f172a" stroke="#1e293b" />
        <rect x="65" y="65" width="25" height="25" fill="#0f172a" stroke="#1e293b" />
      </svg>

      {/* Main Arterial Roads */}
      <svg viewBox="0 0 100 100" className="absolute inset-0 w-full h-full">
        {/* Glow effect on entire road network based on congestion/AI state */}
        <rect x="40" y="-20" width="20" height="140" fill={roadGlow} style={{ transition: 'fill 2s ease' }} opacity="0.4"/>
        <rect x="-20" y="40" width="140" height="20" fill={roadGlow} style={{ transition: 'fill 2s ease' }} opacity="0.4"/>
        
        {/* Base Roads */}
        <rect x="40" y="-20" width="20" height="140" fill="#1e293b" />
        <rect x="-20" y="40" width="140" height="20" fill="#1e293b" />
        
        {/* Road Centerlines */}
        <line x1="50" y1="-20" x2="50" y2="40" stroke="#fbbf24" strokeWidth="0.5" strokeDasharray="3 3" />
        <line x1="50" y1="60" x2="50" y2="120" stroke="#fbbf24" strokeWidth="0.5" strokeDasharray="3 3" />
        <line x1="-20" y1="50" x2="40" y2="50" stroke="#fbbf24" strokeWidth="0.5" strokeDasharray="3 3" />
        <line x1="60" y1="50" x2="120" y2="50" stroke="#fbbf24" strokeWidth="0.5" strokeDasharray="3 3" />

        {/* Intersection Box */}
        <rect x="40" y="40" width="20" height="20" fill="#1e293b" />

        {/* Traffic Lights */}
        {/* North */}
        <circle cx="38" cy="38" r="2" fill={currentPhase.includes("NS") || currentPhase.includes("G") ? "#22c55e" : "#ef4444"} className="shadow-lg"/>
        {/* South */}
        <circle cx="62" cy="62" r="2" fill={currentPhase.includes("NS") || currentPhase.includes("G") ? "#22c55e" : "#ef4444"} />
        {/* East */}
        <circle cx="62" cy="38" r="2" fill={currentPhase.includes("EW") || currentPhase.includes("r") ? "#22c55e" : "#ef4444"} />
        {/* West */}
        <circle cx="38" cy="62" r="2" fill={currentPhase.includes("EW") || currentPhase.includes("r") ? "#22c55e" : "#ef4444"} />

        {/* Queued Cars (Visual Stop) */}
        {/* North Approach Queue */}
        {Array.from({ length: Math.min(10, Math.floor(queueLengthN)) }).map((_, i) => (
          <g key={`q-n-${i}`} transform={`translate(47, ${35 - i * 7})`}>
            <rect x="-1.5" y="-3" width="3" height="6" fill="#ef4444" rx="0.5" />
            <rect x="-1" y="-1.5" width="2" height="3" fill="#1e293b" rx="0.2" />
          </g>
        ))}

        {/* Moving Vehicles */}
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

        {/* Incident Visuals */}
        {maxSeverity > 0.05 && scenarioType === "accident" && (
          <g transform="translate(53, 25)">
            {/* Pulsing Red Beacon */}
            <motion.circle cx="0" cy="0" r="10" fill="none" stroke="#ef4444" strokeWidth="1" initial={{ scale: 0, opacity: 1 }} animate={{ scale: 3, opacity: 0 }} transition={{ repeat: Infinity, duration: 1.5 }} />
            <motion.circle cx="0" cy="0" r="5" fill="none" stroke="#ef4444" strokeWidth="2" initial={{ scale: 0, opacity: 1 }} animate={{ scale: 2, opacity: 0 }} transition={{ repeat: Infinity, duration: 1.5, delay: 0.5 }} />
            
            {/* Crash Icon 💥 */}
            <text x="0" y="0" fontSize="12" textAnchor="middle" dominantBaseline="central" className="animate-pulse drop-shadow-xl">💥</text>
          </g>
        )}
      </svg>
    </div>
  )
}
