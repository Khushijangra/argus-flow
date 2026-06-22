"use client"

import { Brain, ArrowRight, Zap, Lightbulb } from "lucide-react"

import { NexusState } from "@/hooks/useNexusStream"

interface AIDecisionEngineProps {
  simState: "none" | "detected" | "intervening" | "recovering" | "recovered";
  maxAnomaly: number;
  totalQueue: number;
  nexusState: NexusState | null;
}

export function AIDecisionEngine({ simState, maxAnomaly, totalQueue, nexusState }: AIDecisionEngineProps) {
  
  if (simState === "none") {
    return (
      <div className="flex flex-col items-center justify-center h-full text-slate-500 gap-4 p-8">
        <Brain className="w-12 h-12 opacity-20" />
        <span className="text-xs font-bold tracking-widest uppercase">AI Engine Standby</span>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full bg-blue-950/20">
      <div className="bg-blue-900/50 p-3 border-b border-blue-500/30 flex items-center gap-2">
        <Brain className="w-4 h-4 text-blue-400" />
        <span className="text-blue-100 font-black tracking-widest text-xs uppercase">AI Decision Explainer</span>
      </div>

      <div className="p-4 flex flex-col gap-5 overflow-y-auto">
        
        {/* Context */}
        <div className="flex flex-col gap-2 border-l-2 border-red-500 pl-3">
          <span className="text-red-400 text-xs font-black uppercase tracking-widest flex items-center gap-1 animate-pulse">
            <Zap className="w-4 h-4"/> INCIDENT DETECTED
          </span>
          <div className="flex justify-between items-end mt-2">
            <span className="text-white text-xs font-medium">Location</span>
            <span className="text-slate-300 font-mono text-sm">North Approach (J5)</span>
          </div>
          <div className="flex justify-between items-end">
            <span className="text-white text-xs font-medium">Severity</span>
            <span className="text-red-400 font-mono font-black text-sm">{(maxAnomaly > 0 ? maxAnomaly : 0.85).toFixed(2)}</span>
          </div>
          <div className="flex justify-between items-end">
            <span className="text-white text-xs font-medium">Current Queue</span>
            <span className="text-orange-400 font-mono font-black text-sm">{totalQueue} Vehicles</span>
          </div>
          <div className="flex justify-between items-end">
            <span className="text-white text-xs font-medium">Predicted Delay</span>
            <span className="text-red-400 font-mono font-bold text-sm">+31%</span>
          </div>
        </div>

        {/* DECISION */}
        {simState !== "detected" && (
          <div className="flex flex-col gap-3 animate-in fade-in slide-in-from-right-4 duration-500">
            
            <div className="flex flex-col gap-2 border border-emerald-500/50 bg-emerald-950/30 rounded-lg p-3 relative overflow-hidden">
              <div className="absolute top-0 right-0 w-16 h-16 bg-emerald-500/10 rounded-full blur-xl animate-pulse"></div>
              
              <span className="text-emerald-400 text-[10px] font-black uppercase tracking-widest mb-1">AI Decision</span>
              <span className="text-white font-bold text-sm leading-tight uppercase">
                Increase NS Through Phase
              </span>
              
              <div className="flex justify-between items-center mt-3 pt-3 border-t border-emerald-500/20">
                 <span className="text-slate-400 text-xs uppercase font-bold">Green Time</span>
                 <span className="text-white font-mono font-black text-lg">
                    15s <ArrowRight className="inline w-4 h-4 text-emerald-400 mx-1"/> <span className="text-emerald-400">38s</span>
                 </span>
              </div>
            </div>

            {/* LIVE TELEMETRY */}
            {nexusState?.rl && (
              <div className="flex flex-col gap-2 bg-slate-900 border border-slate-700 rounded-lg p-3">
                 <span className="text-purple-400 text-[10px] font-black uppercase tracking-widest flex items-center gap-1">
                   <Brain className="w-3 h-3"/> PPO Policy Telemetry
                 </span>
                 <div className="flex justify-between items-center mt-1">
                   <span className="text-slate-400 text-[10px] uppercase font-bold">RL Action</span>
                   <span className="text-purple-400 font-mono font-black text-xs">{nexusState.rl.action}</span>
                 </div>
                 <div className="flex flex-col mt-1">
                   <span className="text-slate-400 text-[10px] uppercase font-bold mb-1">Probability Distribution</span>
                   <div className="flex gap-1">
                     {nexusState.rl.probabilities.map((p, i) => (
                       <div key={i} className={`flex-1 text-center font-mono text-[9px] py-0.5 rounded ${i === nexusState.rl!.action ? 'bg-purple-900 text-purple-200' : 'bg-slate-800 text-slate-500'}`}>
                         {p.toFixed(2)}
                       </div>
                     ))}
                   </div>
                 </div>
              </div>
            )}

            {/* WHY? */}
            <div className="flex flex-col gap-2 bg-slate-900 border border-slate-700 rounded-lg p-3">
               <span className="text-blue-400 text-[10px] font-black uppercase tracking-widest flex items-center gap-1">
                 <Lightbulb className="w-3 h-3"/> AI Reasoning (Why?)
               </span>
               <span className="text-slate-300 text-xs leading-relaxed">
                 North corridor blocked. Queue growing rapidly. RL policy increased NS green time to flush queue.
               </span>
               <div className="flex justify-between items-center mt-2">
                 <span className="text-slate-500 text-[10px] uppercase font-bold">Expected Recovery</span>
                 <span className="text-emerald-400 font-black text-xs">43 Seconds</span>
               </div>
            </div>

          </div>
        )}

      </div>
    </div>
  )
}
