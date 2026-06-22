# REALITY GAP (The Roadmap)

These components exist in the repository but are severely disconnected from the runtime execution.

- **VideoMAE Integration**: Code exists in `argus_stream_extracted`, but the backend never instantiates or queries it.
- **MULDE Integration**: Code exists, but never executed live.
- **Frame Streaming**: The React frontend does not POST actual video frames to the backend.
- **Live Digital Twin Binding**: The canvas animation is a decoupled `requestAnimationFrame` loop, rather than explicitly drawing queue sizes reported by the WebSocket.
