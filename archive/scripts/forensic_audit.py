"""
NEXUS-ATMS Comprehensive Forensic Audit Script
Phase 1: Static AST Dependency Map
Phase 2: Runtime Entry Point Analysis (FastAPI routes, WebSocket, CLI, Docker, Shell)
Phase 3: Frontend Traceability (React/TS → API → Service → Model)
Phase 4: Dead Code Detection (ACTIVE / SHARED / LEGACY / ORPHANED / DEAD)
Phase 5: Repository Boundary Matrix

Outputs:
  forensics/STATIC_DEPENDENCY_MAP.md
  forensics/NEXUS_RUNTIME_MAP.md
  forensics/ANOMALY_RUNTIME_MAP.md
  forensics/FRONTEND_BACKEND_TRACEABILITY.md
  forensics/ARCHITECTURE_DRIFT_REPORT.md
  forensics/BOUNDARY_MATRIX.md
  forensics/DEAD_CODE_REPORT_V2.md
"""

import ast
import os
import re
import sys
import json
import subprocess
from pathlib import Path
from collections import defaultdict
from typing import Dict, Set, List, Tuple, Optional

# ─────────────────────────────── CONFIG ────────────────────────────────────

ROOT = Path(__file__).resolve().parent.parent
FORENSICS_DIR = ROOT / "forensics"
FORENSICS_DIR.mkdir(exist_ok=True)

# Entry points for each project
NEXUS_ROOTS = [
    "train.py", "evaluate.py",
    "backend/main.py",
    "run_demo.py",
    "modules/corridor.py", "modules/engine.py",
    "modules/carbon/engine.py",
    "modules/emergency/corridor.py",
    "modules/pedestrian_safety/safety.py",
    "modules/cybersecurity/signal_security.py",
    "modules/road_maintenance/maintenance.py",
    "modules/nl_command/parser.py",
    "modules/voice_broadcast/broadcast.py",
    "modules/counterfactual/engine.py",
    "modules/digital_twin/twin.py",
    "control/rl_controller.py",
    "control/traffic_env.py",
    "scripts/train_lstm.py",
    "scripts/compare_agents.py",
    "scripts/benchmark_d3qn_suite.py",
    "scripts/run_multiseed_d3qn.py",
    "scripts/evaluate_multiseed_gate.py",
]

ANOMALY_ROOTS = [
    "backend/main.py",
    "backend/runtime/hybrid_runtime.py",
    "control/traffic_env.py",
    "scripts/train_anomaly_policy.py",
    "scripts/eval_anomaly_policy.py",
    "scripts/evaluate_baseline_vs_ppo.py",
    "argus_stream_extracted/argus stream A/src/training/train_stream.py",
    "argus_stream_extracted/argus stream A/src/evaluation/stream_a.py",
    "argus_stream_extracted/argus stream A/demo.py",
    "argus_stream_extracted/argus stream A/scripts/extract_features.py",
    "argus_stream_extracted/argus stream A/scripts/train.py",
    "frontend/src/components/studio/ScenarioStudio.tsx",
]

