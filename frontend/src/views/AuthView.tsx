import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth, GoogleOneTap } from '@clerk/react';
import { WifiOff, AlertTriangle, RotateCcw, ArrowLeft } from 'lucide-react';
import AuthSwitch from '@/components/ui/auth-switch';
import { isTauri } from '@/api/tauri-bridge';

export function AuthView() {
  const navigate = useNavigate();
  const { isLoaded, isSignedIn } = useAuth();
  const [loadTimedOut, setLoadTimedOut] = useState(false);
  const [isOnline, setIsOnline] = useState<boolean>(
    typeof navigator !== 'undefined' ? navigator.onLine : true
  );

  // Monitor network connectivity
  useEffect(() => {
    const handleOnline = () => setIsOnline(true);
    const handleOffline = () => setIsOnline(false);

    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);
    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, []);

  // Set bounded timeout for session initialization
  useEffect(() => {
    if (isLoaded) return;
    const timer = setTimeout(() => {
      setLoadTimedOut(true);
    }, 6000);
    return () => clearTimeout(timer);
  }, [isLoaded]);

  useEffect(() => {
    const desktopToken = typeof window !== 'undefined' ? sessionStorage.getItem('desktop_auth_token') : null;
    const justSignedOut = typeof window !== 'undefined' ? sessionStorage.getItem('pc_signed_out') : null;
    if (justSignedOut) {
      if (!isSignedIn) {
        sessionStorage.removeItem('pc_signed_out');
      }
      return;
    }
    if ((isLoaded && isSignedIn) || desktopToken) {
      navigate('/studio', { replace: true });
    }
  }, [isLoaded, isSignedIn, navigate]);

  const desktopToken = typeof window !== 'undefined' ? sessionStorage.getItem('desktop_auth_token') : null;
  const justSignedOut = typeof window !== 'undefined' ? sessionStorage.getItem('pc_signed_out') : null;
  const isAuthed = !justSignedOut && ((isLoaded && isSignedIn) || Boolean(desktopToken));

  // If loading took too long or offline while trying to initialize Clerk
  if (!isLoaded && !desktopToken && (loadTimedOut || !isOnline)) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background text-foreground px-4">
        <div className="max-w-md w-full p-6 sm:p-8 rounded-3xl border border-border/80 bg-card/80 backdrop-blur-xl shadow-2xl flex flex-col items-center text-center gap-4 animate-in fade-in duration-300">
          <div className="h-12 w-12 rounded-2xl bg-amber-500/10 border border-amber-500/20 text-amber-500 flex items-center justify-center">
            {!isOnline ? <WifiOff className="h-6 w-6" /> : <AlertTriangle className="h-6 w-6" />}
          </div>

          <div className="space-y-1.5">
            <h2 className="text-lg font-bold tracking-tight text-foreground">
              {!isOnline ? 'Network Connection Unavailable' : 'Authentication Service Unavailable'}
            </h2>
            <p className="text-xs text-muted-foreground leading-relaxed">
              {!isOnline
                ? 'Unable to reach Clerk authentication services. An active internet connection is required to sign in, verify your identity, or establish a desktop session.'
                : 'Connecting to Clerk authentication service timed out. Please check your network connection and firewall settings, then try again.'}
            </p>
          </div>

          <div className="flex items-center gap-3 pt-2 w-full">
            <button
              type="button"
              onClick={() => window.location.reload()}
              className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-primary text-primary-foreground font-semibold text-xs hover:opacity-90 transition-all cursor-pointer shadow-xs"
            >
              <RotateCcw className="h-4 w-4" />
              <span>Retry Connection</span>
            </button>
            <button
              type="button"
              onClick={() => navigate('/')}
              className="flex items-center justify-center gap-1.5 px-4 py-2.5 rounded-xl border border-border text-foreground font-semibold text-xs hover:bg-muted transition-colors cursor-pointer"
            >
              <ArrowLeft className="h-4 w-4" />
              <span>Home</span>
            </button>
          </div>
        </div>
      </div>
    );
  }

  if (!isLoaded && !desktopToken) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background text-foreground">
        <div className="flex flex-col items-center gap-3">
          <div className="h-6 w-6 rounded-full border-2 border-primary border-t-transparent animate-spin" />
          <p className="text-xs font-mono text-muted-foreground">Checking session...</p>
        </div>
      </div>
    );
  }

  if (isAuthed) {
    return null;
  }

  return (
    <>
      {!isTauri() && (
        <GoogleOneTap
          signInForceRedirectUrl="/studio"
          signUpForceRedirectUrl="/studio"
        />
      )}
      <AuthSwitch onBackToHome={() => navigate('/')} />
    </>
  );
}

export default AuthView;

