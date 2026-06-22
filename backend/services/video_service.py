import time
import numpy as np
from typing import Optional, Dict
import backend.dependencies as deps
from backend.core.utils import _optional_cv2
from backend.core.network_mapper import mapper

def _get_cam_renderer(junction_id: str, direction: str):
    from backend.main import RoadCameraRenderer, _resolve_camera_source, _cam_renderers, logger
    """Return a cached RoadCameraRenderer for the given junction + direction."""
    if RoadCameraRenderer is None:
        return None
    source_url = _resolve_camera_source(junction_id, direction)
    source_str = str(source_url).strip() if source_url is not None else ""
    shared_webcam = bool(source_str.isdigit())
    key = f"cam_src_{source_str}" if shared_webcam else f"{junction_id}_{direction.lower()}"
    if key not in _cam_renderers:
        if not source_url:
            logger.warning(
                "[CamRenderer] Missing camera source for %s (%s). Set TRAFFIC_CAM_URL_%s_%s or TRAFFIC_CAM_URL_%s",
                junction_id,
                direction,
                junction_id.upper().replace("-", "_"),
                direction.upper(),
                direction.upper(),
            )
            return None
        try:
            _cam_renderers[key] = RoadCameraRenderer(
                direction=direction,
                junction_id=junction_id,
                fps=10.0,
                source_url=source_url,
                strict_source=True,
            )
            logger.info("[CamRenderer] Created renderer %s", key)
        except Exception as exc:
            logger.warning("[CamRenderer] Could not create renderer %s: %s", key, exc)
            return None
    renderer = _cam_renderers[key]
    # Keep HUD metadata aligned even when renderer instances are shared per source.
    try:
        renderer.junction_id = junction_id
        renderer.direction = str(direction).upper()
    except Exception:
        pass
    return renderer



def _junction_state_payload(junction_id: str) -> Dict:
    from backend.main import _camera_input_mode, _camera_source_payload
    st = deps._junction_states.get(junction_id, {})
    if not st:
        return {}
    payload = dict(st)
    phase = str(payload.get("phase", "NS_GREEN"))
    camera_direction = "north" if phase == "NS_GREEN" else ("east" if phase == "EW_GREEN" else "north")
    payload["selected"] = junction_id == deps._selected_junction_id
    payload["camera"] = {
        "junction_id": junction_id,
        "source_mode": _camera_input_mode,
        "source": _camera_source_payload(),
        "direction_hint": camera_direction,
        "stream_url": f"/api/live/camera/{junction_id}/{camera_direction}"
    }
    payload["live_source"] = _camera_source_payload()
    
    dt_info = mapper.get_intersection(junction_id)
    if dt_info:
        payload["lat"] = dt_info["lat"]
        payload["lon"] = dt_info["lon"]
        payload["junction_id"] = dt_info["junction_id"]
        payload["neighbors"] = dt_info["neighbors"]
    else:
        payload["lat"] = 0.0
        payload["lon"] = 0.0
        payload["junction_id"] = junction_id
        payload["neighbors"] = []
        
    return payload



def _encode_jpeg_frame(frame) -> Optional[bytes]:
    cv2 = _optional_cv2()
    if cv2 is None:
        return None
    try:
        ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 82])
        return buf.tobytes() if ok else None
    except Exception:
        return None



def _demo_placeholder_jpeg(text: str = "Demo feed", junction: str = "J0_0") -> Optional[bytes]:
    cv2 = _optional_cv2()
    if cv2 is None:
        return None
    try:
        frame = np.full((480, 800, 3), (245, 248, 250), dtype=np.uint8)
        accent_seed = sum(ord(ch) for ch in junction)
        accent = ((accent_seed * 37) % 170 + 40, (accent_seed * 17) % 140 + 80, (accent_seed * 29) % 160 + 60)
        road_y = 280
        cv2.rectangle(frame, (0, road_y), (800, 480), (55, 62, 70), -1)
        cv2.line(frame, (0, road_y + 60), (800, road_y + 60), (245, 214, 86), 4)
        cv2.line(frame, (0, road_y + 130), (800, road_y + 130), (255, 255, 255), 3)
        for x in range(40, 800, 120):
            cv2.rectangle(frame, (x, road_y + 20), (x + 60, road_y + 60), accent, -1)
        for x in range(20, 800, 80):
            cv2.line(frame, (x, road_y + 90), (x + 30, road_y + 90), (245, 214, 86), 2)
        pulse_x = 80 + int((time.time() * 90) % 620)
        cv2.circle(frame, (pulse_x, road_y + 45), 18, (38, 166, 154), -1)
        cv2.circle(frame, (pulse_x, road_y + 45), 28, (38, 166, 154), 3)
        cv2.putText(frame, "NEXUS Demo Feed", (28, 72), cv2.FONT_HERSHEY_SIMPLEX, 1.15, (20, 34, 48), 3)
        cv2.putText(frame, text, (28, 122), cv2.FONT_HERSHEY_SIMPLEX, 0.9, accent, 2)
        cv2.putText(frame, f"Junction: {junction}", (28, 162), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (32, 48, 64), 2)
        cv2.putText(frame, time.strftime("%Y-%m-%d %H:%M:%S"), (28, 430), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (60, 72, 84), 2)
        return _encode_jpeg_frame(frame)
    except Exception:
        return None



def _read_demo_video_frame(junction: str = "J0_0") -> Optional[bytes]:
    return _demo_placeholder_jpeg("Synthetic demo frame", junction)



