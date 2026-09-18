# Phase 1 Docker Architecture

This directory contains the deployment scaffolding for containerizing WEAVE CBT.

Phase 1 is intentionally split into two tracks:

- `backend/` — first prove the Python backend runs correctly in Docker, then add Nuitka compilation and a source-free production runtime image.
- `frontend/` — build the staff and student Vite applications and package the static production output for container runtime.

PostgreSQL, Redis, Compose orchestration, LAN networking, DNS, TLS, Windows appliance management, backups, installers, and updating are outside this phase and will be added in later deployment phases.