# Files that belong to NEXUS core v1.0.0 (from git ls-files at 8d49295)
NEXUS_CORE_FILES_SNAPSHOT = set([
    "ai/anomaly/anomaly_detector.py", "ai/anomaly/ml_anomaly_detector.py",
    "ai/envs/multi_agent_env.py", "ai/envs/sumo_env.py",
    "ai/explainability/explainer.py", "ai/prediction/lstm_predictor.py",
    "ai/rl/d3qn.py", "ai/rl/dqn.py", "ai/rl/graph_coordinator.py",
    "ai/rl/graph_state_builder.py", "ai/rl/ppo.py",
    "ai/utils/logger.py", "ai/utils/metrics.py", "ai/utils/visualization.py",
    "ai/vision/counter.py", "ai/vision/detector.py", "ai/vision/geo_mapper.py",
    "ai/vision/incident_detector.py", "ai/vision/road_camera_renderer.py",
    "ai/vision/speed_estimator.py", "ai/vision/tracker.py", "ai/vision/traffic_renderer.py",
    "control/emergency_handler.py", "control/rl_controller.py",
    "control/signal_optimizer.py", "control/traffic_env.py",
    "iot/data_fusion.py", "iot/mqtt_client.py", "iot/sensor_simulator.py",
    "modules/carbon/engine.py", "modules/counterfactual/engine.py",
    "modules/cybersecurity/signal_security.py", "modules/digital_twin/twin.py",
    "modules/emergency/corridor.py", "modules/nl_command/parser.py",
    "modules/pedestrian_safety/safety.py", "modules/road_maintenance/maintenance.py",
    "modules/voice_broadcast/broadcast.py",
    "train.py", "evaluate.py", "run_demo.py",
    "scripts/benchmark_d3qn_suite.py", "scripts/compare_agents.py",
    "scripts/run_multiseed_d3qn.py", "scripts/train_lstm.py",
    "scripts/collect_demo_nonzero_junction_data.py",
    "scripts/collect_waiting_and_corridor_data.py",
    "scripts/evaluate_multiseed_gate.py",
    "scripts/quick_train.py", "scripts/staging_validation.py",
    "scripts/yolo_only_validation.py",
])

# Files introduced in anomaly era (diff B: 539cb6c -> e9cbbe1)
ANOMALY_ERA_FILES = set([
    "argus_stream_extracted/argus stream A/src/data/datasets.py",
    "argus_stream_extracted/argus stream A/src/evaluation/metrics.py",
    "argus_stream_extracted/argus stream A/src/evaluation/stream_a.py",
    "argus_stream_extracted/argus stream A/src/models/backbones/videomae.py",
    "argus_stream_extracted/argus stream A/src/models/scorers/mulde.py",
    "argus_stream_extracted/argus stream A/src/training/train_stream.py",
    "argus_stream_extracted/argus stream A/src/utils/config.py",
    "argus_stream_extracted/argus stream A/src/utils/io.py",
    "argus_stream_extracted/argus stream A/src/utils/logging.py",
    "backend/api/analytics.py", "backend/api/emergency.py",
    "backend/api/health.py", "backend/api/maintenance.py",
    "backend/api/signals.py", "backend/api/traffic.py",
    "backend/api/websockets.py", "backend/core/config.py",
    "backend/core/logging.py", "backend/core/schemas.py",
    "backend/core/utils.py", "backend/dependencies.py",
    "backend/services/traffic_service.py", "backend/services/video_service.py",
    "backend/runtime/hybrid_runtime.py",
    "scripts/train_anomaly_policy.py", "scripts/eval_anomaly_policy.py",
    "scripts/extract_ua_detrac_features.py",
    "tests/test_anomaly_detector.py", "tests/test_api.py",
    "tests/test_d3qn.py", "tests/test_lstm.py",
    "frontend/src/components/studio/ScenarioStudio.tsx",
    "frontend/src/components/studio/CanvasCityTwin.tsx",
    "frontend/src/components/studio/AIVisionPanel.tsx",
    "frontend/src/components/studio/AIDecisionEngine.tsx",
    "frontend/src/components/studio/IncidentTimeline.tsx",
    "frontend/src/hooks/useNexusStream.ts",
])

# ─────────────────────────── PHASE 1: STATIC AST ───────────────────────────

def get_all_py_files(root: Path) -> List[Path]:
    """Collect all .py files, skipping venv/cache dirs."""
    skip = {".venv", "venv", "__pycache__", ".git", "node_modules", ".cache"}
    result = []
    for p in root.rglob("*.py"):
        if not any(s in p.parts for s in skip):
            result.append(p)
    return result

def get_all_ts_files(root: Path) -> List[Path]:
    """Collect all .ts/.tsx files."""
    skip = {".venv", "venv", "__pycache__", ".git", "node_modules", ".cache", ".next"}
    result = []
    for ext in ["*.ts", "*.tsx"]:
        for p in root.rglob(ext):
            if not any(s in p.parts for s in skip):
                result.append(p)
    return result

