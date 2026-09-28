"use client";

import { useState, useEffect, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { useSignIn, useSignUp } from "@clerk/react/legacy";
import { Mail, Lock, User, ArrowLeft, KeyRound } from "lucide-react";
import { GoogleIcon } from "@/components/ui/icons";
import { ThemeToggle } from "@/components/ui/theme-toggle";
import { MagneticCursor } from "@/components/ui/magnetic-cursor";
import { MagneticButton } from "@/components/ui/magnetic-button";
import { Logo } from "@/components/ui/Logo";
import authBg from "@/assets/auth-bg.jpg";
import authSignupBg from "@/assets/auth-signup-bg.png";

export interface AuthSwitchProps {
  initialSignUp?: boolean;
  onBackToHome?: () => void;
}

export default function AuthSwitch({ initialSignUp = false, onBackToHome }: AuthSwitchProps) {
  const navigate = useNavigate();
  const { isLoaded: isSignInLoaded, signIn, setActive: setSignInActive } = useSignIn();
  const { isLoaded: isSignUpLoaded, signUp, setActive: setSignUpActive } = useSignUp();

  const [isSignUp, setIsSignUp] = useState(initialSignUp);

  const handleHomeNavigation = () => {
    if (onBackToHome) {
      onBackToHome();
    } else {
      navigate("/");
    }
  };

  const [signInEmail, setSignInEmail] = useState("");
  const [signInPassword, setSignInPassword] = useState("");
  const [signUpName, setSignUpName] = useState("");
  const [signUpEmail, setSignUpEmail] = useState("");
  const [signUpPassword, setSignUpPassword] = useState("");
  const [verificationCode, setVerificationCode] = useState("");
  const [isVerifying, setIsVerifying] = useState(false);
  const [authStatus, setAuthStatus] = useState<{ text: string; type: "info" | "success" | "error" } | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Sign-in Device Trust / 2FA verification states
  const [isVerifyingDevice, setIsVerifyingDevice] = useState(false);
  const [deviceVerificationCode, setDeviceVerificationCode] = useState("");
  const [deviceVerificationStrategy, setDeviceVerificationStrategy] = useState<string>("email_code");
  const [deviceVerificationFactorId, setDeviceVerificationFactorId] = useState<string | undefined>(undefined);
  const [deviceVerificationTarget, setDeviceVerificationTarget] = useState<string>("");
  const [deviceVerificationTitle, setDeviceVerificationTitle] = useState<string>("Verify your device");
  const [deviceVerificationPrompt, setDeviceVerificationPrompt] = useState<string>("");
  const [canResendDeviceCode, setCanResendDeviceCode] = useState(true);

  useEffect(() => {
    // Safeguard against Chrome automatically populating saved credentials into DOM inputs
    const clearBrowserAutofill = () => {
      const emailEl = document.getElementById("signin-email") as HTMLInputElement | null;
      const passEl = document.getElementById("signin-password") as HTMLInputElement | null;
      if (emailEl && document.activeElement !== emailEl && emailEl.value) {
        emailEl.value = "";
      }
      if (passEl && document.activeElement !== passEl && passEl.value) {
        passEl.value = "";
      }
    };

    const timer = setTimeout(clearBrowserAutofill, 80);
    return () => clearTimeout(timer);
  }, []);

  const handleSignInSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!isSignInLoaded || !signIn) return;

    if (!signInEmail || !signInPassword) {
      setAuthStatus({ text: "Please enter your email and password.", type: "error" });
      return;
    }

    setIsSubmitting(true);
    setAuthStatus({ text: "Signing in...", type: "info" });

    try {
      const result = await signIn.create({
        identifier: signInEmail.trim(),
        password: signInPassword,
      });

      if (result.status === "complete") {
        if (setSignInActive) {
          await setSignInActive({ session: result.createdSessionId });
        }
        setAuthStatus({ text: "Welcome back! Entering Studio...", type: "success" });
        setTimeout(() => {
          navigate("/studio");
        }, 300);
      } else if (result.status === "needs_client_trust" || result.status === "needs_second_factor") {
        const isDeviceTrust = result.status === "needs_client_trust";
        const title = isDeviceTrust ? "Verify your device" : "Two-step verification";
        setDeviceVerificationTitle(title);

        // Inspect supported second factors according to Clerk specifications
        const secondFactors = result.supportedSecondFactors || [];

        // 1. Prefer email_code factor when available
        const emailFactor = secondFactors.find(
          (f) => f.strategy === "email_code"
        ) as { strategy: "email_code"; emailAddressId?: string; safeIdentifier?: string } | undefined;

        if (emailFactor) {
          const target = emailFactor.safeIdentifier || signInEmail.trim();
          setDeviceVerificationStrategy("email_code");
          setDeviceVerificationFactorId(emailFactor.emailAddressId);
          setDeviceVerificationTarget(target);
          setCanResendDeviceCode(true);
          setDeviceVerificationPrompt(
            isDeviceTrust
              ? `A verification code was sent to ${target}. Enter it below to trust this device.`
              : `A verification code was sent to ${target}. Enter it below to complete sign-in.`
          );

          await result.prepareSecondFactor({
            strategy: "email_code",
            ...(emailFactor.emailAddressId ? { emailAddressId: emailFactor.emailAddressId } : {}),
          });

          setIsVerifyingDevice(true);
          setDeviceVerificationCode("");
          setAuthStatus({
            text: `Verification code sent to ${target}`,
            type: "info",
          });
          return;
        }

        // 2. Fall back to phone_code factor if email_code is not available
        const phoneFactor = secondFactors.find(
          (f) => f.strategy === "phone_code"
        ) as { strategy: "phone_code"; phoneNumberId?: string; safeIdentifier?: string } | undefined;

        if (phoneFactor) {
          const target = phoneFactor.safeIdentifier || "your phone";
          setDeviceVerificationStrategy("phone_code");
          setDeviceVerificationFactorId(phoneFactor.phoneNumberId);
          setDeviceVerificationTarget(target);
          setCanResendDeviceCode(true);
          setDeviceVerificationPrompt(
            isDeviceTrust
              ? `A verification code was sent via SMS to ${target}. Enter it below to trust this device.`
              : `A verification code was sent via SMS to ${target}. Enter it below to complete sign-in.`
          );

          await result.prepareSecondFactor({
            strategy: "phone_code",
            ...(phoneFactor.phoneNumberId ? { phoneNumberId: phoneFactor.phoneNumberId } : {}),
          });

          setIsVerifyingDevice(true);
          setDeviceVerificationCode("");
          setAuthStatus({
            text: `Verification code sent to ${target}`,
            type: "info",
          });
          return;
        }

        // 3. Fall back to TOTP (Authenticator application)
        const totpFactor = secondFactors.find((f) => f.strategy === "totp");
        if (totpFactor) {
          setDeviceVerificationStrategy("totp");
          setDeviceVerificationFactorId(undefined);
          setDeviceVerificationTarget("Authenticator App");
          setCanResendDeviceCode(false);
          setDeviceVerificationPrompt("Enter the 6-digit code generated by your authenticator app.");
          setIsVerifyingDevice(true);
          setDeviceVerificationCode("");
          setAuthStatus({
            text: "Please enter the code from your authenticator app.",
            type: "info",
          });
          return;
        }

        // 4. Fall back to backup_code
        const backupFactor = secondFactors.find((f) => f.strategy === "backup_code");
        if (backupFactor) {
          setDeviceVerificationStrategy("backup_code");
          setDeviceVerificationFactorId(undefined);
          setDeviceVerificationTarget("Backup Code");
          setCanResendDeviceCode(false);
          setDeviceVerificationPrompt("Enter one of your saved backup recovery codes.");
          setIsVerifyingDevice(true);
          setDeviceVerificationCode("");
          setAuthStatus({
            text: "Please enter your backup code.",
            type: "info",
          });
          return;
        }

        // 5. Fall back to email_link if supported
        const emailLinkFactor = secondFactors.find(
          (f) => f.strategy === "email_link"
        ) as { strategy: "email_link"; emailAddressId?: string; safeIdentifier?: string } | undefined;

        if (emailLinkFactor) {
          const target = emailLinkFactor.safeIdentifier || signInEmail.trim();
          await result.prepareSecondFactor({
            strategy: "email_link",
            emailAddressId: emailLinkFactor.emailAddressId || "",
            redirectUrl: `${window.location.origin}/sso-callback`,
          });
          setAuthStatus({
            text: `A verification link has been sent to ${target}. Please click it to continue.`,
            type: "info",
          });
          return;
        }

        // No supported factor found
        setAuthStatus({
          text: "Additional verification is required, but no supported verification method is available for your account.",
          type: "error",
        });
      } else if (result.status === "needs_identifier") {
        setAuthStatus({ text: "Please enter your email to continue.", type: "error" });
      } else if (result.status === "needs_first_factor") {
        setAuthStatus({ text: "Additional authentication required. Please try signing in again.", type: "error" });
      } else {
        setAuthStatus({
          text: "Sign-in could not be completed. Please check your credentials and try again.",
          type: "error",
        });
      }
    } catch (err: unknown) {
      const clerkErr = err as { errors?: Array<{ longMessage?: string; message?: string; code?: string }> };
      const firstErr = clerkErr?.errors?.[0];
      const errorMsg =
        firstErr?.longMessage ||
        firstErr?.message ||
        "Invalid email or password. Please try again.";
      setAuthStatus({ text: errorMsg, type: "error" });
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleVerifyDeviceSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!isSignInLoaded || !signIn || !deviceVerificationCode.trim()) {
      setAuthStatus({ text: "Please enter the verification code.", type: "error" });
      return;
    }

    setIsSubmitting(true);
    setAuthStatus({ text: "Verifying code...", type: "info" });

    try {
      let completeSignIn;
      if (deviceVerificationStrategy === "email_code") {
        completeSignIn = await signIn.attemptSecondFactor({
          strategy: "email_code",
          code: deviceVerificationCode.trim(),
        });
      } else if (deviceVerificationStrategy === "phone_code") {
        completeSignIn = await signIn.attemptSecondFactor({
          strategy: "phone_code",
          code: deviceVerificationCode.trim(),
        });
      } else if (deviceVerificationStrategy === "totp") {
        completeSignIn = await signIn.attemptSecondFactor({
          strategy: "totp",
          code: deviceVerificationCode.trim(),
        });
      } else if (deviceVerificationStrategy === "backup_code") {
        completeSignIn = await signIn.attemptSecondFactor({
          strategy: "backup_code",
          code: deviceVerificationCode.trim(),
        });
      } else {
        completeSignIn = await signIn.attemptSecondFactor({
          strategy: "email_code",
          code: deviceVerificationCode.trim(),
        });
      }

      if (completeSignIn.status === "complete") {
        if (setSignInActive) {
          await setSignInActive({ session: completeSignIn.createdSessionId });
        }
        setAuthStatus({ text: "Device verified! Entering Studio...", type: "success" });
        setTimeout(() => {
          navigate("/studio");
        }, 300);
      } else {
        setAuthStatus({
          text: "Verification was not completed. Additional steps needed.",
          type: "error",
        });
      }
    } catch (err: unknown) {
      const clerkErr = err as { errors?: Array<{ longMessage?: string; message?: string; code?: string }> };
      const firstErr = clerkErr?.errors?.[0];
      let errorMsg = firstErr?.longMessage || firstErr?.message || "Invalid verification code. Please try again.";
      if (firstErr?.code === "form_code_incorrect") {
        errorMsg = "Incorrect verification code. Please check your code and try again.";
      } else if (firstErr?.code === "verification_expired" || firstErr?.code === "code_expired") {
        errorMsg = "Verification code has expired. Please request a new code.";
      }
      setAuthStatus({ text: errorMsg, type: "error" });
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleResendDeviceCode = async () => {
    if (!isSignInLoaded || !signIn) return;
    setIsSubmitting(true);
    setAuthStatus({ text: "Sending new code...", type: "info" });

    try {
      if (deviceVerificationStrategy === "email_code") {
        await signIn.prepareSecondFactor({
          strategy: "email_code",
          ...(deviceVerificationFactorId ? { emailAddressId: deviceVerificationFactorId } : {}),
        });
        setAuthStatus({
          text: `A fresh verification code was sent to ${deviceVerificationTarget || signInEmail.trim()}`,
          type: "info",
        });
      } else if (deviceVerificationStrategy === "phone_code") {
        await signIn.prepareSecondFactor({
          strategy: "phone_code",
          ...(deviceVerificationFactorId ? { phoneNumberId: deviceVerificationFactorId } : {}),
        });
        setAuthStatus({
          text: `A fresh verification code was sent to ${deviceVerificationTarget || "your phone"}`,
          type: "info",
        });
      }
    } catch (err: unknown) {
      const clerkErr = err as { errors?: Array<{ longMessage?: string; message?: string; code?: string }> };
      const firstErr = clerkErr?.errors?.[0];
      const errorMsg = firstErr?.longMessage || firstErr?.message || "Could not resend code. Please try again in a moment.";
      setAuthStatus({ text: errorMsg, type: "error" });
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleCancelDeviceVerification = () => {
    setIsVerifyingDevice(false);
    setDeviceVerificationCode("");
    setAuthStatus(null);
  };

  const handleSignUpSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!isSignUpLoaded || !signUp) return;

    if (!signUpEmail || !signUpPassword) {
      setAuthStatus({ text: "Please enter your email and password.", type: "error" });
      return;
    }

    setIsSubmitting(true);
    setAuthStatus({ text: "Creating account...", type: "info" });

    try {
      const trimmedName = signUpName.trim();
      const nameParts = trimmedName ? trimmedName.split(" ") : [];
      const firstName = nameParts[0] || undefined;
      const lastName = nameParts.length > 1 ? nameParts.slice(1).join(" ") : undefined;

      const result = await signUp.create({
        emailAddress: signUpEmail.trim(),
        password: signUpPassword,
        ...(firstName ? { firstName } : {}),
        ...(lastName ? { lastName } : {}),
      });

      if (result.status === "complete") {
        if (setSignUpActive) {
          await setSignUpActive({ session: result.createdSessionId });
        }
        setAuthStatus({ text: "Account created! Entering Studio...", type: "success" });
        setTimeout(() => {
          navigate("/studio");
        }, 300);
      } else {
        // Clerk typically requires email verification
        await signUp.prepareEmailAddressVerification({ strategy: "email_code" });
        setIsVerifying(true);
        setAuthStatus({
          text: `Verification code sent to ${signUpEmail.trim()}`,
          type: "info",
        });
      }
    } catch (err: unknown) {
      const clerkErr = err as { errors?: Array<{ longMessage?: string; message?: string }> };
      const errorMsg =
        clerkErr?.errors?.[0]?.longMessage ||
        clerkErr?.errors?.[0]?.message ||
        "Could not create account. Please check your details.";
      setAuthStatus({ text: errorMsg, type: "error" });
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleVerifyEmailSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!isSignUpLoaded || !signUp || !verificationCode) {
      setAuthStatus({ text: "Please enter the 6-digit verification code.", type: "error" });
      return;
    }

    setIsSubmitting(true);
    setAuthStatus({ text: "Verifying code...", type: "info" });

    try {
      const completeSignUp = await signUp.attemptEmailAddressVerification({
        code: verificationCode.trim(),
      });

      if (completeSignUp.status === "complete") {
        if (setSignUpActive) {
          await setSignUpActive({ session: completeSignUp.createdSessionId });
        }
        setAuthStatus({ text: "Email verified! Entering Studio...", type: "success" });
        setTimeout(() => {
          navigate("/studio");
        }, 300);
      } else {
        setAuthStatus({
          text: `Verification status: ${completeSignUp.status}. Additional steps needed.`,
          type: "error",
        });
      }
    } catch (err: unknown) {
      const clerkErr = err as { errors?: Array<{ longMessage?: string; message?: string }> };
      const errorMsg =
        clerkErr?.errors?.[0]?.longMessage ||
        clerkErr?.errors?.[0]?.message ||
        "Invalid verification code. Please try again.";
      setAuthStatus({ text: errorMsg, type: "error" });
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleResendCode = async () => {
    if (!isSignUpLoaded || !signUp) return;
    setIsSubmitting(true);
    try {
      await signUp.prepareEmailAddressVerification({ strategy: "email_code" });
      setAuthStatus({ text: `A fresh verification code was sent to ${signUpEmail.trim()}`, type: "info" });
    } catch (err: unknown) {
      const clerkErr = err as { errors?: Array<{ longMessage?: string; message?: string }> };
      const errorMsg =
        clerkErr?.errors?.[0]?.longMessage ||
        clerkErr?.errors?.[0]?.message ||
        "Failed to resend code.";
      setAuthStatus({ text: errorMsg, type: "error" });
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleGoogleAuth = async (e?: React.MouseEvent) => {
    if (e) e.preventDefault();
    setIsSubmitting(true);
    setAuthStatus({ text: "Connecting to Google authentication...", type: "info" });

    try {
      if (isSignUp && signUp) {
        await signUp.authenticateWithRedirect({
          strategy: "oauth_google",
          redirectUrl: "/sso-callback",
          redirectUrlComplete: "/studio",
        });
      } else if (signIn) {
        await signIn.authenticateWithRedirect({
          strategy: "oauth_google",
          redirectUrl: "/sso-callback",
          redirectUrlComplete: "/studio",
        });
      }
    } catch (err: unknown) {
      setIsSubmitting(false);
      const clerkErr = err as { errors?: Array<{ longMessage?: string; message?: string }> };
      const errorMsg =
        clerkErr?.errors?.[0]?.longMessage ||
        clerkErr?.errors?.[0]?.message ||
        "Google authentication failed. Please try again.";
      setAuthStatus({ text: errorMsg, type: "error" });
    }
  };

  const handleForgotPassword = async (e: React.MouseEvent) => {
    e.preventDefault();
    if (!signInEmail) {
      setAuthStatus({ text: "Please enter your email above first", type: "info" });
      return;
    }
    if (!isSignInLoaded || !signIn) return;
    setIsSubmitting(true);
    try {
      await signIn.create({
        strategy: "reset_password_email_code",
        identifier: signInEmail.trim(),
      });
      setAuthStatus({ text: `Password reset instructions sent to ${signInEmail.trim()}`, type: "info" });
    } catch (err: unknown) {
      const clerkErr = err as { errors?: Array<{ longMessage?: string; message?: string }> };
      const msg = clerkErr?.errors?.[0]?.longMessage || clerkErr?.errors?.[0]?.message || "Could not start password reset.";
      setAuthStatus({ text: msg, type: "error" });
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <MagneticCursor magneticFactor={0.35} disableOnTouch={true}>
      <div className="auth-switch-root relative min-h-screen w-full bg-background text-foreground font-sans flex flex-col justify-center items-center p-4 sm:p-6 overflow-hidden transition-colors duration-300">
      
      {/* 52px Developer Grid matching Frontpage */}
      <div 
        className="absolute inset-0 z-0 bg-grid-pattern opacity-60 pointer-events-none" 
        aria-hidden="true" 
      />

      {/* Radial vignette overlay matching Frontpage */}
      <div 
        className="absolute inset-0 z-0 bg-vignette pointer-events-none" 
        aria-hidden="true" 
      />

      {/* Ambient center spotlight matching Footer Aurora */}
      <div 
        className="absolute inset-0 z-0 pointer-events-none flex items-center justify-center opacity-70"
        aria-hidden="true"
      >
        <div className="h-[600px] w-[900px] rounded-full bg-gradient-to-tr from-neutral-500/5 via-neutral-400/5 to-transparent blur-3xl dark:from-white/5 dark:via-white/[0.02] dark:to-transparent" />
      </div>

      <style>{`
        .auth-card-container,
        .auth-card-container * {
          box-sizing: border-box;
        }

        .auth-top-bar {
          position: absolute;
          top: 24px;
          left: 0;
          right: 0;
          width: 100%;
          max-width: 1200px;
          padding: 0 24px;
          margin: 0 auto;
          display: flex;
          justify-content: space-between;
          align-items: center;
          z-index: 20;
        }

        .auth-card-container {
          position: relative;
          width: 100%;
          max-width: 960px;
          height: 590px;
          background: #ffffff;
          border-radius: 24px;
          border: 1px solid rgba(0, 0, 0, 0.08);
          box-shadow: 0 25px 60px -15px rgba(0, 0, 0, 0.12);
          overflow: hidden;
          margin-top: 48px;
          z-index: 10;
          transition: all 0.3s ease;
        }

        .dark .auth-card-container {
          background: #08080a;
          border: 1px solid rgba(255, 255, 255, 0.1);
          box-shadow: 0 25px 70px -15px rgba(0, 0, 0, 0.8), 0 0 0 1px rgba(255, 255, 255, 0.03);
        }

        .forms-container {
          position: absolute;
          width: 100%;
          height: 100%;
          top: 0;
          left: 0;
          z-index: 20;
          pointer-events: none;
        }

        .signin-signup {
          position: absolute;
          top: 50%;
          transform: translate(-50%, -50%);
          left: 75%;
          width: 50%;
          transition: left 0.8s cubic-bezier(0.76, 0, 0.24, 1);
          display: grid;
          grid-template-columns: 1fr;
          z-index: 20;
          pointer-events: auto;
        }

        form {
          display: flex;
          align-items: center;
          justify-content: center;
          flex-direction: column;
          padding: 0 4.5rem;
          overflow: hidden;
          grid-column: 1 / 2;
          grid-row: 1 / 2;
          width: 100%;
          z-index: 20;
          pointer-events: auto;
        }

        form.sign-in-form {
          opacity: 1;
          transform: translateX(0);
          z-index: 25;
          pointer-events: auto;
          transition: opacity 0.4s 0.12s ease-out, transform 0.5s 0.12s cubic-bezier(0.76, 0, 0.24, 1);
        }

        form.sign-up-form {
          opacity: 0;
          transform: translateX(25px);
          z-index: 10;
          pointer-events: none;
          transition: opacity 0.25s ease-in, transform 0.3s ease-in;
        }

        .title {
          font-size: 2.1rem;
          color: #09090b;
          margin-bottom: 6px;
          font-weight: 700;
          letter-spacing: -0.025em;
          text-align: center;
        }

        .dark .title {
          color: #f8fafc;
        }

        .subtitle {
          font-size: 0.88rem;
          color: #71717a;
          margin-bottom: 22px;
          text-align: center;
          max-width: 320px;
          line-height: 1.45;
        }

        .dark .subtitle {
          color: #a1a1aa;
        }

        .input-group {
          width: 100%;
          max-width: 380px;
          margin: 6px 0;
        }

        .input-field {
          width: 100%;
          background-color: #f4f4f5;
          height: 50px;
          border-radius: 50px;
          display: grid;
          grid-template-columns: 14% 86%;
          padding: 0 0.8rem;
          position: relative;
          transition: all 0.25s ease;
          border: 1px solid rgba(0, 0, 0, 0.06);
          overflow: hidden;
          cursor: text;
        }

        .dark .input-field {
          background-color: #121215;
          border: 1px solid rgba(255, 255, 255, 0.12);
        }

        .input-field:focus-within {
          background-color: #ffffff;
          border-color: #09090b;
          box-shadow: 0 0 0 3px rgba(0, 0, 0, 0.08);
        }

        .dark .input-field:focus-within {
          background-color: #17171c;
          border-color: rgba(255, 255, 255, 0.35);
          box-shadow: 0 0 0 3px rgba(255, 255, 255, 0.1);
        }

        .input-field .icon-wrap {
          display: flex;
          align-items: center;
          justify-content: center;
          color: #71717a;
          transition: color 0.2s;
        }

        .dark .input-field .icon-wrap {
          color: #a1a1aa;
        }

        .input-field:focus-within .icon-wrap {
          color: #09090b;
        }

        .dark .input-field:focus-within .icon-wrap {
          color: #ffffff;
        }

        .input-field input {
          background: transparent;
          outline: none;
          border: none;
          line-height: 1;
          font-weight: 500;
          font-size: 0.95rem;
          color: #09090b;
          width: 100%;
          height: 100%;
          padding-right: 0.8rem;
          color-scheme: light;
        }

        .dark .input-field input {
          color: #f8fafc;
          color-scheme: dark;
        }

        .input-field input::placeholder {
          color: #a1a1aa;
          font-weight: 400;
        }

        .dark .input-field input::placeholder {
          color: #71717a;
        }

        /* Complete Autofill Reset to Prevent Ugly Light/White Blocks in Dark Mode */
        .dark .input-field input:-webkit-autofill,
        .dark .input-field input:-webkit-autofill:hover,
        .dark .input-field input:-webkit-autofill:focus,
        .dark .input-field input:-webkit-autofill:active {
          -webkit-box-shadow: 0 0 0 1000px #121215 inset !important;
          box-shadow: 0 0 0 1000px #121215 inset !important;
          -webkit-text-fill-color: #f8fafc !important;
          caret-color: #f8fafc !important;
          transition: background-color 5000s ease-in-out 0s;
        }

        .dark .input-field:focus-within input:-webkit-autofill,
        .dark .input-field:focus-within input:-webkit-autofill:hover,
        .dark .input-field:focus-within input:-webkit-autofill:focus,
        .dark .input-field:focus-within input:-webkit-autofill:active {
          -webkit-box-shadow: 0 0 0 1000px #17171c inset !important;
          box-shadow: 0 0 0 1000px #17171c inset !important;
          -webkit-text-fill-color: #f8fafc !important;
          caret-color: #f8fafc !important;
        }

        .dark .input-field input:autofill {
          box-shadow: 0 0 0 1000px #121215 inset !important;
          -webkit-text-fill-color: #f8fafc !important;
          caret-color: #f8fafc !important;
        }

        .input-field input:-webkit-autofill,
        .input-field input:-webkit-autofill:hover,
        .input-field input:-webkit-autofill:focus,
        .input-field input:-webkit-autofill:active {
          -webkit-box-shadow: 0 0 0 1000px #f4f4f5 inset !important;
          box-shadow: 0 0 0 1000px #f4f4f5 inset !important;
          -webkit-text-fill-color: #09090b !important;
          caret-color: #09090b !important;
          transition: background-color 5000s ease-in-out 0s;
        }

        .input-field:focus-within input:-webkit-autofill {
          -webkit-box-shadow: 0 0 0 1000px #ffffff inset !important;
          box-shadow: 0 0 0 1000px #ffffff inset !important;
          -webkit-text-fill-color: #09090b !important;
          caret-color: #09090b !important;
        }

        .forgot-password-row {
          width: 100%;
          max-width: 380px;
          display: flex;
          justify-content: flex-end;
          margin-top: 4px;
          margin-bottom: 10px;
        }

        .forgot-password-btn {
          background: none;
          border: none;
          color: #71717a;
          font-size: 0.8rem;
          font-weight: 500;
          cursor: pointer;
          transition: color 0.15s;
          padding: 0;
        }

        .dark .forgot-password-btn {
          color: #a1a1aa;
        }

        .forgot-password-btn:hover {
          color: #09090b;
          text-decoration: underline;
        }

        .dark .forgot-password-btn:hover {
          color: #ffffff;
        }

        /* High-Contrast Primary Submit Button (Matching Frontpage CTAs) */
        .btn-primary-auth {
          width: 100%;
          max-width: 380px;
          background-color: #09090b;
          color: #ffffff;
          border: none;
          outline: none;
          height: 48px;
          border-radius: 48px;
          font-weight: 600;
          margin: 10px 0;
          cursor: pointer;
          transition: all 0.25s ease;
          font-size: 0.92rem;
          letter-spacing: 0.01em;
          box-shadow: 0 4px 14px rgba(0, 0, 0, 0.15);
        }

        .btn-primary-auth:hover {
          background-color: #18181b;
          transform: translateY(-2px);
          box-shadow: 0 6px 20px rgba(0, 0, 0, 0.25);
        }

        .dark .btn-primary-auth {
          background-color: #ffffff;
          color: #09090b;
          box-shadow: 0 4px 14px rgba(255, 255, 255, 0.15);
        }

        .dark .btn-primary-auth:hover {
          background-color: #f4f4f5;
          transform: translateY(-2px);
          box-shadow: 0 6px 20px rgba(255, 255, 255, 0.25);
        }

        .btn-primary-auth:active {
          transform: translateY(0);
        }

        .social-divider {
          display: flex;
          align-items: center;
          width: 100%;
          max-width: 380px;
          margin: 14px 0 10px;
        }

        .social-text {
          font-size: 0.78rem;
          color: #a1a1aa;
          text-align: center;
          width: 100%;
          font-weight: 500;
          text-transform: uppercase;
          letter-spacing: 0.06em;
        }

        .dark .social-text {
          color: #71717a;
        }

        .social-media {
          display: flex;
          justify-content: center;
          gap: 16px;
          margin-top: 4px;
        }

        .social-icon-btn {
          height: 46px;
          width: 46px;
          display: flex;
          justify-content: center;
          align-items: center;
          border: 1px solid rgba(0, 0, 0, 0.1);
          border-radius: 50%;
          background: #ffffff;
          color: #09090b;
          transition: all 0.25s ease;
          cursor: pointer;
          box-shadow: 0 2px 4px rgba(0, 0, 0, 0.04);
        }

        .social-icon-btn:hover {
          border-color: rgba(0, 0, 0, 0.3);
          transform: translateY(-2px);
          box-shadow: 0 6px 16px rgba(0, 0, 0, 0.1);
        }

        .dark .social-icon-btn {
          background: rgba(255, 255, 255, 0.04);
          border: 1px solid rgba(255, 255, 255, 0.12);
          box-shadow: 0 2px 4px rgba(0, 0, 0, 0.3);
        }

        .dark .social-icon-btn:hover {
          border-color: rgba(255, 255, 255, 0.3);
          background: rgba(255, 255, 255, 0.08);
          transform: translateY(-2px);
          box-shadow: 0 6px 16px rgba(0, 0, 0, 0.4);
        }

        /* Ghost Artwork for Sign-In Mode (Left Section) */
        .auth-ghost-backdrop {
          position: absolute;
          top: 0;
          left: 0;
          width: 52%;
          height: 100%;
          z-index: 4;
          clip-path: url(#auth-ghost-curve);
          -webkit-clip-path: url(#auth-ghost-curve);
          pointer-events: none;
          overflow: hidden;
          transition: transform 0.8s cubic-bezier(0.76, 0, 0.24, 1), opacity 0.5s ease-in-out;
          transform: translateX(0);
          opacity: 1;
        }

        .auth-card-container.sign-up-mode .auth-ghost-backdrop {
          transform: translateX(-100%);
          opacity: 0;
        }

        .auth-ghost-img {
          width: 100%;
          height: 100%;
          object-fit: cover;
          object-position: center 15%;
          display: block;
        }

        .auth-ghost-overlay {
          position: absolute;
          inset: 0;
          background: linear-gradient(
            to bottom,
            rgba(0, 0, 0, 0.2) 0%,
            rgba(0, 0, 0, 0.35) 50%,
            rgba(0, 0, 0, 0.6) 100%
          );
          pointer-events: none;
        }

        /* Monster Hand Artwork for Sign-Up Mode (Right Section) */
        .auth-monster-backdrop {
          position: absolute;
          top: 0;
          right: 0;
          width: 53%;
          height: 100%;
          z-index: 4;
          clip-path: url(#auth-monster-curve);
          -webkit-clip-path: url(#auth-monster-curve);
          pointer-events: none;
          overflow: hidden;
          transition: transform 0.8s cubic-bezier(0.76, 0, 0.24, 1), opacity 0.5s ease-in-out;
          transform: translateX(100%);
          opacity: 0;
        }

        .auth-card-container.sign-up-mode .auth-monster-backdrop {
          transform: translateX(0);
          opacity: 1;
        }

        .auth-monster-img {
          width: 100%;
          height: 100%;
          object-fit: cover;
          object-position: center 20%;
          display: block;
        }

        .auth-monster-overlay {
          position: absolute;
          inset: 0;
          background: linear-gradient(
            to bottom,
            rgba(0, 0, 0, 0.15) 0%,
            rgba(0, 0, 0, 0.3) 50%,
            rgba(0, 0, 0, 0.6) 100%
          );
          pointer-events: none;
        }

        .panels-container {
          position: absolute;
          height: 100%;
          width: 100%;
          top: 0;
          left: 0;
          display: grid;
          grid-template-columns: repeat(2, 1fr);
          z-index: 15;
          pointer-events: none;
        }

        .panel {
          display: flex;
          flex-direction: column;
          align-items: flex-end;
          justify-content: space-around;
          text-align: center;
          z-index: 15;
          pointer-events: none;
        }

        .left-panel {
          pointer-events: none;
          padding: 3rem 16% 2rem 10%;
        }

        .right-panel {
          pointer-events: none;
          padding: 3rem 10% 2rem 16%;
        }

        .panel .content {
          color: #ffffff;
          max-width: 320px;
          pointer-events: auto;
        }

        .left-panel .content {
          transform: translateX(0);
          opacity: 1;
          transition: transform 0.75s cubic-bezier(0.76, 0, 0.24, 1) 0.1s, opacity 0.45s ease-out 0.1s;
        }

        .right-panel .content {
          transform: translateX(120px);
          opacity: 0;
          transition: transform 0.45s cubic-bezier(0.76, 0, 0.24, 1), opacity 0.25s ease-in;
        }

        .left-panel h3,
        .left-panel p,
        .right-panel h3,
        .right-panel p {
          text-shadow: 0 2px 14px rgba(0, 0, 0, 0.85);
        }

        .panel h3 {
          font-weight: 700;
          line-height: 1.2;
          font-size: 1.65rem;
          margin-bottom: 20px;
          letter-spacing: -0.02em;
          color: #ffffff;
        }

        .panel p {
          font-size: 0.92rem;
          line-height: 1.5;
          padding: 0.4rem 0 1.4rem;
          color: rgba(255, 255, 255, 0.85);
        }

        /* Glass Pill Secondary Button matching Frontpage */
        .btn-promo-switch {
          margin: 0 auto;
          background: rgba(255, 255, 255, 0.08);
          border: 1px solid rgba(255, 255, 255, 0.22);
          width: 144px;
          height: 44px;
          font-weight: 600;
          font-size: 0.86rem;
          border-radius: 44px;
          color: #ffffff;
          cursor: pointer;
          backdrop-filter: blur(12px);
          -webkit-backdrop-filter: blur(12px);
          transition: all 0.25s ease;
          display: inline-flex;
          align-items: center;
          justify-content: center;
        }

        .btn-promo-switch:hover {
          background: #ffffff;
          color: #09090b;
          border-color: #ffffff;
          transform: translateY(-2px);
          box-shadow: 0 6px 20px rgba(0, 0, 0, 0.35);
        }

        .left-panel .btn-promo-switch,
        .right-panel .btn-promo-switch {
          margin: 0 auto;
          background: rgba(9, 9, 11, 0.88);
          border: 1px solid rgba(255, 255, 255, 0.28);
          width: 156px;
          height: 46px;
          font-weight: 600;
          font-size: 0.88rem;
          letter-spacing: -0.01em;
          border-radius: 46px;
          color: #ffffff;
          cursor: pointer;
          backdrop-filter: blur(16px);
          -webkit-backdrop-filter: blur(16px);
          transition: all 0.25s ease;
          display: inline-flex;
          align-items: center;
          justify-content: center;
          box-shadow: 0 4px 18px rgba(0, 0, 0, 0.5), 0 0 0 1px rgba(255, 255, 255, 0.08);
        }

        .left-panel .btn-promo-switch:hover,
        .right-panel .btn-promo-switch:hover {
          background: #ffffff;
          color: #09090b;
          border-color: #ffffff;
          transform: translateY(-2px);
          box-shadow: 0 8px 25px rgba(0, 0, 0, 0.7);
        }

        /* Mode Switch Animations */
        .auth-card-container:before,
        .auth-card-container.sign-up-mode:before {
          display: none;
        }

        .auth-card-container.sign-up-mode .left-panel .content {
          transform: translateX(-120px);
          opacity: 0;
          transition: transform 0.45s cubic-bezier(0.76, 0, 0.24, 1), opacity 0.25s ease-in;
        }

        .auth-card-container.sign-up-mode .signin-signup {
          left: 25%;
        }

        .auth-card-container.sign-up-mode form.sign-up-form {
          opacity: 1;
          transform: translateX(0);
          z-index: 25;
          pointer-events: auto;
          transition: opacity 0.4s 0.12s ease-out, transform 0.5s 0.12s cubic-bezier(0.76, 0, 0.24, 1);
        }

        .auth-card-container.sign-up-mode form.sign-in-form {
          opacity: 0;
          transform: translateX(-25px);
          z-index: 10;
          pointer-events: none;
          transition: opacity 0.25s ease-in, transform 0.3s ease-in;
        }

        .auth-card-container.sign-up-mode .right-panel .content {
          transform: translateX(0);
          opacity: 1;
          pointer-events: auto;
          transition: transform 0.75s cubic-bezier(0.76, 0, 0.24, 1) 0.1s, opacity 0.45s ease-out 0.1s;
        }

        .auth-card-container.sign-up-mode .left-panel {
          pointer-events: none;
        }

        .auth-card-container.sign-up-mode .right-panel {
          pointer-events: none;
        }

        /* Responsive Mobile Layout */
        @media (max-width: 870px) {
          .auth-top-bar {
            position: relative;
            top: 0;
            left: 0;
            right: 0;
            width: 100%;
            padding: 0 4px;
            margin-bottom: 16px;
          }

          .auth-card-container {
            min-height: 720px;
            height: auto;
            max-width: 480px;
            margin-top: 0;
          }

          .signin-signup {
            width: 100%;
            top: 92%;
            transform: translate(-50%, -100%);
            transition: top 0.8s cubic-bezier(0.76, 0, 0.24, 1), transform 0.8s cubic-bezier(0.76, 0, 0.24, 1);
          }

          .signin-signup,
          .auth-card-container.sign-up-mode .signin-signup {
            left: 50%;
          }

          .panels-container {
            grid-template-columns: 1fr;
            grid-template-rows: 1fr 2fr 1fr;
          }

          .panel {
            flex-direction: column;
            justify-content: center;
            align-items: center;
            padding: 1.5rem 1.5rem;
            grid-column: 1 / 2;
          }

          .right-panel {
            grid-row: 3 / 4;
          }

          .auth-ghost-backdrop {
            width: 100%;
            height: 36%;
            top: 0;
            left: 0;
            clip-path: none;
            -webkit-clip-path: none;
            border-radius: 24px 24px 0 0;
            transition: transform 0.8s cubic-bezier(0.76, 0, 0.24, 1), opacity 0.5s ease-in-out;
          }

          .auth-card-container.sign-up-mode .auth-ghost-backdrop {
            transform: translateY(-100%);
            opacity: 0;
          }

          .auth-monster-backdrop {
            width: 100%;
            height: 36%;
            bottom: 0;
            left: 0;
            right: 0;
            top: initial;
            clip-path: none;
            -webkit-clip-path: none;
            border-radius: 0 0 24px 24px;
            transform: translateY(100%);
            opacity: 0;
            transition: transform 0.8s cubic-bezier(0.76, 0, 0.24, 1), opacity 0.5s ease-in-out;
          }

          .auth-card-container.sign-up-mode .auth-monster-backdrop {
            transform: translateY(0);
            opacity: 1;
          }

          .left-panel {
            grid-row: 1 / 2;
          }

          .panel .content {
            padding: 0 0.5rem;
            max-width: 100%;
          }

          .left-panel .content {
            transform: translateY(0);
            opacity: 1;
            transition: transform 0.75s cubic-bezier(0.76, 0, 0.24, 1) 0.1s, opacity 0.45s ease-out 0.1s;
          }

          .right-panel .content {
            transform: translateY(60px);
            opacity: 0;
            transition: transform 0.45s cubic-bezier(0.76, 0, 0.24, 1), opacity 0.25s ease-in;
          }

          .auth-card-container.sign-up-mode .left-panel .content {
            transform: translateY(-60px);
            opacity: 0;
            transition: transform 0.45s cubic-bezier(0.76, 0, 0.24, 1), opacity 0.25s ease-in;
          }

          .auth-card-container.sign-up-mode .right-panel .content {
            transform: translateY(0);
            opacity: 1;
            transition: transform 0.75s cubic-bezier(0.76, 0, 0.24, 1) 0.1s, opacity 0.45s ease-out 0.1s;
          }

          .panel h3 {
            font-size: 1.25rem;
            margin-bottom: 6px;
          }

          .panel p {
            font-size: 0.8rem;
            padding: 0.2rem 0 0.8rem;
          }

          .btn-promo-switch {
            width: 124px;
            height: 38px;
            font-size: 0.78rem;
          }

          .auth-card-container:before,
          .auth-card-container.sign-up-mode:before {
            display: none;
          }

          .auth-card-container.sign-up-mode .signin-signup {
            top: 10%;
            transform: translate(-50%, 0);
          }

          form {
            padding: 0 2rem;
          }
        }

        @media (max-width: 570px) {
          .auth-card-container {
            border-radius: 18px;
          }

          form {
            padding: 0 1.25rem;
          }

          .title {
            font-size: 1.65rem;
          }

          .subtitle {
            font-size: 0.82rem;
            margin-bottom: 16px;
          }

          .input-field {
            height: 46px;
          }

          .btn-primary-auth {
            height: 44px;
            font-size: 0.88rem;
          }
        }
      `}</style>

      {/* Top Header Bar matching Frontpage Navbar Layout */}
      <div className="auth-top-bar">
        {/* Very Left Side: Prompt Compiler Brand matching Frontpage with Floating Animation */}
        <div 
          data-magnetic 
          onClick={handleHomeNavigation}
          className="flex items-center gap-2.5 sm:gap-3 cursor-pointer group transition-colors duration-200"
          role="button"
          tabIndex={0}
          aria-label="Prompt Compiler Home"
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") {
              handleHomeNavigation();
            }
          }}
        >
          <Logo size="lg" />
          <div className="flex flex-col">
            <span className="text-base sm:text-lg font-bold tracking-tight text-foreground flex items-center gap-2">
              Prompt Compiler
              <span className="text-[10px] font-mono uppercase tracking-wider px-2 py-0.5 rounded-full bg-neutral-200/80 dark:bg-white/10 text-neutral-800 dark:text-neutral-200 border border-neutral-300 dark:border-white/15 hidden sm:inline-block">
                Local First
              </span>
            </span>
          </div>
        </div>

        {/* Right Side: Toggle button on left of right side, then Back to Home on very right (both with floating effect) */}
        <div className="flex items-center gap-2.5 sm:gap-3">
          {/* Theme Toggle Button (with floating effect) */}
          <ThemeToggle />

          {/* Back to Home Button (with floating effect) */}
          <MagneticButton
            as="button"
            type="button"
            onClick={handleHomeNavigation}
            aria-label="Back to Prompt Compiler Home"
            className="footer-glass-pill h-9 px-3.5 sm:px-4 rounded-full text-xs font-mono font-medium flex items-center gap-1.5 sm:gap-2 cursor-pointer transition-colors duration-200 shadow-sm"
          >
            <ArrowLeft className="h-3.5 w-3.5 pointer-events-none" />
            <span className="hidden sm:inline pointer-events-none">Back to Home</span>
            <span className="sm:hidden pointer-events-none">Home</span>
          </MagneticButton>
        </div>
      </div>

      {/* Hidden SVG Definitions for Organic Responsive Curve Clipping */}
      <svg width="0" height="0" className="absolute pointer-events-none" style={{ position: "absolute", width: 0, height: 0 }} aria-hidden="true">
        <defs>
          <clipPath id="auth-ghost-curve" clipPathUnits="objectBoundingBox">
            <path d="M 0 0 L 0.9965 0 C 0.98 0.35, 0.82 0.72, 0.5208 1 L 0 1 Z" />
          </clipPath>
          <clipPath id="auth-monster-curve" clipPathUnits="objectBoundingBox">
            <path d="M 1 0 L 1 1 L 0.4852 1 C 0.18 0.72, 0.03 0.35, 0.0149 0 Z" />
          </clipPath>
        </defs>
      </svg>

      {/* Main Themed Auth Card with Organic Curved Boundary */}
      <div className={isSignUp ? "auth-card-container sign-up-mode" : "auth-card-container"}>
        {/* Ghost Background Artwork for Sign-In Mode (Left Section) */}
        <div className={isSignUp ? "auth-ghost-backdrop sign-up-mode" : "auth-ghost-backdrop"} aria-hidden="true">
          <img 
            src={authBg} 
            alt="Prompt Compiler Ghost Artwork" 
            className="auth-ghost-img" 
          />
          <div className="auth-ghost-overlay" />
        </div>

        {/* Monster Hand Background Artwork for Sign-Up Mode (Right Section) */}
        <div className={isSignUp ? "auth-monster-backdrop sign-up-mode" : "auth-monster-backdrop"} aria-hidden="true">
          <img 
            src={authSignupBg} 
            alt="Prompt Compiler Monster Hand Artwork" 
            className="auth-monster-img" 
          />
          <div className="auth-monster-overlay" />
        </div>

        <div className="forms-container">
          <div className="signin-signup">
            
            {/* SIGN IN FORM (OR DEVICE VERIFICATION) */}
            {isVerifyingDevice ? (
              <form className="sign-in-form" onSubmit={handleVerifyDeviceSubmit} autoComplete="off">
                <h2 className="title">{deviceVerificationTitle}</h2>
                <p className="subtitle">
                  {deviceVerificationPrompt || (
                    <>
                      Enter the verification code sent to{" "}
                      <span className="font-semibold text-foreground">
                        {deviceVerificationTarget || signInEmail}
                      </span>{" "}
                      to authorize this device.
                    </>
                  )}
                </p>

                {authStatus && (
                  <div 
                    role="status"
                    className={`mb-3.5 px-4 py-1.5 rounded-full text-xs font-medium border text-center transition-all duration-200 ${
                      authStatus.type === "error"
                        ? "bg-red-500/15 border-red-500/35 text-red-600 dark:text-red-400"
                        : authStatus.type === "success" 
                        ? "bg-emerald-500/15 border-emerald-500/35 text-emerald-600 dark:text-emerald-400"
                        : "bg-neutral-200/90 dark:bg-white/10 border-neutral-300 dark:border-white/20 text-neutral-800 dark:text-neutral-200"
                    }`}
                  >
                    {authStatus.text}
                  </div>
                )}

                <div className="input-group">
                  <label htmlFor="device-verify-code" className="sr-only">Verification Code</label>
                  <div 
                    className="input-field"
                    onClick={() => document.getElementById("device-verify-code")?.focus()}
                  >
                    <div className="icon-wrap" aria-hidden="true">
                      <KeyRound className="h-4.5 w-4.5 pointer-events-none" />
                    </div>
                    <input
                      id="device-verify-code"
                      name="device_verify_token"
                      type="text"
                      placeholder="Enter verification code"
                      autoComplete="one-time-code"
                      required
                      value={deviceVerificationCode}
                      onChange={(e) => setDeviceVerificationCode(e.target.value)}
                    />
                  </div>
                </div>

                <button 
                  type="submit" 
                  disabled={isSubmitting || !isSignInLoaded}
                  className="btn-primary-auth cursor-pointer active:scale-[0.98] transition-transform disabled:opacity-60 disabled:cursor-not-allowed"
                >
                  {isSubmitting ? "Verifying..." : "Verify & Continue"}
                </button>

                <div className="forgot-password-row flex justify-between items-center w-full mt-3">
                  {canResendDeviceCode ? (
                    <button
                      type="button"
                      className="forgot-password-btn text-xs text-muted-foreground hover:text-foreground cursor-pointer"
                      onClick={handleResendDeviceCode}
                      disabled={isSubmitting}
                    >
                      Resend code
                    </button>
                  ) : (
                    <span />
                  )}
                  <button
                    type="button"
                    className="forgot-password-btn text-xs text-muted-foreground hover:text-foreground cursor-pointer"
                    onClick={handleCancelDeviceVerification}
                    disabled={isSubmitting}
                  >
                    Start over
                  </button>
                </div>
              </form>
            ) : (
              <form className="sign-in-form" onSubmit={handleSignInSubmit} autoComplete="off">
                <h2 className="title">Welcome back</h2>
                <p className="subtitle">Continue turning your ideas into implementation-ready prompts.</p>
                
                {authStatus && (
                  <div 
                    role="status"
                    className={`mb-3.5 px-4 py-1.5 rounded-full text-xs font-medium border text-center transition-all duration-200 ${
                      authStatus.type === "error"
                        ? "bg-red-500/15 border-red-500/35 text-red-600 dark:text-red-400"
                        : authStatus.type === "success" 
                        ? "bg-emerald-500/15 border-emerald-500/35 text-emerald-600 dark:text-emerald-400"
                        : "bg-neutral-200/90 dark:bg-white/10 border-neutral-300 dark:border-white/20 text-neutral-800 dark:text-neutral-200"
                    }`}
                  >
                    {authStatus.text}
                  </div>
                )}

                <div className="input-group">
                  <label htmlFor="signin-email" className="sr-only">Email address</label>
                  <div 
                    className="input-field"
                    onClick={() => document.getElementById("signin-email")?.focus()}
                  >
                    <div className="icon-wrap" aria-hidden="true">
                      <Mail className="h-4.5 w-4.5 pointer-events-none" />
                    </div>
                    <input
                      id="signin-email"
                      name="login_account_id"
                      type="email"
                      placeholder="Email"
                      autoComplete="off"
                      data-lpignore="true"
                      data-1p-ignore="true"
                      data-form-type="other"
                      required
                      value={signInEmail}
                      onChange={(e) => setSignInEmail(e.target.value)}
                    />
                  </div>
                </div>

                <div className="input-group">
                  <label htmlFor="signin-password" className="sr-only">Password</label>
                  <div 
                    className="input-field"
                    onClick={() => document.getElementById("signin-password")?.focus()}
                  >
                    <div className="icon-wrap" aria-hidden="true">
                      <Lock className="h-4.5 w-4.5 pointer-events-none" />
                    </div>
                    <input
                      id="signin-password"
                      name="login_account_key"
                      type="password"
                      placeholder="Password"
                      autoComplete="new-password"
                      data-lpignore="true"
                      data-1p-ignore="true"
                      data-form-type="other"
                      required
                      value={signInPassword}
                      onChange={(e) => setSignInPassword(e.target.value)}
                    />
                  </div>
                </div>

                <div className="forgot-password-row">
                  <button
                    type="button"
                    className="forgot-password-btn"
                    onClick={handleForgotPassword}
                    aria-label="Forgot password recovery"
                  >
                    Forgot password?
                  </button>
                </div>

                <button 
                  type="submit" 
                  disabled={isSubmitting || !isSignInLoaded}
                  className="btn-primary-auth cursor-pointer active:scale-[0.98] transition-transform disabled:opacity-60 disabled:cursor-not-allowed"
                >
                  {isSubmitting ? "Signing In..." : "Sign In"}
                </button>

                <div className="social-divider">
                  <p className="social-text">Or continue with</p>
                </div>

                <div className="social-media">
                  <button
                    type="button"
                    onClick={handleGoogleAuth}
                    disabled={isSubmitting}
                    className="social-icon-btn cursor-pointer transition-transform hover:scale-105 active:scale-95 disabled:opacity-60 disabled:cursor-not-allowed"
                    aria-label="Continue with Google"
                  >
                    <GoogleIcon className="h-5 w-5 pointer-events-none" />
                  </button>
                </div>
              </form>
            )}

            {/* SIGN UP FORM (OR EMAIL VERIFICATION) */}
            {isVerifying ? (
              <form className="sign-up-form" onSubmit={handleVerifyEmailSubmit} autoComplete="off">
                <h2 className="title">Verify your email</h2>
                <p className="subtitle">Enter the 6-digit code sent to <span className="font-semibold text-foreground">{signUpEmail}</span></p>
                
                {authStatus && (
                  <div 
                    role="status"
                    className={`mb-3.5 px-4 py-1.5 rounded-full text-xs font-medium border text-center transition-all duration-200 ${
                      authStatus.type === "error"
                        ? "bg-red-500/15 border-red-500/35 text-red-600 dark:text-red-400"
                        : authStatus.type === "success" 
                        ? "bg-emerald-500/15 border-emerald-500/35 text-emerald-600 dark:text-emerald-400"
                        : "bg-neutral-200/90 dark:bg-white/10 border-neutral-300 dark:border-white/20 text-neutral-800 dark:text-neutral-200"
                    }`}
                  >
                    {authStatus.text}
                  </div>
                )}

                <div className="input-group">
                  <label htmlFor="verify-code" className="sr-only">Verification Code</label>
                  <div 
                    className="input-field"
                    onClick={() => document.getElementById("verify-code")?.focus()}
                  >
                    <div className="icon-wrap" aria-hidden="true">
                      <KeyRound className="h-4.5 w-4.5 pointer-events-none" />
                    </div>
                    <input
                      id="verify-code"
                      name="email_verify_token"
                      type="text"
                      placeholder="Enter 6-digit code"
                      autoComplete="one-time-code"
                      required
                      value={verificationCode}
                      onChange={(e) => setVerificationCode(e.target.value)}
                    />
                  </div>
                </div>

                <button 
                  type="submit" 
                  disabled={isSubmitting || !isSignUpLoaded}
                  className="btn-primary-auth cursor-pointer active:scale-[0.98] transition-transform disabled:opacity-60 disabled:cursor-not-allowed"
                >
                  {isSubmitting ? "Verifying..." : "Verify & Continue"}
                </button>

                <div className="forgot-password-row flex justify-between items-center w-full mt-3">
                  <button
                    type="button"
                    className="forgot-password-btn text-xs text-muted-foreground hover:text-foreground cursor-pointer"
                    onClick={handleResendCode}
                    disabled={isSubmitting}
                  >
                    Resend code
                  </button>
                  <button
                    type="button"
                    className="forgot-password-btn text-xs text-muted-foreground hover:text-foreground cursor-pointer"
                    onClick={() => {
                      setIsVerifying(false);
                      setAuthStatus(null);
                    }}
                  >
                    Edit details
                  </button>
                </div>
              </form>
            ) : (
              <form className="sign-up-form" onSubmit={handleSignUpSubmit} autoComplete="off">
                <h2 className="title">Create your account</h2>
                <p className="subtitle">Start compiling ideas into implementation-ready prompts.</p>
                
                {authStatus && (
                  <div 
                    role="status"
                    className={`mb-3.5 px-4 py-1.5 rounded-full text-xs font-medium border text-center transition-all duration-200 ${
                      authStatus.type === "error"
                        ? "bg-red-500/15 border-red-500/35 text-red-600 dark:text-red-400"
                        : authStatus.type === "success" 
                        ? "bg-emerald-500/15 border-emerald-500/35 text-emerald-600 dark:text-emerald-400"
                        : "bg-neutral-200/90 dark:bg-white/10 border-neutral-300 dark:border-white/20 text-neutral-800 dark:text-neutral-200"
                    }`}
                  >
                    {authStatus.text}
                  </div>
                )}

                <div className="input-group">
                  <label htmlFor="signup-name" className="sr-only">Full name</label>
                  <div 
                    className="input-field"
                    onClick={() => document.getElementById("signup-name")?.focus()}
                  >
                    <div className="icon-wrap" aria-hidden="true">
                      <User className="h-4.5 w-4.5 pointer-events-none" />
                    </div>
                    <input
                      id="signup-name"
                      name="register_account_name"
                      type="text"
                      placeholder="Name"
                      autoComplete="off"
                      data-lpignore="true"
                      data-1p-ignore="true"
                      data-form-type="other"
                      required
                      value={signUpName}
                      onChange={(e) => setSignUpName(e.target.value)}
                    />
                  </div>
                </div>

                <div className="input-group">
                  <label htmlFor="signup-email" className="sr-only">Email address</label>
                  <div 
                    className="input-field"
                    onClick={() => document.getElementById("signup-email")?.focus()}
                  >
                    <div className="icon-wrap" aria-hidden="true">
                      <Mail className="h-4.5 w-4.5 pointer-events-none" />
                    </div>
                    <input
                      id="signup-email"
                      name="register_account_id"
                      type="email"
                      placeholder="Email"
                      autoComplete="off"
                      data-lpignore="true"
                      data-1p-ignore="true"
                      data-form-type="other"
                      required
                      value={signUpEmail}
                      onChange={(e) => setSignUpEmail(e.target.value)}
                    />
                  </div>
                </div>

                <div className="input-group">
                  <label htmlFor="signup-password" className="sr-only">Password</label>
                  <div 
                    className="input-field"
                    onClick={() => document.getElementById("signup-password")?.focus()}
                  >
                    <div className="icon-wrap" aria-hidden="true">
                      <Lock className="h-4.5 w-4.5 pointer-events-none" />
                    </div>
                    <input
                      id="signup-password"
                      name="register_account_key"
                      type="password"
                      placeholder="Password"
                      autoComplete="new-password"
                      data-lpignore="true"
                      data-1p-ignore="true"
                      data-form-type="other"
                      required
                      value={signUpPassword}
                      onChange={(e) => setSignUpPassword(e.target.value)}
                    />
                  </div>
                </div>

                <button 
                  type="submit" 
                  disabled={isSubmitting || !isSignUpLoaded}
                  className="btn-primary-auth cursor-pointer active:scale-[0.98] transition-transform disabled:opacity-60 disabled:cursor-not-allowed"
                >
                  {isSubmitting ? "Creating Account..." : "Create Account"}
                </button>

                <div className="social-divider">
                  <p className="social-text">Or continue with</p>
                </div>

                <div className="social-media">
                  <button
                    type="button"
                    onClick={handleGoogleAuth}
                    disabled={isSubmitting}
                    className="social-icon-btn cursor-pointer transition-transform hover:scale-105 active:scale-95 disabled:opacity-60 disabled:cursor-not-allowed"
                    aria-label="Continue with Google"
                  >
                    <GoogleIcon className="h-5 w-5 pointer-events-none" />
                  </button>
                </div>
              </form>
            )}

          </div>
        </div>

        {/* Promotional Side Panels */}
        <div className="panels-container">
          {/* Left Panel - Visible during Sign-In Mode */}
          <div className="panel left-panel">
            <div className="content">
              <h3>New to Prompt Compiler?</h3>
              <button
                type="button"
                className="btn-promo-switch"
                onClick={() => {
                  setIsSignUp(true);
                  setIsVerifying(false);
                  setIsVerifyingDevice(false);
                  setDeviceVerificationCode("");
                  setAuthStatus(null);
                }}
              >
                Create account
              </button>
            </div>
          </div>

          {/* Right Panel - Visible during Sign-Up Mode */}
          <div className="panel right-panel">
            <div className="content">
              <h3>Already using Prompt Compiler?</h3>
              <button
                type="button"
                className="btn-promo-switch"
                onClick={() => {
                  setIsSignUp(false);
                  setIsVerifying(false);
                  setIsVerifyingDevice(false);
                  setDeviceVerificationCode("");
                  setAuthStatus(null);
                }}
              >
                Sign In
              </button>
            </div>
          </div>
        </div>

      </div>
    </div>
    </MagneticCursor>
  );
}
