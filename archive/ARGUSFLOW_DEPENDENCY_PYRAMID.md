# ARGUSFLOW DEPENDENCY PYRAMID

```mermaid
graph TD
    subgraph Level 5: Application Layer
        DT[Digital Twin]
        SS[Scenario Studio]
    end

    subgraph Level 4: Network & UI
        FE[Next.js Frontend]
        WS[WebSocket Streamer]
    end

    subgraph Level 3: Orchestration
        HR[Hybrid Runtime]
    end

    subgraph Level 2: Intelligence Engine
        PPO[PPO Engine]
    end

    subgraph Level 1: Foundational Reality
        TE[Traffic Environment]
    end

    subgraph Parallel Disconnected Branch (The Reality Gap)
        VMAE[VideoMAE Vision Stack]
        MULDE[MULDE Anomaly Scorer]
    end

    DT --> FE
    SS --> FE
    FE --> WS
    WS --> HR
    HR --> PPO
    PPO --> TE

    VMAE -. "Future Integration" .-> HR
    MULDE -. "Future Integration" .-> HR
```
