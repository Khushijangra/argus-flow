# EVOLUTION FORENSICS AUDIT
## Document 9: DIGITAL_TWIN_FORENSICS.md

### Digital Twin Forensics Audit

The "Digital Twin" is visually the most impressive part of Phase B (Hackathon iteration).

#### Component: `CanvasCityTwin.tsx`
This component occupies the entire background of the Next.js UI, rendering hundreds of cars moving smoothly through a complex 4-way intersection.

#### How it works (Forensic Reality)
1.  **Not Physics Based**: It does not use rigid-body physics, nor does it link to a real SUMO physical simulation.
2.  **Not Backend Driven**: It does not read `nexusState.rl.queue` or `nexusState.network` to spawn cars.
3.  **Pure React Mathematics**: Inside a `useEffect`, it spawns exactly 300 `cars` arrays with properties like `x`, `y`, `dx`, `dy`, and `color`. 
4.  **Looping Logic**: Cars run continuously until they hit the boundary (`canvas.width + 50`), at which point their coordinates simply teleport to `-50` and loop again.
5.  **Signal Mimicry**: It uses an internal `isNSGreen` state interval (switching every 15 seconds). Cars check their lane alignment against `isNSGreen` and set their `currentSpeed` to 0 if the light is "red".

#### Truth Conclusion
The Digital Twin is **ANIMATED, NOT SIMULATED**. It is a brilliant UI component that visually demonstrates queue theory, but it has zero data-binding to the actual RL agent's metrics. It exists purely to satisfy the "Government Command Center" aesthetic requirement.
