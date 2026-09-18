# Backend Docker Architecture

Phase 1 backend deployment is implemented in checkpoints:

1. `Dockerfile.source` — baseline image that runs the existing Python application normally inside Linux Docker.
2. `entrypoints/` — explicit API and worker program entry points used by the compiled build.
3. `nuitka/` — Nuitka build configuration for compiling the API and worker separately from the same backend source tree.
4. `Dockerfile.production` — multi-stage production image that compiles in a builder stage and copies only runtime artifacts into the final image.

The API and worker remain separate processes but may be shipped in the same versioned backend image.

No runtime implementation is present in this scaffold yet.
