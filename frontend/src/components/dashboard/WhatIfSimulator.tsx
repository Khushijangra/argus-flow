"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Play } from "lucide-react"

export function WhatIfSimulator() {
  return (
    <Card className="bg-slate-900 border-slate-800">
      <CardHeader className="pb-2">
        <CardTitle className="text-slate-200 text-sm uppercase tracking-wider">What-If Simulator</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <div className="grid grid-cols-2 gap-4">
          <div className="flex flex-col gap-1">
            <span className="text-xs text-slate-400 uppercase">Inject Event</span>
            <select className="bg-slate-950 border border-slate-700 rounded p-1.5 text-sm text-slate-200 outline-none">
              <option>Major Accident</option>
              <option>Ambulance Routing</option>
              <option>Pedestrian Crowd</option>
            </select>
          </div>
          <div className="flex flex-col gap-1">
            <span className="text-xs text-slate-400 uppercase">Junction</span>
            <select className="bg-slate-950 border border-slate-700 rounded p-1.5 text-sm text-slate-200 outline-none">
              <option>J0_0 (North)</option>
              <option>J1_1 (East)</option>
            </select>
          </div>
        </div>
        
        <div className="flex flex-col gap-1">
          <span className="text-xs text-slate-400 uppercase flex justify-between">
            Severity <span className="text-red-400 font-bold">0.85</span>
          </span>
          <input type="range" min="0" max="1" step="0.05" defaultValue="0.85" className="w-full accent-blue-500" />
        </div>

        <Button className="w-full bg-blue-600 hover:bg-blue-700 text-white font-bold gap-2">
          <Play className="w-4 h-4"/> RUN SIMULATION
        </Button>
      </CardContent>
    </Card>
  )
}
