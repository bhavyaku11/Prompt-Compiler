import React, { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useClerk, useUser } from '@clerk/react';
import {
  LogOut,
  CheckCircle2,
  AlertCircle,
  Menu,
  WifiOff,
  Loader2,
} from 'lucide-react';
import { ThemeToggle } from '@/components/ui/theme-toggle';
import { signOutApp } from '@/api/auth';
import { UserAvatar } from '@/components/ui/UserAvatar';

interface TopBarProps {
  isBackendHealthy: boolean;
  onToggleSidebar: () => void;
  isOnline?: boolean;
}

export const TopBar: React.FC<TopBarProps> = ({
  isBackendHealthy,
  onToggleSidebar,
  isOnline = true,
}) => {
  const navigate = useNavigate();
  const { user } = useUser();
  const { signOut } = useClerk();
  const [isSigningOut, setIsSigningOut] = useState(false);

  const desktopUserRaw =
    typeof window !== 'undefined'
      ? sessionStorage.getItem('desktop_auth_user') || localStorage.getItem('desktop_auth_user')
      : null;
  let desktopUser: { firstName?: string; lastName?: string; email?: string; imageUrl?: string } | null = null;
  try {
    if (desktopUserRaw) desktopUser = JSON.parse(desktopUserRaw);
  } catch {}

  const activeEmail = user?.primaryEmailAddress?.emailAddress || desktopUser?.email || '';
  const avatarUrl =
    user?.imageUrl ||
    desktopUser?.imageUrl ||
    (activeEmail ? `https://unavatar.io/${encodeURIComponent(activeEmail)}` : null);

  const activeUser = user
    ? {
        firstName: user.firstName || user.username,
        fullName:
          user.fullName ||
          `${user.firstName || ''} ${user.lastName || ''}`.trim() ||
          user.username ||
          activeEmail.split('@')[0],
        primaryEmailAddress: { emailAddress: activeEmail },
        imageUrl: avatarUrl,
      }
    : desktopUser
    ? {
        firstName: desktopUser.firstName,
        fullName:
          `${desktopUser.firstName || ''} ${desktopUser.lastName || ''}`.trim() ||
          activeEmail.split('@')[0] ||
          'Developer',
        primaryEmailAddress: { emailAddress: activeEmail },
        imageUrl: avatarUrl,
      }
    : null;

  const [isUserMenuOpen, setIsUserMenuOpen] = useState(false);
  const userMenuRef = useRef<HTMLDivElement>(null);

  // Close menus on click outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (userMenuRef.current && !userMenuRef.current.contains(e.target as Node)) {
        setIsUserMenuOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleSignOut = async () => {
    setIsSigningOut(true);
    try {
      await signOutApp(signOut, () => {
        navigate('/auth', { replace: true });
      });
    } catch {
      navigate('/auth', { replace: true });
    } finally {
      setIsSigningOut(false);
    }
  };

  return (
    <header className="h-14 border-b border-topbar-border bg-topbar/95 backdrop-blur-xl px-4 sm:px-6 flex items-center justify-between z-30 shrink-0 shadow-2xs">
      {/* Left: Mobile Menu Toggle */}
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={onToggleSidebar}
          className="p-1.5 rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted md:hidden transition-colors cursor-pointer"
          aria-label="Toggle Sidebar"
        >
          <Menu className="h-5 w-5" />
        </button>
      </div>

      {/* Right: Engine Status + Account Status + Theme + Clerk Avatar */}
      <div className="flex items-center gap-2 sm:gap-3">
        {/* Backend / Local Engine Health Pill */}
        <div
          className={`hidden md:flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-mono border shadow-2xs ${
            isBackendHealthy
              ? 'border-border/80 bg-card text-foreground'
              : 'border-red-500/30 bg-red-500/10 text-red-500'
          }`}
          title={
            isBackendHealthy
              ? 'Local Engine Ready • FastAPI sidecar and SQLite active on 127.0.0.1'
              : 'Local Engine unavailable. Sidecar process is stopped or unreachable.'
          }
        >
          {isBackendHealthy ? (
            <>
              <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
              <span className="text-muted-foreground font-medium">Local Engine</span>
              <span className="text-[10px] text-emerald-500 font-semibold uppercase tracking-wider">Ready</span>
            </>
          ) : (
            <>
              <AlertCircle className="h-3 w-3 text-red-500" />
              <span className="font-semibold">Engine Stopped</span>
            </>
          )}
        </div>

        {/* Account / Network Connectivity Pill */}
        <div
          className={`hidden sm:flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-mono border shadow-2xs ${
            !isOnline
              ? 'border-amber-500/30 bg-amber-500/10 text-amber-500'
              : 'border-border/80 bg-card text-foreground'
          }`}
          title={
            !isOnline
              ? 'Internet disconnected • Running in local session mode'
              : activeUser
              ? 'Account Connected • Active authenticated session'
              : 'Authentication required'
          }
        >
          {!isOnline ? (
            <>
              <WifiOff className="h-3 w-3 text-amber-500" />
              <span className="font-medium text-muted-foreground">Account</span>
              <span className="text-[10px] text-amber-500 font-semibold uppercase tracking-wider">Offline</span>
            </>
          ) : activeUser ? (
            <>
              <span className="h-2 w-2 rounded-full bg-emerald-500" />
              <span className="text-muted-foreground font-medium">Account</span>
              <span className="text-[10px] text-emerald-500 font-medium">Connected</span>
            </>
          ) : (
            <>
              <AlertCircle className="h-3 w-3 text-amber-500" />
              <span className="text-amber-500 font-medium">Sign In Required</span>
            </>
          )}
        </div>

        {/* Theme Toggle */}
        <ThemeToggle />

        {/* User Avatar & Dropdown */}
        {activeUser && (
          <div className="relative" ref={userMenuRef}>
            <button
              type="button"
              onClick={() => setIsUserMenuOpen((prev) => !prev)}
              className="relative flex items-center justify-center rounded-full transition-transform hover:scale-105 cursor-pointer focus:outline-none"
              aria-label="User account menu"
            >
              <UserAvatar
                imageUrl={activeUser.imageUrl}
                name={activeUser.fullName || activeUser.firstName}
                email={activeUser.primaryEmailAddress?.emailAddress}
                size="md"
              />
            </button>

            {isUserMenuOpen && (
              <div className="absolute right-0 mt-2 w-56 rounded-2xl border border-border bg-card/95 backdrop-blur-xl p-3 shadow-2xl z-50 animate-in fade-in zoom-in-95 duration-100 flex flex-col gap-2">
                <div className="flex items-center gap-2.5 pb-2.5 border-b border-border/50">
                  <UserAvatar
                    imageUrl={activeUser.imageUrl}
                    name={activeUser.fullName || activeUser.firstName}
                    email={activeUser.primaryEmailAddress?.emailAddress}
                    size="md"
                  />
                  <div className="flex flex-col min-w-0">
                    <span className="text-xs font-semibold text-foreground truncate">
                      {activeUser.fullName || activeUser.firstName || 'Developer'}
                    </span>
                    <span className="text-[10px] font-mono text-muted-foreground truncate">
                      {activeUser.primaryEmailAddress?.emailAddress || ''}
                    </span>
                  </div>
                </div>

                <div className="flex flex-col gap-1">
                  <div className="px-3 py-1.5 text-[11px] text-muted-foreground font-mono flex items-center gap-1.5">
                    {isOnline ? (
                      <>
                        <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" />
                        <span>{user ? 'Authenticated via Clerk' : 'Connected via Google'}</span>
                      </>
                    ) : (
                      <>
                        <WifiOff className="h-3.5 w-3.5 text-amber-500" />
                        <span className="text-amber-500">Local Session (Offline)</span>
                      </>
                    )}
                  </div>

                  <button
                    type="button"
                    onClick={handleSignOut}
                    disabled={isSigningOut}
                    className="flex items-center gap-2 px-3 py-2 rounded-xl text-xs font-medium text-red-600 dark:text-red-400 hover:bg-red-500/10 transition-colors w-full text-left cursor-pointer disabled:opacity-50"
                  >
                    {isSigningOut ? (
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    ) : (
                      <LogOut className="h-3.5 w-3.5" />
                    )}
                    <span>{isSigningOut ? 'Signing out...' : 'Sign Out'}</span>
                  </button>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </header>
  );
};
