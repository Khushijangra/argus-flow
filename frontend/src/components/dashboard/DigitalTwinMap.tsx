"use client"

import { useEffect, useState } from "react"
import { motion } from "framer-motion"

export function DigitalTwinMap() {
  const [cars, setCars] = useState<{ id: number; path: string; duration: number }[]>([])

  useEffect(() => {
    // Generate some random cars moving along the roads
    const generateCars = () => {
      const newCars = Array.from({ length: 20 }).map((_, i) => {
        // Simple random paths on a cross layout
        const isHorizontal = Math.random() > 0.5;
        const dir = Math.random() > 0.5 ? 1 : -1;
        
        let d = "";
        if (isHorizontal) {
          const y = 48 + Math.random() * 4;
          d = dir > 0 ? `M 0 ${y} L 100 ${y}` : `M 100 ${y} L 0 ${y}`;
        } else {
          const x = 48 + Math.random() * 4;
          d = dir > 0 ? `M ${x} 0 L ${x} 100` : `M ${x} 100 L ${x} 0`;
        }

        return {
          id: i,
          path: d,
          duration: 3 + Math.random() * 4
        }
      });
      setCars(newCars);
    };

    generateCars();
    const interval = setInterval(generateCars, 4000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="relative w-full h-full bg-slate-950 rounded-xl border border-slate-800 overflow-hidden shadow-2xl">
      {/* Grid Background */}
      <div className="absolute inset-0" style={{ 
        backgroundImage: 'linear-gradient(rgba(255,255,255,0.03) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.03) 1px, transparent 1px)',
        backgroundSize: '20px 20px'
      }}></div>

      {/* SVG Map */}
      <svg viewBox="0 0 100 100" className="absolute inset-0 w-full h-full" preserveAspectRatio="none">
        {/* Roads */}
        <rect x="0" y="45" width="100" height="10" fill="#1e293b" />
        <rect x="45" y="0" width="10" height="100" fill="#1e293b" />
        
        {/* Road markings */}
        <line x1="0" y1="50" x2="45" y2="50" stroke="#fbbf24" strokeWidth="0.2" strokeDasharray="2 1" />
        <line x1="55" y1="50" x2="100" y2="50" stroke="#fbbf24" strokeWidth="0.2" strokeDasharray="2 1" />
        <line x1="50" y1="0" x2="50" y2="45" stroke="#fbbf24" strokeWidth="0.2" strokeDasharray="2 1" />
        <line x1="50" y1="55" x2="50" y2="100" stroke="#fbbf24" strokeWidth="0.2" strokeDasharray="2 1" />

        {/* Intersection center */}
        <rect x="45" y="45" width="10" height="10" fill="#0f172a" />

        {/* Incident highlight on North approach */}
        <motion.circle 
          cx="50" cy="25" r="15" 
          fill="rgba(239, 68, 68, 0.2)"
          animate={{ scale: [1, 1.2, 1], opacity: [0.5, 0.8, 0.5] }}
          transition={{ repeat: Infinity, duration: 2 }}
        />
        <text x="50" y="25" fill="#ef4444" fontSize="3" textAnchor="middle" fontWeight="bold" className="animate-pulse">INCIDENT DETECTED</text>
        
        {/* Cars */}
        {cars.map(car => (
          <motion.circle
            key={car.id}
            r="0.8"
            fill="#60a5fa"
            style={{
              offsetPath: `path('${car.path}')`,
              offsetRotate: 'auto'
            }}
            initial={{ offsetDistance: '0%' }}
            animate={{ offsetDistance: '100%' }}
            transition={{ duration: car.duration, ease: "linear" }}
          />
        ))}

        {/* Traffic Lights */}
        {/* North */}
        <circle cx="43" cy="43" r="1.5" fill="#22c55e" />
        {/* South */}
        <circle cx="57" cy="57" r="1.5" fill="#22c55e" />
        {/* East */}
        <circle cx="57" cy="43" r="1.5" fill="#ef4444" />
        {/* West */}
        <circle cx="43" cy="57" r="1.5" fill="#ef4444" />
      </svg>

      {/* Junction Overlay */}
      <div className="absolute top-4 left-4 bg-slate-900/80 backdrop-blur-sm border border-slate-700 p-3 rounded-lg text-xs">
        <h3 className="font-bold text-white mb-2 uppercase tracking-wider">J0_0 Status</h3>
        <div className="grid grid-cols-2 gap-x-4 gap-y-1">
          <span className="text-slate-400">Phase:</span>
          <span className="text-green-400 font-bold">NS_Through</span>
          <span className="text-slate-400">N Queue:</span>
          <span className="text-red-400 font-bold">14 veh</span>
          <span className="text-slate-400">E Queue:</span>
          <span className="text-slate-200">2 veh</span>
        </div>
      </div>
    </div>
  )
}
