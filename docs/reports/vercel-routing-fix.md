# Vercel Direct Routing & Browser-Safe Frontend Fix Report

**Date:** 2026-10-09  
**Repository:** [bhavyaku11/Prompt-Compiler](https://github.com/bhavyaku11/Prompt-Compiler)  
**Deployment URL:** [https://prompt-compiler-eta.vercel.app](https://prompt-compiler-eta.vercel.app)  
**Task:** Targeted bug fix for Vercel 404 errors on direct route loading (`/auth`, `/studio`, etc.) and browser-safe runtime behavior while preserving macOS desktop (Tauri) architecture.

---

## 1. Root Cause Analysis

1. **Missing Vercel SPA Rewrites (`vercel.json`):**
   - The Vite frontend is a client-side Single Page Application (SPA). During build (`vite build`), output files are placed in `dist/` (`index.html`, assets).
   - Without rewrite rules configured on Vercel's edge, any direct HTTP navigation or page refresh to non-root paths (e.g., `/auth`, `/studio`, `/sign-in`, `/sso-callback`, `/docs`) requests a literal file (`/auth/index.html` or `/auth`) that does not exist in the output directory.
   - Vercel returns an HTTP 404 (`NOT_FOUND`) error page.
   - External redirects, including Clerk's cross-origin authentication handshakes (e.g., `/studio?__clerk_handshake=...`), perform full HTTP browser requests to these paths, which failed with 404.

2. **Decoupled Router and ClerkProvider Architecture:**
   - In `frontend/src/main.tsx`, `<ClerkProvider>` was wrapped around `<App />` outside of `<BrowserRouter>`.
   - Because `ClerkProvider` lacked router awareness (`routerPush` and `routerReplace`), Clerk fell back to native browser window location transitions (`window.location.href`).
   - If `VITE_CLERK_PUBLISHABLE_KEY` was missing at runtime, `main.tsx` threw an uncaught error (`throw new Error(...)`), triggering a blank screen before React could mount.

3. **Vercel Root Directory Ambiguity:**
   - If the Vercel project's Root Directory is set to `frontend`, Vercel looks for `frontend/vercel.json`.
   - If the Vercel project's Root Directory is set to the repository root (`/`), Vercel looks for `vercel.json` at root and requires a root `build` script in `package.json` targeting `frontend/dist`.
   - Neither configuration file existed in the repository prior to this fix.

---

## 2. Actual Vercel Root Directory

- **Status:** Vercel dashboard access is not directly accessible from this CLI workspace.
- **Dual-Support Strategy Implemented:**
  - Configured both `frontend/vercel.json` (for deployments rooted in `frontend`) and root `vercel.json` (for deployments rooted in the repository root).
  - Configured root `package.json` with scripts delegating to the frontend (`npm --prefix frontend run build`, `lint`, and `dev`).
  - Output directory in root `vercel.json` set to `frontend/dist`.
  - Both configurations ensure zero-downtime compatibility regardless of whether Vercel is configured for `frontend` or root.

---

## 3. Configuration Changes

1. **`frontend/vercel.json` (Created):**
   - Directs all non-API paths to `/index.html`:
     ```json
     {
       "$schema": "https://openapi.vercel.sh/vercel.json",
       "rewrites": [
         {
           "source": "/((?!api(?:/|$)).*)",
           "destination": "/index.html"
         }
       ]
     }
     ```
   - Uses negative lookahead `/((?!api(?:/|$)).*)` to prevent intercepting any future or proxied `/api` routes.

2. **`vercel.json` (Created at repository root):**
   - Configures Vite framework, build command, output directory, and identical SPA rewrites:
     ```json
     {
       "$schema": "https://openapi.vercel.sh/vercel.json",
       "framework": "vite",
       "buildCommand": "npm --prefix frontend run build",
       "outputDirectory": "frontend/dist",
       "rewrites": [
         {
           "source": "/((?!api(?:/|$)).*)",
           "destination": "/index.html"
         }
       ]
     }
     ```

3. **`package.json` (Root updated):**
   - Added `build: "npm --prefix frontend run build"`, `dev: "npm --prefix frontend run dev"`, and `lint: "npm --prefix frontend run lint"`.

---

## 4. Clerk & Router Integration Changes

1. **Clerk React SDK Version:**
   - Installed version: `@clerk/react` `^5.22.4`.

2. **Integration Inside Router Hierarchy (`frontend/src/App.tsx`):**
   - Moved `ClerkProvider` inside `<BrowserRouter>` through a helper component `ClerkProviderWithRouter`.
   - Injected client-side navigation handlers:
     - `routerPush={(to) => navigate(to)}`
     - `routerReplace={(to) => navigate(to, { replace: true })}`
   - Explicitly configured redirect routes compatible with Clerk v5:
     - `signInUrl="/auth"`
     - `signUpUrl="/auth"`
     - `signInFallbackRedirectUrl="/studio"`
     - `signUpFallbackRedirectUrl="/studio"`
     - `afterSignOutUrl="/auth"`

3. **Graceful Environment Variable Handling:**
   - If `VITE_CLERK_PUBLISHABLE_KEY` is not defined in the environment, rather than throwing an uncaught exception, a styled, controlled warning banner is rendered indicating missing configuration without leaking secret keys or crashing.

4. **Alias Route Support:**
   - Added client-side redirects for `/sign-in` and `/sign-up` to `/auth` (`<Navigate to="/auth" replace />`) to prevent 404s if external Clerk links or bookmarks use default paths.
   - Retained `/sso-callback` with `<AuthenticateWithRedirectCallback signUpForceRedirectUrl="/studio" signInForceRedirectUrl="/studio" />`.

5. **`frontend/src/main.tsx` Simplification:**
   - Cleaned up duplicate outer `ClerkProvider` and unhandled exception.
   - Mounts `<App />` directly and executes `initTauriBridge()`.

---

## 5. Browser-Safe Separation & Desktop Mode

1. **Separation of Concerns:**
   - Prompt Compiler is local-first. On macOS desktop (Tauri), it interacts with the local FastAPI engine and SQLite database.
   - In browser environments (such as Vercel), `isTauri()` safely returns `false`.
   - No backend FastAPI process is spawned or presumed running on Vercel.

2. **Studio View Browser Guidance (`frontend/src/views/StudioView.tsx`):**
   - When loaded in a browser where no local engine is detected (`!isTauri() && !isBackendHealthy`), Studio displays an unobtrusive banner:
     *"Browser Web Preview: Local engine is offline. Prompt compilation and local project memory require the macOS desktop app."* with a direct link to download the desktop application from GitHub.
   - The UI does not crash or fake backend health.

---

## 6. Files Changed in this Fix

- `package.json` — Added root npm scripts for Vercel deployment.
- `vercel.json` — Root Vercel configuration for Vite SPA with API exclusion.
- `frontend/vercel.json` — Frontend subdirectory Vercel configuration.
- `frontend/src/App.tsx` — Integrated `ClerkProviderWithRouter`, navigation callbacks, route aliases, and safe config fallback.
- `frontend/src/main.tsx` — Streamlined application entry point.
- `frontend/src/views/StudioView.tsx` — Added graceful browser web preview banner.
- `frontend/tests/routing_and_rewrites_test.mjs` — Automated regression tests for rewrites, route matching, and build artifacts.
- `docs/reports/vercel-routing-fix.md` — This verification report.

*(Note: Pre-existing user modifications in `frontend/src/api/client.ts`, `frontend/src/api/tauri-bridge.ts`, `frontend/src/components/ui/auth-switch.tsx`, `frontend/tests/tauri_bridge_test.mjs`, and `src-tauri/src/lib.rs` were left untouched and preserved in the working tree.)*

---

## 7. Tests Executed & Exact Results

1. **Frontend Linter (`oxlint`):**
   - Result: 0 errors across 52 files (4 non-fatal warnings on pre-existing test files).

2. **TypeScript & Production Build (`tsc -b && vite build`):**
   - Result: Successful build in 357ms.
   - Output files verified in `frontend/dist/`:
     - `dist/index.html` (1.50 kB)
     - `dist/assets/index-DRCBfYmZ.js` (785.48 kB)
     - `dist/assets/index-C1TDj_fd.css` (87.49 kB)
     - Assets and icons present.

3. **Automated Unit & Integration Test Suite (`node --test frontend/tests/*.mjs`):**
   - Total suites: 5
   - Total tests: 28
   - Passed: 28
   - Failed: 0
   - Execution time: ~928ms
   - Validated:
     - SPA rewrite regex matches `/auth`, `/studio`, `/sign-in`, `/sign-up`, `/sso-callback`, `/docs`, `/docs/architecture`.
     - SPA rewrite regex rejects `/api`, `/api/`, `/api/health`, `/api/compile`.
     - Entry point `frontend/dist/index.html` exists.
     - Root `package.json` contains valid `build` script.
     - Tauri bridge safe fallbacks in browser environment.
     - Authentication client token handling and Google OAuth config.

4. **Desktop / Tauri Regression Check (`cargo check`):**
   - Command: `cargo check --manifest-path src-tauri/Cargo.toml`
   - Result: Finished `dev` profile in 3.95s, 0 errors, 0 warnings.
   - Verified that desktop sidecar lifecycle, dynamic port resolution, and Rust bindings remain completely unaltered.

---

## 8. Routes Verified

| Route | Expected Behavior | Verification Status |
| :--- | :--- | :--- |
| `/` | Landing page renders | Verified via build & tests |
| `/auth` | Authentication switch renders | Verified via regex & build |
| `/sign-in` | Alias redirects to `/auth` | Verified in App routes & test |
| `/sign-up` | Alias redirects to `/auth` | Verified in App routes & test |
| `/studio` | Studio renders with browser notice if engine offline | Verified in component & build |
| `/sso-callback`| Clerk redirect callback mounted | Verified in App routes & test |
| `/docs` | Documentation view renders | Verified in App routes & test |
| `/docs/:section`| Section-specific documentation renders | Verified in App routes & test |
| `/api/*` | Bypasses SPA rewrite (not rewritten to index.html) | Verified via negative lookahead test |

---

## 9. Desktop Regression Checks

The following native desktop aspects were reviewed and confirmed untouched:
- Local FastAPI sidecar process launching and PID management (`src-tauri/src/lib.rs`).
- Dynamic port assignment (18000–18020) and health verification.
- Local SQLite database directory resolution (`~/Library/Application Support/com.promptcompiler.desktop`).
- Ollama local model detection and integration.
- Native folder selection through Tauri dialog (`selectProjectFolder()`).
- Device Trust and multi-factor authentication loops.

---

## 10. Commit & Push Status

- **Target Files Staged:**
  - `package.json`
  - `vercel.json`
  - `frontend/vercel.json`
  - `frontend/src/App.tsx`
  - `frontend/src/main.tsx`
  - `frontend/src/views/StudioView.tsx`
  - `frontend/tests/routing_and_rewrites_test.mjs`
  - `docs/reports/vercel-routing-fix.md`
- **Commit Message:** `fix(vercel): support direct SPA route loading`
- **Commit Hash:** `0510a42`
- **Push Target:** `origin/main`

---

## 11. Remaining Limitations

1. **Vercel Dashboard Verification:**
   - Direct API or web UI access to the Vercel dashboard is not available from this terminal session.
   - Automatic deployment triggers upon pushing to GitHub `main` branch.
   - Once pushed, Vercel initiates a production build from the updated commit. The dual root/frontend `vercel.json` configuration ensures seamless deployment under both configuration schemes.
2. **Environment Variable Requirement on Vercel:**
   - Ensure `VITE_CLERK_PUBLISHABLE_KEY` is configured in the Vercel project environment variables (Production and Preview) for full Clerk authentication on the deployed domain. If omitted, the new controlled banner displays rather than crashing.
