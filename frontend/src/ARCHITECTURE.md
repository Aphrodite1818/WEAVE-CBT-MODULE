# Frontend architecture

The frontend is organized by responsibility rather than by generic file type.

```text
src/
  app/       application composition, global reducer, gateway wiring
  api/       HTTP transport adapters grouped by backend domain
  features/  role/user-facing feature modules
  shared/    reusable UI and icon primitives with no feature ownership
  styles/    application-wide CSS
  assets/    bundled static assets
```

## Boundaries

- `app/` may compose features, shared primitives, and API-backed gateways.
- `api/` owns HTTP details. Feature components use the domain adapters through the app gateway rather than calling `fetch` directly.
- `features/` owns user-facing flows. Feature-specific components, pages, hooks, and CSS stay inside their feature folder.
- `shared/` contains reusable presentation primitives only. It must not depend on a feature.
- `styles/` contains truly global styles. Feature-specific styles stay with the feature.
- Avoid recreating generic top-level `components/`, `lib/`, `services/`, or `state/` buckets. Put code under the owner that gives it context.

`src/App.jsx` re-exports the application root for tests and imports. The real application root is `src/app/App.jsx`.
