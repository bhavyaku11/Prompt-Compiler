import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth, useUser, useClerk } from '@clerk/react';
import { Terminal, ArrowUpRight, LogOut } from 'lucide-react';
import { GithubIcon } from '@/components/ui/icons';
import { ThemeToggle } from '@/components/ui/theme-toggle';
import { MagneticButton } from '@/components/ui/magnetic-button';
import { Logo } from '@/components/ui/Logo';
import { UserAvatar } from '@/components/ui/UserAvatar';
import { signOutApp, getDesktopUser, getDesktopToken, type DesktopUser } from '@/api/auth';

export const Navbar = () => {
  const navigate = useNavigate();
  const { isSignedIn } = useAuth();
  const { user } = useUser();
  const { signOut } = useClerk();
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  const [desktopUser, setDesktopUser] = useState<DesktopUser | null>(() => getDesktopUser());
  const [desktopToken, setDesktopToken] = useState<string | null>(() => getDesktopToken());

  // Listen for storage changes or sign-in / sign-out events across windows and sessions
  useEffect(() => {
    const syncUser = () => {
      setDesktopUser(getDesktopUser());
      setDesktopToken(getDesktopToken());
    };
    window.addEventListener('prompt-compiler:signed-out', syncUser);
    window.addEventListener('storage', syncUser);
    return () => {
      window.removeEventListener('prompt-compiler:signed-out', syncUser);
      window.removeEventListener('storage', syncUser);
    };
  }, []);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setIsMenuOpen(false);
      }
    };
    if (isMenuOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [isMenuOpen]);

  // Compute unified user profile from Clerk user or cached Desktop session
  const activeUser = user
    ? {
        fullName:
          user.fullName ||
          `${user.firstName || ''} ${user.lastName || ''}`.trim() ||
          user.username ||
          user.primaryEmailAddress?.emailAddress?.split('@')[0],
        firstName: user.firstName || user.username,
        email: user.primaryEmailAddress?.emailAddress || '',
        imageUrl: user.imageUrl || null,
      }
    : desktopUser
    ? {
        fullName:
          `${desktopUser.firstName || ''} ${desktopUser.lastName || ''}`.trim() ||
          desktopUser.email?.split('@')[0] ||
          'Developer',
        firstName: desktopUser.firstName,
        email: desktopUser.email || '',
        imageUrl: desktopUser.imageUrl || null,
      }
    : null;

  const isAuthenticated = Boolean(isSignedIn && user) || Boolean(desktopToken && activeUser);

  const handleSignOut = async () => {
    setIsMenuOpen(false);
    await signOutApp(signOut, () => {
      setDesktopUser(null);
      setDesktopToken(null);
      navigate('/');
    });
  };

  return (
    <header className="relative z-20 flex items-center justify-between px-6 py-3.5 md:px-12 md:py-4.5 max-w-7xl mx-auto w-full">
      {/* Brand / Logo */}
      <div 
        data-magnetic 
        onClick={() => navigate('/')}
        className="flex items-center gap-3 cursor-pointer group transition-colors duration-200"
      >
        <Logo size="lg" />
        <span className="text-lg font-bold tracking-tight text-foreground">
          Prompt Compiler
        </span>
      </div>

      {/* Navigation Actions */}
      <nav aria-label="Main Navigation" className="flex items-center gap-2 sm:gap-3">
        {/* Theme Toggle Button */}
        <ThemeToggle />

        {/* GitHub link with 3D Magnetic Floating Effect */}
        <MagneticButton
          as="a"
          href="https://github.com/bhavyaku11/Prompt-Compiler"
          target="_blank"
          rel="noopener noreferrer"
          aria-label="GitHub Repository"
          className="flex items-center gap-2 px-3.5 sm:px-4 py-2 rounded-full border border-neutral-300 dark:border-white/15 bg-neutral-100/90 dark:bg-white/5 text-sm font-medium text-neutral-800 dark:text-neutral-100 backdrop-blur-sm transition-colors duration-200 hover:bg-neutral-200 dark:hover:bg-white/10 hover:border-neutral-400 dark:hover:border-white/30 hover:text-black dark:hover:text-white"
        >
          <GithubIcon className="h-4 w-4 pointer-events-none" />
          <span className="hidden sm:inline pointer-events-none">GitHub</span>
          <ArrowUpRight className="h-3.5 w-3.5 text-neutral-500 dark:text-neutral-400 pointer-events-none" />
        </MagneticButton>

        {/* Profile Picture when logged in, or Login Button when logged out */}
        {isAuthenticated && activeUser ? (
          <div className="relative" ref={menuRef}>
            <MagneticButton
              as="button"
              type="button"
              onClick={() => setIsMenuOpen((prev) => !prev)}
              aria-label="User profile menu"
              aria-expanded={isMenuOpen}
              className="relative flex items-center justify-center h-9 w-9 sm:h-10 sm:w-10 rounded-full border border-neutral-300 dark:border-white/20 bg-neutral-100/90 dark:bg-white/5 p-0.5 overflow-hidden shadow-sm transition-all duration-200 hover:scale-105 hover:border-neutral-400 dark:hover:border-white/40 cursor-pointer focus:outline-none"
            >
              <UserAvatar
                imageUrl={activeUser.imageUrl}
                name={activeUser.fullName}
                email={activeUser.email}
                size="md"
              />
            </MagneticButton>

            {/* Dropdown Menu */}
            {isMenuOpen && (
              <div 
                className="absolute right-0 mt-2.5 w-60 rounded-2xl border border-neutral-200 dark:border-white/15 bg-white/95 dark:bg-[#121215]/95 backdrop-blur-xl p-3 shadow-2xl z-50 animate-in fade-in zoom-in-95 duration-150 flex flex-col gap-2.5"
                role="menu"
              >
                {/* User Info Header */}
                <div className="flex items-center gap-2.5 pb-2.5 border-b border-neutral-100 dark:border-white/10">
                  <UserAvatar
                    imageUrl={activeUser.imageUrl}
                    name={activeUser.fullName}
                    email={activeUser.email}
                    size="lg"
                  />
                  <div className="flex flex-col min-w-0">
                    <span className="text-xs font-semibold text-foreground truncate">
                      {activeUser.fullName || "Developer"}
                    </span>
                    <span className="text-[11px] font-mono text-muted-foreground truncate">
                      {activeUser.email || ""}
                    </span>
                  </div>
                </div>

                {/* Actions */}
                <div className="flex flex-col gap-1">
                  <button
                    type="button"
                    onClick={() => {
                      setIsMenuOpen(false);
                      navigate('/studio');
                    }}
                    className="flex items-center gap-2.5 px-3 py-2 rounded-xl text-xs font-medium text-foreground hover:bg-neutral-100 dark:hover:bg-white/10 transition-colors w-full text-left cursor-pointer"
                    role="menuitem"
                  >
                    <Terminal className="h-3.5 w-3.5 text-emerald-500" />
                    <span>Open Studio</span>
                  </button>

                  <button
                    type="button"
                    onClick={handleSignOut}
                    className="flex items-center gap-2.5 px-3 py-2 rounded-xl text-xs font-medium text-red-600 dark:text-red-400 hover:bg-red-500/10 transition-colors w-full text-left cursor-pointer"
                    role="menuitem"
                  >
                    <LogOut className="h-3.5 w-3.5" />
                    <span>Sign Out</span>
                  </button>
                </div>
              </div>
            )}
          </div>
        ) : (
          /* Login / Access action with 3D Magnetic Floating Effect */
          <MagneticButton
            as="button"
            type="button"
            onClick={() => navigate('/auth')}
            aria-label="Open Studio / Login"
            className="flex items-center gap-2 px-4 py-2 rounded-full bg-neutral-900 text-white dark:bg-white dark:text-neutral-950 text-sm font-semibold transition-colors duration-200 hover:bg-neutral-800 dark:hover:bg-neutral-100 hover:shadow-lg cursor-pointer"
          >
            <span className="pointer-events-none">Login</span>
          </MagneticButton>
        )}
      </nav>
    </header>
  );
};

export default Navbar;
