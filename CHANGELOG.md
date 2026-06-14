# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [Portfolio Transformation] - 2026-06-14

### Added
- A comprehensive `pytest` testing suite validating imports and core logic execution.
- Extensive production-quality documentation (`API.md`, `BACKEND_ARCHITECTURE.md`, `benchmarks.md`).
- Backend modularization, introducing `api/`, `services/`, and `core/` layers using the Strangler Fig pattern.
- Strict requirement manifests (`requirements-full.txt` and `requirements-dev.txt`) for improved reproducibility.

### Changed
- Refactored `README.md` to highlight verified recruiter-facing metrics (D3QN wait-time reduction, Anomaly F1/Recall).
- Consolidated global configurations into `backend/core/config.py`.
- Repaired and optimized CI/CD GitHub action workflows to ensure automated verification.

### Fixed
- Workflow failure issues causing CI pipelines to stall on dependency conflicts.
- Duplicate implementations of code snippets within the monolith backend.

### Removed
- Internal security-sensitive artifacts and `.env` files that were improperly tracked.
- Stale, orphaned scripts lacking documentation or context.
