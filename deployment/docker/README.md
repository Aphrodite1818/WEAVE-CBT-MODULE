# Phase 1 Docker Architecture

This directory contains the deployment scaffolding for containerizing WEAVE CBT.

Phase 1 is intentionally split into two production tracks:

- `backend/` — compile the FastAPI API and ARQ worker with Nuitka, then package only compiled runtime artifacts in the backend image. Source correctness is handled by CI; there is no separate source-based backend image.
- `frontend/` — build the staff and student Vite applications and package only their static production output for container runtime.

After both images are implemented, focused smoke tests will validate the actual production containers before release.

PostgreSQL, Redis, Compose orchestration, LAN networking, DNS, TLS, Windows appliance management, backups, installers, and updating are outside this phase and will be added in later deployment phases.
