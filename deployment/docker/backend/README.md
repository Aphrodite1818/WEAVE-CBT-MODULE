# Backend Docker Architecture

Phase 1 uses a single production deployment path:

1. `entrypoints/` — explicit API and worker program entry points used by the compiled build.
2. `nuitka/` — Nuitka build configuration for compiling the API and worker separately from the same backend source tree.
3. `Dockerfile` — multi-stage backend image that compiles both entry points in a builder stage and copies only compiled runtime artifacts into the final image.

Source correctness is validated by CI before the production build. We are intentionally not maintaining a separate source-based Docker image.

The API and worker remain separate processes but are shipped from the same versioned backend image.

No runtime implementation is present in this scaffold yet.
