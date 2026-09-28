# Task 31 Auth Fix — Handle Clerk Device Trust (`needs_client_trust`)

**Date**: 2026-09-27  
**Status**: COMPLETE  

---

## 1. Root Cause

When password authentication occurs on a new or untrusted device, Clerk's security layer triggers Device Trust (formerly known as Client Trust). Instead of returning `status: "complete"`, Clerk returns:

```ts
signIn.status === "needs_client_trust"
```

In the previous implementation of [auth-switch.tsx](file:///Users/bhavyakumar/prompt-compiler/frontend/src/components/ui/auth-switch.tsx), any sign-in attempt resulting in a status other than `"complete"` was treated as an unhandled status and simply displayed:

```text
"Sign in status: needs_client_trust. Additional verification needed."
```

There was no UI or API flow to initiate second factor verification, enter the verification code, or complete the session.

---

## 2. Clerk Device Trust Behavior

- **Trigger**: New or untrusted browser/device signing in with password credentials.
- **Precedence**: If both Device Trust and user-configured MFA (two-step verification) are enabled, MFA takes precedence (`needs_second_factor`). If only Device Trust is triggered, the status is `needs_client_trust`.
- **Supported Factors**: Clerk populates `signIn.supportedSecondFactors` with the available secondary challenge methods configured on the instance (typically `email_code`, `phone_code`, or `email_link`).
- **Lifecycle**:
  1. Password accepted: `signIn.create({ identifier, password })` returns `needs_client_trust`.
  2. Factor discovery: Inspect `signIn.supportedSecondFactors` (preferring `email_code`).
  3. Factor preparation: Call `signIn.prepareSecondFactor({ strategy: "email_code", emailAddressId })` to dispatch the verification code to the user's email.
  4. Challenge submission: User submits code via `signIn.attemptSecondFactor({ strategy: "email_code", code })`.
  5. Completion: On `status: "complete"`, finalize active session via `setSignInActive({ session: result.createdSessionId })` and navigate to `/studio`.

---

## 3. Files Changed

- [frontend/src/components/ui/auth-switch.tsx](file:///Users/bhavyakumar/prompt-compiler/frontend/src/components/ui/auth-switch.tsx):
  - Added dedicated Device Trust / MFA state management (`isVerifyingDevice`, `deviceVerificationCode`, `deviceVerificationStrategy`, `deviceVerificationTarget`, `canResendDeviceCode`, etc.).
  - Updated `handleSignInSubmit` to intercept `needs_client_trust` and `needs_second_factor`.
  - Implemented dynamic factor selection inspecting `result.supportedSecondFactors`, prioritizing `email_code`, with fallbacks to `phone_code`, `totp`, `backup_code`, and `email_link`.
  - Added `handleVerifyDeviceSubmit` calling `signIn.attemptSecondFactor` with user-friendly error mapping (`form_code_incorrect`, `verification_expired`).
  - Added `handleResendDeviceCode` to re-trigger `signIn.prepareSecondFactor`.
  - Added `handleCancelDeviceVerification` / "Start over" to gracefully return to the sign-in form.
  - Implemented dedicated Device Verification UI preserving the dark/light design system, grid aesthetics, and black/green styling.
  - Reset device verification states upon switching between sign-in and sign-up promotional panels.
- [docs/reports/task-31-fix-clerk-device-trust.md](file:///Users/bhavyakumar/prompt-compiler/docs/reports/task-31-fix-clerk-device-trust.md):
  - Created comprehensive documentation report.

---

## 4. SDK Version

- **Package**: `@clerk/react@6.17.2` (via `@clerk/react/legacy` hooks `useSignIn` and `useSignUp`)
- **API Surface**:
  - `signIn.create({ identifier, password })`
  - `signIn.supportedSecondFactors`
  - `signIn.prepareSecondFactor({ strategy, emailAddressId / phoneNumberId })`
  - `signIn.attemptSecondFactor({ strategy, code })`
  - `setSignInActive({ session })`

---

## 5. Verification Strategy Selection Logic

```ts
const secondFactors = result.supportedSecondFactors || [];

// 1. Prefer email_code (most common and user-friendly for desktop/web)
const emailFactor = secondFactors.find((f) => f.strategy === "email_code");
if (emailFactor) {
  await result.prepareSecondFactor({ strategy: "email_code", emailAddressId: emailFactor.emailAddressId });
  // switch UI to email verification mode
}

// 2. Fall back to phone_code (SMS)
const phoneFactor = secondFactors.find((f) => f.strategy === "phone_code");
if (phoneFactor) {
  await result.prepareSecondFactor({ strategy: "phone_code", phoneNumberId: phoneFactor.phoneNumberId });
  // switch UI to SMS verification mode
}

// 3. Fall back to TOTP (Authenticator App)
const totpFactor = secondFactors.find((f) => f.strategy === "totp");
if (totpFactor) {
  // prompt for authenticator code (no preparation needed)
}

// 4. Fall back to backup_code
const backupFactor = secondFactors.find((f) => f.strategy === "backup_code");
if (backupFactor) {
  // prompt for emergency recovery backup code
}
```

---

## 6. Verification Results

### A. Frontend Linting
```bash
npm --prefix ./frontend run lint
```
**Output**:
```text
Found 0 warnings and 0 errors.
Finished in 39ms on 40 files with 116 rules using 8 threads.
```

### B. Frontend Production Build
```bash
npm --prefix ./frontend run build
```
**Output**:
```text
vite v8.3.1 building client environment for production...
✓ 2008 modules transformed.
dist/index.html                                 1.49 kB │ gzip:   0.73 kB
dist/assets/index-B6NmCu5E.js                 696.37 kB │ gzip: 205.78 kB
✓ built in 298ms
```

### C. Rust Tauri Cargo Check
```bash
cargo check
```
**Output**:
```text
Finished `dev` profile [unoptimized + debuginfo] target(s) in 0.57s
```

### D. Backend Tests
```bash
pytest backend/tests/test_desktop_runtime.py backend/tests/test_data_ownership.py backend/tests/test_database.py backend/tests/test_standalone_executable.py backend/tests/test_auth.py
```
**Output**:
```text
======================== 96 passed, 1 warning in 42.04s ========================
```

### E. Runtime Environment Verification
- **Vite Server**: Port `5173` active with live HMR.
- **HTTP /auth Endpoint**: Returns `HTTP/1.1 200 OK`.
- **Tauri Desktop Window**: Active process `PID 13886` (`com.apple.WebKit.WebContent` / `prompt-compiler`) connected to `localhost:5173`.
- **FastAPI Desktop Sidecar**: Active on dynamic desktop port `18001`.

---

## 7. Remaining Limitations

- Real Clerk authentication flow requires live user credentials and mailbox access to receive one-time passcodes from Clerk. The UI and SDK handler are fully wired and ready for interactive user login.
- Task 32 has NOT been started, per instructions.
