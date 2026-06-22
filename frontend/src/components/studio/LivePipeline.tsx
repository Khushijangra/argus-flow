"use client"

import { motion } from "framer-motion"
import { ArrowRight, Video, BrainCircuit, Activity, Cpu, TrafficCone, Map } from "lucide-react"

export function LivePipeline() {
  const steps = [
    { id: "cam", label: "CAMERA", icon: <Video className="w-4 h-4" /> },
    { id: "detect", label: "INCIDENT DETECTION", icon: <Activity className="w-4 h-4" /> },
    { id: "analysis", label: "TRAFFIC ANALYSIS", icon: <Map className="w-4 h-4" /> },
    { id: "ai", label: "AI DECISION", icon: <BrainCircuit className="w-4 h-4" /> },
    { id: "signal", label: "SIGNAL OPTIMIZATION", icon: <Cpu className="w-4 h-4" /> },
    { id: "recovery", label: "TRAFFIC RECOVERY", icon: <TrafficCone className="w-4 h-4" /> }
  ]

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 w-full">
      <div className="flex justify-between items-center text-xs text-slate-400 mb-4 uppercase tracking-wider font-bold">
        <span>NEXUS End-to-End Pipeline</span>
        <span className="text-blue-400 animate-pulse">Running</span>
      </div>
      <div className="flex items-center justify-between">
        {steps.map((step, i) => (
          <div key={step.id} className="flex items-center">
            <motion.div
              initial={{ opacity: 0.5, borderColor: "#1e293b" }}
              animate={{ 
                opacity: [0.5, 1, 0.5],
                borderColor: ["#1e293b", "#3b82f6", "#1e293b"],
                boxShadow: ["0 0 0px rgba(59,130,246,0)", "0 0 15px rgba(59,130,246,0.5)", "0 0 0px rgba(59,130,246,0)"]
              }}
              transition={{ repeat: Infinity, duration: 2.5, delay: i * 0.4 }}
              className="flex flex-col items-center gap-2 bg-slate-950 border-2 px-3 py-2 rounded-lg min-w-[120px]"
            >
              <div className="text-blue-400">{step.icon}</div>
              <span className="text-[10px] font-bold text-slate-200 text-center uppercase">{step.label}</span>
            </motion.div>
            
            {i < steps.length - 1 && (
              <motion.div 
                className="mx-2 text-slate-600"
                animate={{ color: ["#475569", "#3b82f6", "#475569"] }}
                transition={{ repeat: Infinity, duration: 2.5, delay: (i * 0.4) + 0.2 }}
              >
                <ArrowRight className="w-5 h-5" />
              </motion.div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