def extract_imports(filepath: Path, root: Path) -> Tuple[Set[str], List[str]]:
    """
    Extract all imports from a Python file.
    Returns (resolved_local_files, raw_module_names).
    Also detects conditional imports and importlib calls.
    """
    try:
        source = filepath.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return set(), []

    local_files = set()
    raw_modules = []
    warnings = []

    # Detect dynamic imports
    if "importlib.import_module" in source:
        warnings.append(f"[DYNAMIC_IMPORT] {filepath.relative_to(root)} uses importlib")
    if re.search(r"if\s+\w+.*:\s*\n\s+(?:from|import)\s+", source):
        warnings.append(f"[CONDITIONAL_IMPORT] {filepath.relative_to(root)} has conditional import")

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return set(), warnings

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                raw_modules.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                raw_modules.append(node.module)
                # Try to resolve local
                mod_path = node.module.replace(".", "/")
                # Relative import
                if node.level > 0:
                    parent = filepath.parent
                    for _ in range(node.level - 1):
                        parent = parent.parent
                    candidate = parent / (mod_path + ".py")
                    if candidate.exists():
                        local_files.add(str(candidate.relative_to(root)))
                    candidate_init = parent / mod_path / "__init__.py"
                    if candidate_init.exists():
                        local_files.add(str(candidate_init.relative_to(root)))
                else:
                    # Absolute: try from root
                    candidate = root / (mod_path + ".py")
                    if candidate.exists():
                        local_files.add(str(candidate.relative_to(root)))
                    candidate_init = root / mod_path / "__init__.py"
                    if candidate_init.exists():
                        local_files.add(str(candidate_init.relative_to(root)))

    return local_files, warnings + raw_modules

def build_import_graph(py_files: List[Path], root: Path) -> Tuple[Dict, List[str]]:
    """Build full import graph for all Python files."""
    graph = {}
    all_warnings = []
    for f in py_files:
        rel = str(f.relative_to(root)).replace("\\", "/")
        local, warns = extract_imports(f, root)
        graph[rel] = {"imports": sorted(local), "warnings": [w for w in warns if "[" in w]}
        all_warnings.extend([w for w in warns if "[" in w])
    return graph, all_warnings

def trace_reachable(roots: List[str], graph: Dict, root: Path) -> Set[str]:
    """DFS from root entry points through import graph."""
    visited = set()
    stack = []
    for r in roots:
        norm = r.replace("\\", "/")
        if (root / norm).exists():
            stack.append(norm)
    while stack:
        node = stack.pop()
        if node in visited:
            continue
        visited.add(node)
        for dep in graph.get(node, {}).get("imports", []):
            dep_norm = dep.replace("\\", "/")
            if dep_norm not in visited:
                stack.append(dep_norm)
    return visited

# ─────────────────────────── PHASE 2: RUNTIME ANALYSIS ─────────────────────

def extract_fastapi_routes(filepath: Path) -> List[Dict]:
    """Extract FastAPI route decorators from a Python file."""
    routes = []
    try:
        source = filepath.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return routes
    # Match @app.get("/path") or @router.post("/path") etc.
    pattern = re.compile(
        r'@(?:app|router)\.(get|post|put|delete|patch|websocket)\s*\(\s*["\']([^"\']+)["\']',
        re.MULTILINE
    )
    for m in pattern.finditer(source):
        routes.append({"method": m.group(1).upper(), "path": m.group(2)})
    # Background tasks
    bg_pattern = re.compile(r'@app\.on_event\s*\(\s*["\']([^"\']+)["\']')
    for m in bg_pattern.finditer(source):
        routes.append({"method": "EVENT", "path": m.group(1)})
    return routes

def extract_fastapi_imports(filepath: Path) -> List[str]:
    """Extract service/module imports from main.py to trace chain."""
    try:
        source = filepath.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return []
    includes = []
    for line in source.splitlines():
        if line.strip().startswith("from") or line.strip().startswith("import"):
            includes.append(line.strip())
    return includes

