"use client"

import { useState, useRef, useEffect } from "react"
import { Button } from "@/components/ui/button"
import { PlayCircle, AlertTriangle, Activity, Upload, Video } from "lucide-react"

interface AIVisionPanelProps {
  onLaunch: () => void;
  simState: "none" | "detected" | "intervening" | "recovering" | "recovered";
  maxAnomaly: number;
  totalQueue: number;
}

export function AIVisionPanel({ onLaunch, simState, maxAnomaly, totalQueue }: AIVisionPanelProps) {
  const [videoUrl, setVideoUrl] = useState<string | null>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  
  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const url = URL.createObjectURL(e.target.files[0]);
      setVideoUrl(url);
    }
  }

  const startAnalysis = () => {
    if (videoRef.current) {
      videoRef.current.play();
    }
    onLaunch();
  }

  return (
    <div className="flex flex-col h-full bg-slate-900 border-r border-slate-800">
      
      {/* VIDEO UPLOAD / CONTROL */}
      <div className="p-4 border-b border-slate-800 flex flex-col gap-3">
        <span className="text-slate-500 text-[10px] font-black uppercase tracking-widest flex items-center gap-2">
          <Video className="w-3 h-3" /> Live Camera Feed
        </span>
        
        {!videoUrl ? (
           <label className="flex flex-col items-center justify-center w-full h-16 border-2 border-slate-700 border-dashed rounded-lg cursor-pointer bg-slate-800 hover:bg-slate-700">
              <div className="flex flex-col items-center justify-center pt-5 pb-6">
                 <Upload className="w-4 h-4 text-slate-400 mb-1" />
                 <p className="text-[10px] text-slate-400 font-bold uppercase">Upload accident.mp4</p>
              </div>
              <input type="file" className="hidden" accept="video/mp4" onChange={handleFileChange} />
           </label>
        ) : (
           <Button 
             onClick={startAnalysis}
             disabled={simState !== "none" && simState !== "recovered"}
             className="bg-blue-600 hover:bg-blue-500 text-white font-black uppercase tracking-widest text-xs h-10 shadow-[0_0_15px_rgba(37,99,235,0.5)] animate-pulse"
           >
             <PlayCircle className="w-4 h-4 mr-2" /> Start Analysis Pipeline
           </Button>
        )}
      </div>

      {/* AI VISION ANALYSIS LAYER */}
      <div className="p-4 flex-1 flex flex-col gap-6 overflow-y-auto">
        <span className="text-blue-400 text-[10px] font-black uppercase tracking-widest flex items-center gap-2">
          <Activity className="w-3 h-3" /> Pipeline Vision Array
        </span>

        {/* Video Frame */}
        <div className="relative w-full aspect-video bg-black rounded-xl border border-slate-800 overflow-hidden flex items-center justify-center shadow-inner">
           {videoUrl ? (
             <video ref={videoRef} src={videoUrl} loop muted playsInline className="w-full h-full object-cover" />
           ) : (
             <span className="text-slate-600 text-[10px] font-mono font-bold tracking-widest">NO SIGNAL</span>
           )}
           
           {/* Bounding Box Drawing when Detected */}
           {(simState === "detected" || simState === "intervening") && (
             <div className="absolute inset-0 bg-red-900/30">
               <div className="absolute top-[20%] left-[30%] w-[40%] h-[40%] border-2 border-red-500 bg-red-500/20 flex flex-col">
                 <div className="bg-red-500 text-white text-[9px] font-black px-1.5 py-0.5 w-max tracking-wider">
                   ACCIDENT - 87% CONFIDENCE
                 </div>
               </div>
             </div>
           )}

           <div className="absolute inset-0 bg-gradient-to-b from-transparent via-white/5 to-transparent bg-[length:100%_4px] animate-[scan_2s_linear_infinite] pointer-events-none"></div>
        </div>

        {/* Causal Chain Display */}
        {simState !== "none" && (
           <div className="flex flex-col gap-2">
             <div className="text-[10px] font-bold uppercase tracking-widest px-2 py-1 rounded bg-blue-900/50 text-blue-400 border border-blue-500/50">
                1. VideoMAE Processing...
             </div>
             <div className="text-[10px] font-bold uppercase tracking-widest px-2 py-1 rounded bg-purple-900/50 text-purple-400 border border-purple-500/50">
                2. MULDE Score = 39.8 (High)
             </div>
             <div className="text-[10px] font-bold uppercase tracking-widest px-2 py-1 rounded bg-red-900/50 text-red-400 border border-red-500/50">
                3. Severity Output = {(maxAnomaly || 0.85).toFixed(2)}
             </div>
             <div className="text-[10px] font-bold uppercase tracking-widest px-2 py-1 rounded bg-slate-800/50 text-slate-300 border border-slate-600/50 flex justify-between">
                <span>4. Data Source:</span>
                <span className={maxAnomaly > 0 ? "text-emerald-400" : "text-amber-400"}>
                  {maxAnomaly > 0 ? "Live Inference Stream" : "Demo Scenario Fallback"}
                </span>
             </div>
           </div>
        )}

      </div>
    </div>
  )
}
