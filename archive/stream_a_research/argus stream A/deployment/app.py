from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import uvicorn
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

PROJECT_ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("ARGUS_STREAM_A_ROOT", str(PROJECT_ROOT))

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from demo import ENGINE, PROFILES, _profile_payload  # noqa: E402


def _resolve_profile_label(profile_value: str) -> str:
    if profile_value in PROFILES:
        return profile_value

    for label, profile in PROFILES.items():
        if profile.key == profile_value:
            return label

    raise HTTPException(status_code=400, detail=f"Unknown profile: {profile_value}")


def preload_profiles(*, include_extractor: bool = True) -> None:
    ENGINE.preload(
        include_extractor=include_extractor,
        profile_labels=list(PROFILES.keys()),
    )


def _cors_origins() -> tuple[list[str], bool]:
    raw = os.environ.get("ARGUS_STREAM_A_CORS_ORIGINS", "*").strip()
    if not raw or raw == "*":
        return ["*"], True
    origins = [origin.strip() for origin in raw.split(",") if origin.strip()]
    return origins, False


def create_fastapi_app(*, preload: bool = False) -> FastAPI:
    if preload:
        preload_profiles()

    app = FastAPI(
        title="ARGUS Stream A API",
        version="1.0.0",
    )

    origins, allow_all = _cors_origins()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=not allow_all,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/")
    def root() -> dict[str, object]:
        return {
            "service": "ARGUS Stream A API",
            "status": "ok",
            "endpoints": ["/health", "/profiles", "/analyze"],
        }

    @app.get("/health")
    def health() -> dict[str, object]:
        return {
            "status": "ok",
            "device": ENGINE.device,
            "cached_profiles": sorted(ENGINE.scorers.keys()),
            "extractor_loaded": ENGINE.extractor is not None,
        }

    @app.get("/profiles")
    def profiles() -> dict[str, object]:
        return {
            "profiles": [
                _profile_payload(profile)
                for profile in (PROFILES[label] for label in PROFILES)
            ]
        }

    @app.post("/analyze")
    async def analyze(
        profile: str = Form(...),
        video: UploadFile = File(...),
    ) -> dict[str, object]:
        profile_label = _resolve_profile_label(profile)

        filename = video.filename or "upload.mp4"
        suffix = Path(filename).suffix or ".mp4"
        temp_path: Path | None = None

        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
                temp_path = Path(temp_file.name)
                while True:
                    chunk = await video.read(1024 * 1024)
                    if not chunk:
                        break
                    temp_file.write(chunk)

            payload = ENGINE.analyze_payload(temp_path, profile_label)
            payload["request"] = {
                "profile": profile_label,
                "filename": filename,
            }
            return payload
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except FileNotFoundError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        finally:
            await video.close()
            if temp_path is not None and temp_path.exists():
                temp_path.unlink(missing_ok=True)

    return app


app = create_fastapi_app(preload=False)


def main() -> None:
    uvicorn.run(
        "deployment.app:app",
        host=os.environ.get("ARGUS_STREAM_A_HOST", "127.0.0.1"),
        port=int(os.environ.get("ARGUS_STREAM_A_PORT", "8000")),
        reload=False,
    )


if __name__ == "__main__":
    main()