def scan_docker_entrypoints(root: Path) -> List[str]:
    """Scan Dockerfile, Procfile, shell scripts for CMD/entrypoints."""
    entrypoints = []
    for fname in ["Dockerfile", "Procfile", "railway.json", "render.yaml",
                  "docker-compose.yml", "start.sh", "stop.sh", "nexus-start.ps1"]:
        p = root / fname
        if p.exists():
            try:
                content = p.read_text(encoding="utf-8", errors="ignore")
                entrypoints.append(f"### {fname}\n```\n{content[:500]}\n```")
            except Exception:
                pass
    return entrypoints

# ─────────────────────────── PHASE 3: FRONTEND TRACEABILITY ────────────────

def extract_api_calls_from_tsx(filepath: Path) -> List[Dict]:
    """Find fetch/axios/WebSocket calls in TS/TSX files."""
    calls = []
    try:
        source = filepath.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return calls

    # fetch("/api/...")
    fetch_pattern = re.compile(r'fetch\s*\(\s*[`"\']([^`"\']+)[`"\']')
    for m in fetch_pattern.finditer(source):
        calls.append({"type": "fetch", "url": m.group(1)})

    # axios.post/get("/api/...")
    axios_pattern = re.compile(r'axios\.(get|post|put|delete)\s*\(\s*[`"\']([^`"\']+)[`"\']')
    for m in axios_pattern.finditer(source):
        calls.append({"type": f"axios.{m.group(1)}", "url": m.group(2)})

    # WebSocket("ws://...")
    ws_pattern = re.compile(r'new\s+WebSocket\s*\(\s*[`"\']([^`"\']+)[`"\']')
    for m in ws_pattern.finditer(source):
        calls.append({"type": "WebSocket", "url": m.group(1)})

    # Template literal fetch with variable
    template_pattern = re.compile(r'fetch\s*\(\s*`([^`]+)`')
    for m in template_pattern.finditer(source):
        calls.append({"type": "fetch_template", "url": m.group(1)})

    return calls

def build_frontend_traceability(root: Path) -> List[Dict]:
    """Build component → API call map from all TSX files."""
    ts_files = get_all_ts_files(root)
    trace = []
    for f in ts_files:
        calls = extract_api_calls_from_tsx(f)
        if calls:
            rel = str(f.relative_to(root)).replace("\\", "/")
            trace.append({"component": rel, "api_calls": calls})
    return trace

# ─────────────────────── PHASE 4: DEAD CODE DETECTION ──────────────────────

def classify_file(rel_path: str,
                  nexus_reachable: Set[str],
                  anomaly_reachable: Set[str],
                  nexus_snapshot: Set[str],
                  anomaly_snapshot: Set[str]) -> str:
    """Classify a file into ACTIVE / SHARED / LEGACY / ORPHANED / DEAD."""
    in_nexus = rel_path in nexus_reachable
    in_anomaly = rel_path in anomaly_reachable
    in_nexus_snap = rel_path in nexus_snapshot
    in_anomaly_snap = rel_path in anomaly_snapshot

    if in_nexus and in_anomaly:
        return "SHARED"
    elif in_nexus and not in_anomaly:
        return "NEXUS_ONLY"
    elif in_anomaly and not in_nexus:
        return "ANOMALY_ONLY"
    elif in_nexus_snap and not in_nexus and not in_anomaly:
        return "LEGACY"       # Was in original NEXUS but no longer reachable
    elif in_anomaly_snap and not in_nexus and not in_anomaly:
        return "ORPHANED"     # Was introduced in anomaly era but not reachable
    else:
        return "DEAD"         # Not in any snapshot, not reachable

# ─────────────────────────── PHASE 5: BOUNDARY MATRIX ──────────────────────

def build_boundary_matrix(all_files: List[str],
                          nexus_reachable: Set[str],
                          anomaly_reachable: Set[str]) -> List[Dict]:
    rows = []
    for f in sorted(all_files):
        in_n = f in nexus_reachable
        in_a = f in anomaly_reachable
        shared = in_n and in_a
        # Recommend delete if not in either and not a config/doc
        ext = Path(f).suffix
        is_deletable = (not in_n and not in_a and
                        ext in [".py", ".sh", ".ps1", ".md", ".txt"] and
                        "forensics/" not in f and
                        "docs/" not in f)
        rows.append({
            "file": f,
            "nexus": "✅" if in_n else "❌",
            "anomaly": "✅" if in_a else "❌",
            "shared": "✅" if shared else "❌",
            "delete": "⚠️ Candidate" if is_deletable else "❌ Keep",
        })
    return rows

