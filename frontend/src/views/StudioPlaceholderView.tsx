import { useNavigate } from 'react-router-dom';
import { useAuth, useUser, useClerk } from '@clerk/react';
import { LogOut, ArrowLeft, CheckCircle2, ShieldCheck, User } from 'lucide-react';
import { MagneticButton } from '@/components/ui/magnetic-button';
import { ThemeToggle } from '@/components/ui/theme-toggle';
import { Logo } from '@/components/ui/Logo';

export function StudioPlaceholderView() {
  const navigate = useNavigate();
  const { isLoaded, isSignedIn } = useAuth();
  const { user } = useUser();
  const { signOut } = useClerk();

  if (!isLoaded) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background text-foreground">
        <div className="flex flex-col items-center gap-3">
          <div className="h-6 w-6 rounded-full border-2 border-primary border-t-transparent animate-spin" />
          <p className="text-xs font-mono text-muted-foreground">Checking authentication...</p>
        </div>
      </div>
    );
  }

  if (!isSignedIn) {
    navigate('/auth', { replace: true });
    return null;
  }

  const handleSignOut = async () => {
    await signOut();
    navigate('/auth', { replace: true });
  };

  const userDisplayName = user?.fullName || user?.firstName || user?.username || 'Architect';
  const userEmail = user?.primaryEmailAddress?.emailAddress || 'No primary email';

  return (
    <div className="min-h-screen w-full bg-background text-foreground flex flex-col justify-between p-4 sm:p-8 relative overflow-x-hidden selection:bg-neutral-800 selection:text-white dark:selection:bg-white dark:selection:text-black">
      {/* Background Grid Pattern */}
      <div 
        className="absolute inset-0 z-0 bg-grid-pattern opacity-40 pointer-events-none" 
        aria-hidden="true" 
      />

      {/* Top Header */}
      <header className="relative z-10 flex items-center justify-between max-w-5xl mx-auto w-full pb-6 border-b border-border/40">
        <div 
          onClick={() => navigate('/')} 
          className="flex items-center gap-2.5 cursor-pointer group transition-opacity hover:opacity-90"
        >
          <Logo size="md" />
          <span className="text-base font-bold tracking-tight text-foreground">
            Prompt Compiler
          </span>
        </div>

        <div className="flex items-center gap-2 sm:gap-3">
          <ThemeToggle />
          <MagneticButton
            as="button"
            type="button"
            onClick={() => navigate('/')}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium border border-border bg-card/60 backdrop-blur-sm text-foreground hover:bg-muted transition-colors"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            <span className="hidden sm:inline">Home</span>
          </MagneticButton>
          <MagneticButton
            as="button"
            type="button"
            onClick={handleSignOut}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold bg-neutral-900 text-white dark:bg-white dark:text-neutral-950 hover:opacity-90 transition-opacity"
          >
            <LogOut className="h-3.5 w-3.5" />
            <span>Sign Out</span>
          </MagneticButton>
        </div>
      </header>

      {/* Main Studio Placeholder Body */}
      <main className="relative z-10 flex flex-1 flex-col items-center justify-center max-w-3xl mx-auto w-full py-12 text-center">
        {/* Temporary Notice Eyebrow */}
        <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full border border-amber-500/30 bg-amber-500/10 text-amber-600 dark:text-amber-400 mb-6 text-xs font-mono font-medium tracking-wide">
          <span className="flex h-2 w-2 rounded-full bg-amber-500 animate-pulse" />
          <span>TEMPORARY PLACEHOLDER • WORKSPACE COMING NEXT</span>
        </div>

        <h1 className="text-3xl sm:text-5xl font-extrabold tracking-tight mb-4 text-foreground">
          Prompt Compiler Studio
        </h1>

        <p className="text-base sm:text-lg text-muted-foreground max-w-xl mx-auto leading-relaxed mb-8">
          Authentication successful. Workspace coming next.
        </p>

        {/* User Session Profile Card */}
        <div className="w-full max-w-md p-6 rounded-2xl border border-border/80 bg-card/70 backdrop-blur-xl shadow-xl text-left flex flex-col gap-4">
          <div className="flex items-center gap-3.5 pb-4 border-b border-border/50">
            {user?.imageUrl ? (
              <img 
                src={user.imageUrl} 
                alt={userDisplayName} 
                className="h-12 w-12 rounded-full object-cover border border-border"
              />
            ) : (
              <div className="h-12 w-12 rounded-full bg-primary/10 text-primary flex items-center justify-center font-bold text-lg">
                <User className="h-6 w-6" />
              </div>
            )}
            <div className="flex flex-col min-w-0">
              <span className="text-sm font-semibold text-foreground truncate">
                {userDisplayName}
              </span>
              <span className="text-xs text-muted-foreground font-mono truncate">
                {userEmail}
              </span>
            </div>
            <div className="ml-auto flex items-center gap-1 text-[11px] font-mono text-emerald-600 dark:text-emerald-400 bg-emerald-500/10 px-2.5 py-1 rounded-full border border-emerald-500/20">
              <ShieldCheck className="h-3 w-3" />
              <span>Verified</span>
            </div>
          </div>

          <div className="flex flex-col gap-2 text-xs font-mono text-muted-foreground">
            <div className="flex justify-between items-center py-1">
              <span>Clerk Auth Session:</span>
              <span className="text-emerald-500 font-semibold flex items-center gap-1">
                <CheckCircle2 className="h-3 w-3" /> Active
              </span>
            </div>
            <div className="flex justify-between items-center py-1">
              <span>Next Milestone:</span>
              <span className="text-foreground">Task 26 — Interactive Studio</span>
            </div>
          </div>

          <div className="pt-2 flex flex-col gap-2">
            <MagneticButton
              as="button"
              type="button"
              onClick={handleSignOut}
              className="w-full py-2.5 rounded-xl border border-border hover:bg-muted text-foreground text-xs font-semibold flex items-center justify-center gap-2 transition-colors cursor-pointer"
            >
              <LogOut className="h-3.5 w-3.5" />
              <span>Sign Out of Clerk Session</span>
            </MagneticButton>
          </div>
        </div>
      </main>

      {/* Footer Info */}
      <footer className="relative z-10 max-w-5xl mx-auto w-full pt-6 border-t border-border/40 text-center text-xs text-muted-foreground font-mono">
        Prompt Compiler Local Studio • Frontend Clerk Authentication Ready
      </footer>
    </div>
  );
}

export default StudioPlaceholderView;
