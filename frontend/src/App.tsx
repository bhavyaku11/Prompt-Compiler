import { useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthenticateWithRedirectCallback, useAuth } from '@clerk/react';
import { ThemeProvider } from '@/context/ThemeContext';
import { LandingView } from '@/views/LandingView';
import { AuthView } from '@/views/AuthView';
import { StudioView } from '@/views/StudioView';
import { setAuthTokenGetter } from '@/api/client';

function AuthTokenSync() {
  const { getToken, isSignedIn } = useAuth();

  useEffect(() => {
    if (isSignedIn) {
      setAuthTokenGetter(() => getToken());
    } else {
      setAuthTokenGetter(null);
    }
  }, [getToken, isSignedIn]);

  return null;
}

export function App() {
  return (
    <ThemeProvider>
      <AuthTokenSync />
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<LandingView />} />
          <Route path="/auth" element={<AuthView />} />
          <Route path="/studio" element={<StudioView />} />
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
      </BrowserRouter>
    </ThemeProvider>
  );
}

export default App;