# ─────────────────────────── ARCHITECTURE DRIFT ────────────────────────────

ORIGINAL_FEATURES = {
    "Emergency Corridor (A* Routing)": {
        "files": ["modules/emergency/corridor.py", "modules/corridor.py"],
        "description": "A* graph path planning to pre-clear traffic lights for emergency vehicles."
    },
    "Carbon Engine (ESG)": {
        "files": ["modules/carbon/engine.py", "modules/engine.py"],
        "description": "Converts idle-time reduction to CO2/fuel/cost savings."
    },
    "Pedestrian Safety AI": {
        "files": ["modules/pedestrian_safety/safety.py"],
        "description": "Crowd surge detection, elderly heuristics, near-miss detection, school-zone policy."
    },
    "Cybersecurity (Command Validation)": {
        "files": ["modules/cybersecurity/signal_security.py"],
        "description": "HMAC signature verification, rate limiting, oscillation detection."
    },
    "Road Maintenance AI": {
        "files": ["modules/road_maintenance/maintenance.py"],
        "description": "Hard-braking event clustering → pothole detection → work-order generation."
    },
    "NL Command Parser": {
        "files": ["modules/nl_command/parser.py"],
        "description": "Intent classification → junction extraction → action dict."
    },
    "Voice Broadcast": {
        "files": ["modules/voice_broadcast/broadcast.py"],
        "description": "TTS multilingual public safety announcements."
    },
    "Counterfactual Engine": {
        "files": ["modules/counterfactual/engine.py"],
        "description": "AI vs fixed-timing baseline comparison for real-time proof-of-benefit."
    },
    "LSTM Traffic Forecasting": {
        "files": ["ai/prediction/lstm_predictor.py"],
        "description": "Short-horizon traffic queue growth prediction."
    },
    "D3QN RL Agent": {
        "files": ["ai/rl/d3qn.py"],
        "description": "Original Double Dueling DQN agent."
    },
    "PPO RL Agent (SB3)": {
        "files": ["ai/rl/ppo.py", "control/rl_controller.py"],
        "description": "StableBaselines3 PPO agent for production control."
    },
    "YOLO+DeepSORT Vision Pipeline": {
        "files": ["ai/vision/detector.py", "ai/vision/tracker.py"],
        "description": "Frame-level vehicle detection and tracking."
    },
    "Multi-Agent Graph Coordination": {
        "files": ["ai/rl/graph_coordinator.py", "ai/rl/graph_state_builder.py"],
        "description": "Junction-level graph RL coordination."
    },
    "VideoMAE Anomaly Backbone": {
        "files": ["argus_stream_extracted/argus stream A/src/models/backbones/videomae.py"],
        "description": "Video Masked Autoencoder for feature extraction."
    },
    "MULDE Anomaly Scorer": {
        "files": ["argus_stream_extracted/argus stream A/src/models/scorers/mulde.py"],
        "description": "Multi-scale density estimation for anomaly scoring."
    },
    "Hybrid Runtime (RL+CV Bridge)": {
        "files": ["backend/runtime/hybrid_runtime.py"],
        "description": "Orchestration engine bridging RL policy and anomaly events."
    },
    "Digital Twin (Canvas)": {
        "files": ["frontend/src/components/studio/CanvasCityTwin.tsx"],
        "description": "Animated city-scale traffic visualization."
    },
    "WebSocket Live Telemetry": {
        "files": ["backend/api/websockets.py"],
        "description": "5Hz backend state broadcast to React frontend."
    },
}

# ─────────────────────────── REPORT GENERATORS ─────────────────────────────

