// Sentry error reporting for the browser bundle (GEN-37). This module must be
// the first import in main.jsx so the SDK is initialized before any app code
// can throw. The DSN only permits submitting events — it ships in the bundle
// like any frontend config. Gated on PROD so the Vite dev server and the
// Playwright e2e run (which uses `npm run dev`) never send events.
import * as Sentry from "@sentry/react";

if (import.meta.env.PROD) {
  Sentry.init({
    dsn: "https://ec8aed6d6e3a722cb856e77d2dabf976@o4508060872409088.ingest.us.sentry.io/4511892462567424",
  });
}
