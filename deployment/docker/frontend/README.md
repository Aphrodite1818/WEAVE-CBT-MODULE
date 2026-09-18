# Frontend Docker Architecture

The Phase 1 frontend image will use a multi-stage build:

1. Build stage: install frontend dependencies and run the existing production Vite build for both staff and student applications.
2. Runtime stage: copy only the generated static assets into a lightweight web-server image.

The final runtime image must not contain the development server, `node_modules`, or the frontend source tree.

Reverse-proxy routing, LAN exposure, DNS and TLS are later deployment phases; this scaffold only establishes the frontend container boundary.