def write_static_dependency_map(graph: Dict, warnings: List[str], root: Path):
    lines = ["# STATIC DEPENDENCY MAP\n",
             "Generated by: `scripts/forensic_audit.py` — Phase 1\n\n",
             "## Dynamic/Conditional Import Warnings\n"]
    for w in warnings:
        lines.append(f"- {w}\n")
    lines.append("\n## Import Graph (Python Files)\n\n")
    lines.append("| File | Imports (Local) |\n|---|---|\n")
    for f, data in sorted(graph.items()):
        imports = ", ".join(data["imports"]) if data["imports"] else "—"
        lines.append(f"| `{f}` | {imports} |\n")
    out = FORENSICS_DIR / "STATIC_DEPENDENCY_MAP.md"
    out.write_text("".join(lines), encoding="utf-8")
    print(f"  ✅ Written: {out}")

def write_runtime_map(name: str, reachable: Set[str], roots: List[str],
                      routes: List[Dict], docker_info: List[str], root: Path):
    fname = FORENSICS_DIR / f"{name}_RUNTIME_MAP.md"
    lines = [f"# {name} RUNTIME MAP\n\n",
             f"Generated by: `scripts/forensic_audit.py` — Phase 2\n\n",
             "## Entry Points (Roots)\n"]
    for r in roots:
        exists = "✅" if (root / r).exists() else "❌ MISSING"
        lines.append(f"- `{r}` {exists}\n")
    lines.append("\n## Reachable Files (Traced from Roots)\n\n")
    for f in sorted(reachable):
        lines.append(f"- `{f}`\n")
    lines.append(f"\n**Total reachable: {len(reachable)} files**\n\n")
    lines.append("## FastAPI Routes Discovered\n\n")
    lines.append("| Method | Path |\n|---|---|\n")
    for r in sorted(routes, key=lambda x: x["path"]):
        lines.append(f"| `{r['method']}` | `{r['path']}` |\n")
    lines.append("\n## Docker/Shell/Deployment Entry Points\n\n")
    for d in docker_info:
        lines.append(d + "\n\n")
    fname.write_text("".join(lines), encoding="utf-8")
    print(f"  ✅ Written: {fname}")

def write_frontend_traceability(trace: List[Dict], root: Path):
    fname = FORENSICS_DIR / "FRONTEND_BACKEND_TRACEABILITY.md"
    lines = ["# FRONTEND ↔ BACKEND TRACEABILITY\n\n",
             "Generated by: `scripts/forensic_audit.py` — Phase 3\n\n",
             "> Maps each React/TS component to the API endpoints it calls.\n\n"]
    if not trace:
        lines.append("*No frontend TypeScript files found or no API calls detected.*\n")
    else:
        for item in trace:
            lines.append(f"### `{item['component']}`\n\n")
            lines.append("| Type | URL/Endpoint |\n|---|---|\n")
            for call in item["api_calls"]:
                lines.append(f"| `{call['type']}` | `{call['url']}` |\n")
            lines.append("\n")

    # Add known manual traceability for key components
    lines.append("## Known Manual Traces (Verified by Code Inspection)\n\n")
    traces = [
        ("ScenarioStudio.tsx", "setTimeout() → POST /api/inject", "backend/main.py", "HybridRuntime.inject_anomaly()", "control/traffic_env.py → _anomaly_severity"),
        ("AIVisionPanel.tsx", "Local `<video>` element only", "NOT CONNECTED", "No model called", "N/A"),
        ("CanvasCityTwin.tsx", "requestAnimationFrame loop (frontend only)", "NOT CONNECTED", "No backend data", "N/A"),
        ("AIDecisionEngine.tsx", "WebSocket useNexusStream()", "backend/api/websockets.py", "HybridRuntime → PPO.predict()", "nexusState.rl"),
        ("NetworkStatusGrid.tsx", "WebSocket useNexusStream()", "backend/demo_data.py (J1-J16 mocked)", "Only J5 is real RL", "nexusState.network"),
    ]
    lines.append("| Component | Call | Backend Handler | Model/Logic | Output |\n|---|---|---|---|---|\n")
    for t in traces:
        lines.append(f"| `{t[0]}` | {t[1]} | `{t[2]}` | `{t[3]}` | {t[4]} |\n")

    fname.write_text("".join(lines), encoding="utf-8")
    print(f"  ✅ Written: {fname}")

