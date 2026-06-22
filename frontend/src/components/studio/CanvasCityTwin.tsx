"use client"

import { useEffect, useRef, useState } from "react"
import { NexusState } from "@/hooks/useNexusStream"

interface CanvasCityTwinProps {
  nexusState: NexusState | null;
  simState: "none" | "detected" | "intervening" | "recovering" | "recovered";
}

type Car = {
  id: number;
  x: number;
  y: number;
  dx: number;
  dy: number;
  speed: number;
  maxSpeed: number;
  color: string;
};

// 4x4 Grid coordinates
const V_ROADS = [200, 600, 1000, 1400];
const H_ROADS = [200, 500, 800, 1100];
const J5_X = 600; // The targeted junction
const J5_Y = 500;
const ROAD_WIDTH = 40;

export function CanvasCityTwin({ nexusState, simState }: CanvasCityTwinProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const carsRef = useRef<Car[]>([]);
  
  // Real State mapping
  const queueN = nexusState?.traffic.queue?.North || 0;
  const currentPhase = nexusState?.signals || "NS_GREEN";
  const isNSGreen = currentPhase.includes("NS") || currentPhase.includes("G");
  
  // Initialize cars once
  useEffect(() => {
    const cars: Car[] = [];
    const colors = ["#cbd5e1", "#f8fafc", "#94a3b8", "#ef4444", "#3b82f6", "#eab308"];
    
    // Spawn 300 ambient cars across all roads
    for (let i = 0; i < 300; i++) {
      const isVertical = Math.random() > 0.5;
      const roadX = V_ROADS[Math.floor(Math.random() * V_ROADS.length)];
      const roadY = H_ROADS[Math.floor(Math.random() * H_ROADS.length)];
      
      const dir = Math.random() > 0.5 ? 1 : -1;
      const laneOffset = dir === 1 ? 8 : -8; // drive on the right side of the road
      
      let x = isVertical ? roadX + laneOffset : Math.random() * 1920;
      let y = isVertical ? Math.random() * 1080 : roadY + laneOffset;
      
      cars.push({
        id: i,
        x,
        y,
        dx: isVertical ? 0 : dir,
        dy: isVertical ? dir : 0,
        speed: 1 + Math.random() * 2,
        maxSpeed: 1 + Math.random() * 2,
        color: colors[Math.floor(Math.random() * colors.length)]
      });
    }
    carsRef.current = cars;
  }, []);

  // Main Render Loop
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let animationId: number;

    const render = () => {
      // Clear canvas
      ctx.fillStyle = "#0f172a"; // Deep navy city background
      ctx.fillRect(0, 0, canvas.width, canvas.height);

      // 1. Draw Grid Roads
      ctx.fillStyle = "#1e293b";
      H_ROADS.forEach(y => ctx.fillRect(0, y - ROAD_WIDTH/2, canvas.width, ROAD_WIDTH));
      V_ROADS.forEach(x => ctx.fillRect(x - ROAD_WIDTH/2, 0, ROAD_WIDTH, canvas.height));

      // 2. Draw Intersections & Heatmaps
      H_ROADS.forEach(y => {
        V_ROADS.forEach(x => {
          const isJ5 = (x === J5_X && y === J5_Y);
          
          // Heatmap logic for J5
          if (isJ5 && simState !== "none" && simState !== "recovered") {
             const gradient = ctx.createRadialGradient(x, y, 10, x, y, 150);
             if (simState === "detected") {
               gradient.addColorStop(0, "rgba(239, 68, 68, 0.4)"); // Red jam
             } else if (simState === "intervening" || simState === "recovering") {
               gradient.addColorStop(0, "rgba(34, 197, 94, 0.4)"); // Green flush
             }
             gradient.addColorStop(1, "rgba(0, 0, 0, 0)");
             ctx.fillStyle = gradient;
             ctx.fillRect(x - 150, y - 150, 300, 300);
             
             // Draw Incident Marker
             if (simState === "detected") {
               ctx.beginPath();
               ctx.arc(x, y, 15 + Math.sin(Date.now() / 150) * 5, 0, Math.PI * 2);
               ctx.fillStyle = "rgba(239, 68, 68, 0.8)";
               ctx.fill();
               ctx.fillStyle = "#fff";
               ctx.font = "bold 14px monospace";
               ctx.textAlign = "center";
               ctx.fillText("ACCIDENT", x, y - 25);
             }
             
             // Draw Signals at J5
             ctx.fillStyle = isNSGreen ? "#22c55e" : "#ef4444"; // N-S lights
             ctx.beginPath(); ctx.arc(x - 10, y - 25, 4, 0, Math.PI * 2); ctx.fill();
             ctx.beginPath(); ctx.arc(x + 10, y + 25, 4, 0, Math.PI * 2); ctx.fill();
             
             ctx.fillStyle = isNSGreen ? "#ef4444" : "#22c55e"; // E-W lights
             ctx.beginPath(); ctx.arc(x - 25, y + 10, 4, 0, Math.PI * 2); ctx.fill();
             ctx.beginPath(); ctx.arc(x + 25, y - 10, 4, 0, Math.PI * 2); ctx.fill();
          } else {
             // Standard Intersection styling
             ctx.fillStyle = "#334155";
             ctx.fillRect(x - ROAD_WIDTH/2, y - ROAD_WIDTH/2, ROAD_WIDTH, ROAD_WIDTH);
          }
        });
      });

      // 3. Update & Draw Cars
      carsRef.current.forEach(car => {
        
        // --- LOGIC ---
        let currentSpeed = car.maxSpeed;
        
        const isApproachingJ5 = Math.abs(car.x - J5_X) < 200 && Math.abs(car.y - J5_Y) < 200;
        
        if (isApproachingJ5) {
          if (simState === "detected") {
             // Red light / Accident jam: Cars stop moving
             currentSpeed = 0.1; 
          } else if (simState === "intervening" || simState === "recovering") {
             // Green flush: Cars speed up massively if they match the green direction
             if ((car.dy !== 0 && isNSGreen) || (car.dx !== 0 && !isNSGreen)) {
               currentSpeed = car.maxSpeed * 2.5; 
             } else {
               currentSpeed = 0; // The other direction is stuck at red
             }
          }
        }

        // Apply speed
        car.x += car.dx * currentSpeed;
        car.y += car.dy * currentSpeed;

        // Loop boundaries
        if (car.x > canvas.width + 50) car.x = -50;
        if (car.x < -50) car.x = canvas.width + 50;
        if (car.y > canvas.height + 50) car.y = -50;
        if (car.y < -50) car.y = canvas.height + 50;

        // --- DRAWING ---
        ctx.fillStyle = car.color;
        ctx.beginPath();
        // Draw car aligned to direction
        if (car.dx !== 0) {
           ctx.roundRect(car.x - 6, car.y - 3, 12, 6, 2);
        } else {
           ctx.roundRect(car.x - 3, car.y - 6, 6, 12, 2);
        }
        ctx.fill();
        
        // Taillights
        ctx.fillStyle = currentSpeed < 0.5 ? "#ef4444" : "#991b1b"; // bright red if braking/stopped
        if (car.dx > 0) ctx.fillRect(car.x - 6, car.y - 2, 2, 4); // heading right, lights on left
        if (car.dx < 0) ctx.fillRect(car.x + 4, car.y - 2, 2, 4); // heading left, lights on right
        if (car.dy > 0) ctx.fillRect(car.x - 2, car.y - 6, 4, 2); // heading down, lights on top
        if (car.dy < 0) ctx.fillRect(car.x - 2, car.y + 4, 4, 2); // heading up, lights on bottom
      });

      animationId = requestAnimationFrame(render);
    };

    render();

    return () => cancelAnimationFrame(animationId);
  }, [simState, isNSGreen]);

  return (
    <div className="absolute inset-0 w-full h-full bg-[#0f172a] overflow-hidden">
      <canvas 
        ref={canvasRef} 
        width={1920} 
        height={1080} 
        className="w-full h-full object-cover opacity-90"
      />
      
      {/* HUD Overlays matching the command center aesthetic */}
      <div className="absolute top-24 left-1/2 -translate-x-1/2 flex gap-4 z-10 pointer-events-none">
         <div className="bg-slate-900/80 border border-slate-700 backdrop-blur px-4 py-1.5 rounded-full flex items-center gap-2 shadow-xl">
           <span className="text-[10px] font-black tracking-widest text-slate-300 uppercase">City Network Pilot</span>
         </div>
         <div className="bg-slate-900/80 border border-slate-700 backdrop-blur px-4 py-1.5 rounded-full flex items-center gap-2 shadow-xl">
           <span className="text-[10px] font-black tracking-widest text-slate-300 uppercase">Digital Twin Visualization (Mathematical State)</span>
         </div>
         <div className="bg-blue-900/80 border border-blue-500 backdrop-blur px-4 py-1.5 rounded-full flex items-center gap-2 shadow-[0_0_15px_rgba(59,130,246,0.5)]">
           <div className="w-2 h-2 rounded-full bg-blue-400 animate-pulse"></div>
           <span className="text-[10px] font-black tracking-widest text-blue-100 uppercase">J5 Live AI Control Active</span>
         </div>
      </div>
      
    </div>
  )
}
