"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { BrainCircuit, ThumbsUp } from "lucide-react"

export function ExplainableAIPanel() {
  return (
    <Card className="bg-slate-900 border-slate-800 h-full">
      <CardHeader className="pb-2 bg-slate-800/50 border-b border-slate-800">
        <CardTitle className="text-slate-200 text-sm uppercase tracking-wider flex items-center gap-2">
          <BrainCircuit className="w-4 h-4 text-purple-400" />
          Why did AI change this signal?
        </CardTitle>
      </CardHeader>
      <CardContent className="pt-4 flex flex-col gap-4">
        <div className="bg-slate-950 p-3 rounded-md border border-slate-800">
          <p className="text-slate-300 text-sm leading-relaxed">
            <strong className="text-red-400">North lane contains a high-severity incident.</strong><br/>
            Queue growth was predicted to exceed road capacity within 2 minutes.<br/><br/>
            AI preemptively <strong className="text-green-400">extended North-South green time by 18 seconds</strong> and suppressed East-West traffic to clear the blocked intersection safely.
          </p>
        </div>
        
        <div className="flex items-center gap-3 bg-emerald-950/30 p-3 rounded-md border border-emerald-900/50">
          <ThumbsUp className="w-5 h-5 text-emerald-400" />
          <div className="flex flex-col">
            <span className="text-emerald-400 text-xs font-bold uppercase">Expected Outcome</span>
            <span className="text-slate-300 text-sm">Prevents secondary collisions and reduces overall intersection wait time by 42%.</span>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