def write_architecture_drift_report(root: Path, nexus_reachable: Set[str], anomaly_reachable: Set[str]):
    fname = FORENSICS_DIR / "ARCHITECTURE_DRIFT_REPORT.md"
    lines = ["# ARCHITECTURE DRIFT REPORT\n\n",
             "Generated by: `scripts/forensic_audit.py` — Phase 4 (Drift)\n\n",
             "Tracks what happened to each original NEXUS-ATMS feature in the current codebase.\n\n",
             "| Feature | Files Present? | NEXUS Reachable? | ANOMALY Reachable? | Status | Notes |\n",
             "|---|---|---|---|---|---|\n"]
    for feature, info in ORIGINAL_FEATURES.items():
        present = any((root / f).exists() for f in info["files"])
        in_nexus = any(f.replace("\\", "/") in nexus_reachable for f in info["files"])
        in_anomaly = any(f.replace("\\", "/") in anomaly_reachable for f in info["files"])
        if in_nexus and in_anomaly:
            status = "🟢 ACTIVE (SHARED)"
        elif in_nexus:
            status = "🟡 NEXUS_ONLY"
        elif in_anomaly:
            status = "🔵 ANOMALY_ONLY"
        elif present:
            status = "🔴 ORPHANED (Present but unreachable)"
        else:
            status = "⚫ MISSING (Files not found)"
        lines.append(f"| **{feature}** | {'✅' if present else '❌'} | {'✅' if in_nexus else '❌'} | {'✅' if in_anomaly else '❌'} | {status} | {info['description'][:60]}... |\n")
    fname.write_text("".join(lines), encoding="utf-8")
    print(f"  ✅ Written: {fname}")

def write_boundary_matrix(rows: List[Dict]):
    fname = FORENSICS_DIR / "BOUNDARY_MATRIX.md"
    lines = ["# REPOSITORY BOUNDARY MATRIX\n\n",
             "Generated by: `scripts/forensic_audit.py` — Phase 5\n\n",
             "> Every file in the repository classified by which project it belongs to.\n\n",
             "| File | NEXUS | ANOMALY | Shared | Delete? |\n|---|---|---|---|---|\n"]
    for row in rows:
        lines.append(f"| `{row['file']}` | {row['nexus']} | {row['anomaly']} | {row['shared']} | {row['delete']} |\n")
    # Summary
    nexus_only = sum(1 for r in rows if r["nexus"] == "✅" and r["anomaly"] == "❌")
    anomaly_only = sum(1 for r in rows if r["nexus"] == "❌" and r["anomaly"] == "✅")
    shared = sum(1 for r in rows if r["shared"] == "✅")
    candidates = sum(1 for r in rows if r["delete"] == "⚠️ Candidate")
    lines.append(f"\n## Summary\n- NEXUS-only files: **{nexus_only}**\n- ANOMALY-only files: **{anomaly_only}**\n- Shared files: **{shared}**\n- Deletion candidates: **{candidates}**\n")
    fname.write_text("".join(lines), encoding="utf-8")
    print(f"  ✅ Written: {fname}")

def write_dead_code_report_v2(all_files: List[str], nexus_reachable: Set[str],
                               anomaly_reachable: Set[str]):
    fname = FORENSICS_DIR / "DEAD_CODE_REPORT_V2.md"
    categories = defaultdict(list)
    for f in sorted(all_files):
        cat = classify_file(f, nexus_reachable, anomaly_reachable,
                            NEXUS_CORE_FILES_SNAPSHOT, ANOMALY_ERA_FILES)
        categories[cat].append(f)

    lines = ["# DEAD CODE REPORT v2\n\n",
             "Generated by: `scripts/forensic_audit.py` — Phase 4\n\n",
             "Categories: `SHARED` | `NEXUS_ONLY` | `ANOMALY_ONLY` | `LEGACY` | `ORPHANED` | `DEAD`\n\n"]
    for cat in ["SHARED", "NEXUS_ONLY", "ANOMALY_ONLY", "LEGACY", "ORPHANED", "DEAD"]:
        files = categories.get(cat, [])
        emoji = {"SHARED": "🟢", "NEXUS_ONLY": "🟡", "ANOMALY_ONLY": "🔵",
                 "LEGACY": "🟠", "ORPHANED": "🔴", "DEAD": "⚫"}.get(cat, "")
        lines.append(f"## {emoji} {cat} ({len(files)} files)\n\n")
        for f in files:
            lines.append(f"- `{f}`\n")
        lines.append("\n")
    fname.write_text("".join(lines), encoding="utf-8")
    print(f"  ✅ Written: {fname}")

