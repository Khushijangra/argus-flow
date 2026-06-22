"use client"

import { Activity } from "lucide-react"

interface IncidentTimelineProps {
  timeline: { time: string, msg: string, type: string }[];
}

export function IncidentTimeline({ timeline }: IncidentTimelineProps) {
  return (
    <div className="flex h-full w-full bg-slate-900 border-t border-slate-800 p-4">
      <div className="flex flex-col justify-center shrink-0 pr-8 border-r border-slate-800 mr-6">
        <span className="text-slate-500 text-[10px] font-black uppercase tracking-widest flex items-center gap-2">
          <Activity className="w-3 h-3"/> Incident Timeline
        </span>
      </div>
      
      <div className="flex flex-1 items-center gap-2 overflow-x-auto overflow-y-hidden px-2">
        {timeline.length === 0 ? (
          <span className="text-slate-600 font-medium italic text-sm">Awaiting scenario execution...</span>
        ) : (
          timeline.map((ev, i) => (
            <div key={i} className="flex items-center shrink-0">
              <div className={`flex flex-col border border-${ev.type}-500/30 bg-${ev.type}-950/30 px-4 py-2 rounded-lg animate-in fade-in slide-in-from-right-4`}>
                <span className="text-slate-500 text-[10px] font-mono font-bold mb-0.5">{ev.time}</span>
                <span className={`text-${ev.type}-400 text-xs font-bold whitespace-nowrap`}>{ev.msg}</span>
              </div>
              {i < timeline.length - 1 && (
                <div className="w-8 h-px bg-slate-700 mx-2 relative">
                  <div className="absolute right-0 top-1/2 -translate-y-1/2 w-1.5 h-1.5 border-t border-r border-slate-700 rotate-45"></div>
                </div>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  )
}
