// Sentry error reporting for the browser bundle (GEN-37). This module must be
// the first import in main.jsx so the SDK is initialized before any app code
// can throw. The DSN is baked in at build time from VITE_SENTRY_DSN, which
// only the image build sets (see Dockerfile) — mirroring the backend's
// SENTRY_DSN gate — so the Vite dev server, the Playwright e2e run, and local
// production builds never send events. The DSN only permits submitting
// events, so shipping it in the bundle is fine.
import * as Sentry from "@sentry/react";

const dsn = import.meta.env.VITE_SENTRY_DSN;
if (dsn) {
  Sentry.init({ dsn });
}