# ──────────────────────────────── MAIN ─────────────────────────────────────

def main():
    print(f"\n{'='*60}")
    print("NEXUS-ATMS FORENSIC AUDIT — Starting")
    print(f"Root: {ROOT}")
    print(f"{'='*60}\n")

    # ── Phase 1: Static Dependency Map ──
    print("PHASE 1: Building Static AST Import Graph...")
    py_files = get_all_py_files(ROOT)
    print(f"  Found {len(py_files)} Python files")
    graph, warnings = build_import_graph(py_files, ROOT)
    write_static_dependency_map(graph, warnings, ROOT)

    # ── Phase 2: Runtime Entry Point Analysis ──
    print("\nPHASE 2: Tracing Runtime Reachability...")

    # NEXUS reachability
    nexus_reachable = trace_reachable(NEXUS_ROOTS, graph, ROOT)
    print(f"  NEXUS reachable files: {len(nexus_reachable)}")

    # ANOMALY reachability
    anomaly_reachable = trace_reachable(ANOMALY_ROOTS, graph, ROOT)
    print(f"  ANOMALY reachable files: {len(anomaly_reachable)}")

    # FastAPI routes
    all_routes = []
    nexus_routes = []
    anomaly_routes = []
    for py in py_files:
        rel = str(py.relative_to(ROOT)).replace("\\", "/")
        routes = extract_fastapi_routes(py)
        if routes:
            if rel in nexus_reachable:
                nexus_routes.extend(routes)
            if rel in anomaly_reachable:
                anomaly_routes.extend(routes)
            all_routes.extend(routes)

    # Docker/shell entrypoints
    docker_info = scan_docker_entrypoints(ROOT)

    write_runtime_map("NEXUS", nexus_reachable, NEXUS_ROOTS, nexus_routes, docker_info, ROOT)
    write_runtime_map("ANOMALY", anomaly_reachable, ANOMALY_ROOTS, anomaly_routes, docker_info, ROOT)

    # ── Phase 3: Frontend Traceability ──
    print("\nPHASE 3: Building Frontend ↔ Backend Traceability...")
    trace = build_frontend_traceability(ROOT)
    print(f"  Components with API calls: {len(trace)}")
    write_frontend_traceability(trace, ROOT)

    # ── Phase 4: Architecture Drift + Dead Code ──
    print("\nPHASE 4: Architecture Drift + Dead Code Detection...")
    write_architecture_drift_report(ROOT, nexus_reachable, anomaly_reachable)

    # All Python files as relative paths
    all_py_rel = [str(f.relative_to(ROOT)).replace("\\", "/") for f in py_files]
    write_dead_code_report_v2(all_py_rel, nexus_reachable, anomaly_reachable)

    # ── Phase 5: Boundary Matrix ──
    print("\nPHASE 5: Building Repository Boundary Matrix...")
    rows = build_boundary_matrix(all_py_rel, nexus_reachable, anomaly_reachable)
    write_boundary_matrix(rows)

    print(f"\n{'='*60}")
    print("FORENSIC AUDIT COMPLETE")
    print(f"All reports written to: {FORENSICS_DIR}")
    print(f"{'='*60}")
    print("\nGenerated Reports:")
    for f in sorted(FORENSICS_DIR.glob("*.md")):
        print(f"  📄 {f.name}")


if __name__ == "__main__":
    main()
