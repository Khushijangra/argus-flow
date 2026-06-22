"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { ArrowDown, Clock, Car, Activity } from "lucide-react"

export function OptimizationComparison() {
  return (
    <Card className="bg-slate-900 border-slate-800">
      <CardHeader className="pb-2">
        <CardTitle className="text-slate-200 text-sm uppercase tracking-wider">Signal Optimization Comparison</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-3 gap-4 text-sm mt-2">
          {/* Metrics Column */}
          <div className="flex flex-col gap-4 justify-end pb-2">
            <span className="text-slate-400 flex items-center gap-2"><Car className="w-4 h-4"/> Queue Length</span>
            <span className="text-slate-400 flex items-center gap-2"><Clock className="w-4 h-4"/> Waiting Time</span>
            <span className="text-slate-400 flex items-center gap-2"><Activity className="w-4 h-4"/> Avg Speed</span>
          </div>
          
          {/* Before AI */}
          <div className="flex flex-col gap-4 bg-slate-800/50 p-3 rounded-lg border border-slate-700">
            <span className="text-slate-300 text-xs uppercase text-center font-bold mb-1 border-b border-slate-700 pb-2">Without AI</span>
            <span className="text-red-400 text-center font-mono">28 veh</span>
            <span className="text-red-400 text-center font-mono">145s</span>
            <span className="text-orange-400 text-center font-mono">12 km/h</span>
          </div>

          {/* After AI */}
          <div className="flex flex-col gap-4 bg-emerald-900/20 p-3 rounded-lg border border-emerald-800/50">
            <span className="text-emerald-400 text-xs uppercase text-center font-bold mb-1 border-b border-emerald-800/50 pb-2">With AI</span>
            <span className="text-emerald-400 text-center font-mono flex items-center justify-center gap-1">
              12 veh <ArrowDown className="w-3 h-3"/>
            </span>
            <span className="text-emerald-400 text-center font-mono flex items-center justify-center gap-1">
              42s <ArrowDown className="w-3 h-3"/>
            </span>
            <span className="text-emerald-400 text-center font-mono flex items-center justify-center gap-1">
              28 km/h 
            </span>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
