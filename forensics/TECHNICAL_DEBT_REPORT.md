# EVOLUTION FORENSICS AUDIT
## Document 11: TECHNICAL_DEBT_REPORT.md

### Technical Debt Analysis

The rapid evolution from a methodical research project (Phase A) to a highly visual hackathon demonstration (Phase B) accrued massive technical debt. 

| Debt Type | Description | Severity | Fix Effort |
| :--- | :--- | :--- | :--- |
| **Integration Debt** | `argus stream A` (VideoMAE) is a functioning ML pipeline, but the frontend bypasses it via `POST /api/inject`. | **CRITICAL** | High. Requires wiring OpenCV streaming from the backend to the UI. |
| **Architectural Debt** | The `backend/main.py` is overloaded. It attempts to serve static React files, manage WebSockets, run an RL simulation loop, and expose legacy REST endpoints simultaneously. | **HIGH** | Medium. Break `main.py` into a clean router architecture. |
| **Frontend Debt** | `CanvasCityTwin.tsx` operates entirely on frontend `requestAnimationFrame` loops completely detached from the backend state. | **MEDIUM** | Very High. Rewriting this to read actual `nexusState.network` vehicle positions would require microscopic SUMO linkage. |
| **Dead Code Debt** | The `modules/` directory contains thousands of lines of valid Python for carbon tracking and emergency corridors that are never executed. | **LOW** | Low. Delete the directory for Phase B, or move to Repo A. |

### Summary
The highest risk is the Integration Debt regarding Stream A. If a judge asks to see the actual VideoMAE pipeline analyzing a custom uploaded video, the system will fail because the React frontend physically does not send the video bytes to the backend.
