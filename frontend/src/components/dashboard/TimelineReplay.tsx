"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { motion } from "framer-motion"

const timelineEvents = [
  { time: "14:23:10", label: "Incident Detected", color: "text-red-400" },
  { time: "14:23:12", label: "Severity Generated", color: "text-orange-400" },
  { time: "14:23:13", label: "Hybrid State Updated", color: "text-blue-400" },
  { time: "14:23:15", label: "RL Decision Made", color: "text-purple-400" },
  { time: "14:23:16", label: "Signal Updated", color: "text-emerald-400" }
]

export function TimelineReplay() {
  return (
    <Card className="bg-slate-900 border-slate-800">
      <CardHeader className="pb-2">
        <CardTitle className="text-slate-200 text-sm uppercase tracking-wider">Timeline Replay</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex justify-between items-center relative mt-4">
          <div className="absolute top-1/2 left-0 w-full h-0.5 bg-slate-800 -z-10"></div>
          {timelineEvents.map((ev, i) => (
            <motion.div 
              key={i} 
              className="flex flex-col items-center gap-2 bg-slate-900 px-2"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.5, duration: 0.5 }}
            >
              <div className={`w-3 h-3 rounded-full ${ev.color.replace('text-', 'bg-')} ring-4 ring-slate-900`} />
              <span className={`text-xs font-bold ${ev.color}`}>{ev.time}</span>
              <span className="text-[10px] text-slate-400 uppercase max-w-[80px] text-center">{ev.label}</span>
            </motion.div>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}
