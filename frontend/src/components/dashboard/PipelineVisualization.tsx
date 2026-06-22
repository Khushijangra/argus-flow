"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { motion } from "framer-motion"
import { ArrowRight } from "lucide-react"

const stages = [
  "VIDEO",
  "VIDEOMAE",
  "STREAM-A",
  "HYBRID STATE",
  "RL AGENT",
  "SIGNAL CONTROL"
]

export function PipelineVisualization() {
  return (
    <Card className="bg-slate-900 border-slate-800">
      <CardHeader className="pb-2">
        <CardTitle className="text-slate-200 text-sm uppercase tracking-wider">Live Pipeline Execution</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex items-center justify-between mt-4">
          {stages.map((stage, i) => (
            <div key={stage} className="flex items-center">
              <motion.div
                initial={{ opacity: 0.3, scale: 0.9 }}
                animate={{ 
                  opacity: [0.3, 1, 0.3], 
                  scale: [0.9, 1.05, 0.9],
                  borderColor: ["#1e293b", "#3b82f6", "#1e293b"]
                }}
                transition={{ 
                  repeat: Infinity, 
                  duration: 2, 
                  delay: i * 0.3 
                }}
                className="bg-slate-800 border-2 border-slate-700 px-3 py-2 rounded text-xs font-bold text-slate-300 tracking-wider"
              >
                {stage}
              </motion.div>
              {i < stages.length - 1 && (
                <div className="mx-2 text-slate-600">
                  <ArrowRight className="w-4 h-4" />
                </div>
              )}
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}
