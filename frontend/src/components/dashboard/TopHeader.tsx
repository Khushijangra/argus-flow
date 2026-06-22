"use client"

import { Card, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"

export function TopHeader() {
  return (
    <div className="grid grid-cols-5 gap-4 mb-4">
      <Card className="bg-slate-900 text-white border-slate-800">
        <CardContent className="p-4 flex flex-col items-center justify-center">
          <span className="text-slate-400 text-xs uppercase tracking-wider mb-1">Active Junctions</span>
          <span className="text-3xl font-bold text-blue-400">16</span>
        </CardContent>
      </Card>
      
      <Card className="bg-slate-900 text-white border-slate-800">
        <CardContent className="p-4 flex flex-col items-center justify-center">
          <span className="text-slate-400 text-xs uppercase tracking-wider mb-1">Incidents Detected</span>
          <span className="text-3xl font-bold text-red-500 animate-pulse">1</span>
        </CardContent>
      </Card>

      <Card className="bg-slate-900 text-white border-slate-800">
        <CardContent className="p-4 flex flex-col items-center justify-center">
          <span className="text-slate-400 text-xs uppercase tracking-wider mb-1">Vehicles Managed</span>
          <span className="text-3xl font-bold text-emerald-400">4,120/hr</span>
        </CardContent>
      </Card>

      <Card className="bg-slate-900 text-white border-slate-800">
        <CardContent className="p-4 flex flex-col items-center justify-center">
          <span className="text-slate-400 text-xs uppercase tracking-wider mb-1">Congestion Reduction</span>
          <span className="text-3xl font-bold text-green-500">28.4%</span>
        </CardContent>
      </Card>

      <Card className="bg-slate-900 text-white border-slate-800 relative overflow-hidden">
        <div className="absolute top-0 left-0 w-1 h-full bg-blue-500"></div>
        <CardContent className="p-4 flex flex-col items-center justify-center h-full">
          <span className="text-slate-400 text-xs uppercase tracking-wider mb-1">Current AI Status</span>
          <Badge variant="outline" className="text-blue-400 border-blue-400 animate-pulse bg-blue-950/30">
            OPTIMIZING J0_0
          </Badge>
        </CardContent>
      </Card>
    </div>
  )
}
