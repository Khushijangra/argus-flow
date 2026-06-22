"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { motion } from "framer-motion"
import { AlertTriangle, Camera, Activity, AlertCircle } from "lucide-react"

export function IncidentPanel() {
  return (
    <Card className="bg-slate-900 border-red-500/50 shadow-[0_0_15px_rgba(239,68,68,0.2)] overflow-hidden relative">
      <div className="absolute top-0 left-0 w-full h-1 bg-red-500 animate-pulse"></div>
      <CardHeader className="pb-2">
        <CardTitle className="text-red-500 flex items-center gap-2 text-sm uppercase tracking-wider">
          <AlertTriangle className="w-5 h-5 animate-pulse" />
          Active Incident Detected
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 gap-4">
          <div className="flex flex-col gap-1">
            <span className="text-slate-400 text-xs flex items-center gap-1"><Camera className="w-3 h-3"/> Camera ID</span>
            <span className="text-slate-100 font-mono text-sm">CAM_N_01</span>
          </div>
          <div className="flex flex-col gap-1">
            <span className="text-slate-400 text-xs flex items-center gap-1"><Activity className="w-3 h-3"/> Severity Score</span>
            <span className="text-red-400 font-bold text-lg">0.85 / 1.0</span>
          </div>
          <div className="flex flex-col gap-1">
            <span className="text-slate-400 text-xs">Current Queue</span>
            <span className="text-orange-400 font-mono text-sm">14 vehicles</span>
          </div>
          <div className="flex flex-col gap-1">
            <span className="text-slate-400 text-xs flex items-center gap-1"><AlertCircle className="w-3 h-3"/> Expected Impact</span>
            <span className="text-red-400 font-mono text-sm">High Congestion</span>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
