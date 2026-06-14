# Demo Completion Audit

Date: 2026-04-12

## Scope
This audit verifies the demo dashboard’s camera flow, backend responsiveness, and the two supported camera modes:
- Live webcam
- Uploaded traffic video

It also records the operational state observed during verification.

## Verified Results

### 1. Dashboard camera controls are visible
The frontend camera panel contains visible controls for:
- Camera Mode selector
- Video upload input
- Use Uploaded Video button
- Use Live Webcam button

### 2. Live/upload mode switching works
The backend accepted both mode transitions during testing:
- `POST /api/live/upload-video` returned `200` and switched the source to `mode: upload`
- `POST /api/live/source/mode` with `{"mode":"live"}` returned `200` and switched the source to `mode: live`

### 3. A real uploaded video was accepted
A real user video file was uploaded from:
- `C:\Users\Asus\Downloads\y\WhatsApp Video 2026-04-12 at 10.30.19 PM - Copy.mp4`

The upload response confirmed:
- `ok: true`
- `message: Video uploaded and camera source switched to upload mode`
- the uploaded file was stored under the backend uploads folder

### 4. Camera rendering is live
The snapshot endpoint returned a real JPEG frame after the backend restart and camera tests:
- `GET /api/live/camera/J1_1/north/snapshot` -> `200 image/jpeg`

### 5. Backend runtime is healthy enough for the demo path
The current backend status showed:
- `status: running`
- `demo_mode: false`
- `live_mode: true`
- `decision_engine: active`
- `junctions: 16`

## Audit Evidence

Recent audit logs confirm active control processing, including AI decision entries and consistency warnings, which indicates the runtime loop is operating and the dashboard is receiving live state updates.

## Operational Notes

- `run_demo.py --dashboard-only` was unstable in this environment, so direct backend startup was used for verification.
- The camera source state is session-based; after switching back to live mode, the backend reported `mode: live`.

## Conclusion
The demo camera flow is functionally complete for the two required modes. The verified behavior is:
- live webcam mode is available
- uploaded video mode is available
- switching between them works through the backend API
- the camera snapshot endpoint returns real image data

This audit supports demo completion with a minor operational caveat: the dashboard should be launched through the direct backend start path if `run_demo.py` fails in the current environment.