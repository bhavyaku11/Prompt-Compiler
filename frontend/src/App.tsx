import { Component, useEffect, type ReactNode } from 'react';
import { BrowserRouter, Routes, Route, Navigate, useNavigate } from 'react-router-dom';
import { AuthenticateWithRedirectCallback, ClerkProvider, useAuth } from '@clerk/react';
import { AlertTriangle, RotateCcw } from 'lucide-react';
import { ThemeProvider } from '@/context/ThemeContext';
import { LandingView } from '@/views/LandingView';
import { AuthView } from '@/views/AuthView';
import { StudioView } from '@/views/StudioView';
import { DocsView } from '@/views/DocsView';
import { setAuthTokenGetter } from '@/api/client';

const PUBLISHABLE_KEY = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY;

interface ErrorBoundaryProps {
  children: ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: unknown) {
    console.error('[ErrorBoundary] Unhandled React error caught:', error, errorInfo);
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null });
    window.location.href = '/studio';
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen flex items-center justify-center bg-[#08080c] text-[#f8fafc] px-4">
          <div className="max-w-md w-full p-8 rounded-3xl border border-white/10 bg-[#13131b] shadow-2xl flex flex-col items-center text-center gap-4">
            <div className="h-12 w-12 rounded-2xl bg-amber-500/10 border border-amber-500/20 text-amber-500 flex items-center justify-center">
              <AlertTriangle className="h-6 w-6" />
            </div>
            <div className="space-y-1.5">
              <h2 className="text-lg font-bold tracking-tight text-white">Something went wrong</h2>
              <p className="text-xs text-neutral-400 leading-relaxed font-mono">
                {this.state.error?.message || 'An unexpected rendering error occurred.'}
              </p>
            </div>
            <button
              type="button"
              onClick={this.handleReset}
              className="mt-2 flex items-center gap-2 px-5 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-semibold text-xs transition-colors cursor-pointer"
            >
              <RotateCcw className="h-4 w-4" />
              <span>Reload Workspace</span>
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

function ClerkProviderWithRouter({ children }: { children: ReactNode }) {
  const navigate = useNavigate();

  if (!PUBLISHABLE_KEY) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#08080c] text-[#f8fafc] px-4">
        <div className="max-w-md w-full p-8 rounded-3xl border border-white/10 bg-[#13131b] shadow-2xl flex flex-col items-center text-center gap-4">
          <div className="h-12 w-12 rounded-2xl bg-amber-500/10 border border-amber-500/20 text-amber-500 flex items-center justify-center">
            <AlertTriangle className="h-6 w-6" />
          </div>
          <div className="space-y-1.5">
            <h2 className="text-lg font-bold tracking-tight text-white">Missing Configuration</h2>
            <p className="text-xs text-neutral-400 leading-relaxed font-mono">
              Missing VITE_CLERK_PUBLISHABLE_KEY in environment variables.
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <ClerkProvider
      publishableKey={PUBLISHABLE_KEY}
      routerPush={(to) => navigate(to)}
      routerReplace={(to) => navigate(to, { replace: true })}
      signInUrl="/auth"
      signUpUrl="/auth"
      signInFallbackRedirectUrl="/studio"
      signUpFallbackRedirectUrl="/studio"
      afterSignOutUrl="/auth"
    >
      {children}
    </ClerkProvider>
  );
}

function AuthTokenSync() {
  const { getToken, isSignedIn } = useAuth();

  useEffect(() => {
    if (isSignedIn) {
      setAuthTokenGetter(() => getToken());
    } else {
      const desktopToken = typeof window !== 'undefined' ? sessionStorage.getItem('desktop_auth_token') : null;
      if (desktopToken) {
        setAuthTokenGetter(async () => desktopToken);
      } else {
        setAuthTokenGetter(null);
      }
    }
  }, [getToken, isSignedIn]);

  useEffect(() => {
    const handleSignedOut = () => {
      setAuthTokenGetter(null);
    };
    window.addEventListener('prompt-compiler:signed-out', handleSignedOut);
    return () => {
      window.removeEventListener('prompt-compiler:signed-out', handleSignedOut);
    };
  }, []);

  return null;
}

export function App() {
  return (
    <ErrorBoundary>
      <ThemeProvider>
        <BrowserRouter>
          <ClerkProviderWithRouter>
            <AuthTokenSync />
            <Routes>
              <Route path="/" element={<LandingView />} />
              <Route path="/auth" element={<AuthView />} />
              <Route path="/sign-in" element={<Navigate to="/auth" replace />} />
              <Route path="/sign-up" element={<Navigate to="/auth" replace />} />
              <Route path="/studio" element={<StudioView />} />
              <Route path="/docs" element={<DocsView />} />
              <Route path="/docs/:section" element={<DocsView />} />
              <Route
                path="/sso-callback"
                element={
                  <AuthenticateWithRedirectCallback
                    signUpForceRedirectUrl="/studio"
                    signInForceRedirectUrl="/studio"
                  />
                }
              />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </ClerkProviderWithRouter>
        </BrowserRouter>
      </ThemeProvider>
    </ErrorBoundary>
  );
}

export default App;



