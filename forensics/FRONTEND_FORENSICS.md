# EVOLUTION FORENSICS AUDIT
## Document 6: FRONTEND_FORENSICS.md

### React Component Audit

The React Frontend (`frontend/src/`) was introduced purely for the hackathon (Phase B). It replaced older HTML/JS attempts with a modern, glassmorphic Next.js UI.

#### Component Breakdown

| Component | Purpose | Data Source | Status |
| :--- | :--- | :--- | :--- |
| **`ScenarioStudio.tsx`** | The main orchestration view. | `useNexusStream()` hook + React state. | **REAL + MOCKED**. Drives the narrative flow using `setTimeout`, but successfully reads `nexusState` via WebSockets. |
| **`CanvasCityTwin.tsx`** | Giant background visualization of traffic. | Pure frontend mathematical loops. | **SIMULATED**. Generates visual traffic entities independent of the backend state. Purely cosmetic. |
| **`AIVisionPanel.tsx`** | "Upload accident.mp4" and view severity. | React local state for Video, `ScenarioStudio` props for severity. | **FRONTEND DRIVEN**. Does not send video to the backend. Visualizes bounding boxes via hardcoded absolute CSS positioning. |
| **`AIDecisionEngine.tsx`** | Shows RL telemetry and "AI Reasoning". | Uses `nexusState.rl` (recently integrated) + hardcoded reasoning strings. | **BACKEND DRIVEN (Mostly)**. Reads actual PPO policy telemetry, but the "Why?" text is hardcoded. |
| **`IncidentTimeline.tsx`** | Shows events like "VideoMAE Processing". | Passed down from `ScenarioStudio.tsx` state array. | **HARDCODED**. Populated sequentially by `setTimeout` intervals. |
| **`NetworkStatusGrid.tsx`** | Displays 16 junctions. | Reads `nexusState.network`. | **SIMULATED (By Backend)**. The backend uses `demo_data.py` to generate the 15 non-J5 junctions. |

### Conclusion
The frontend is a masterclass in UI/UX illusion. By wrapping a single, valid backend data stream (J5 RL Telemetry) in 15 layers of mock data and visual timers, it successfully gives the impression of a massive, city-scale command center.
