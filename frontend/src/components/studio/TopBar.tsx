import React, { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useClerk, useUser } from '@clerk/react';
import {
  LogOut,
  FolderKanban,
  CheckCircle2,
  AlertCircle,
  Menu,
  ChevronDown,
  WifiOff,
} from 'lucide-react';
import { ThemeToggle } from '@/components/ui/theme-toggle';
import type { Project } from '@/types/api';

interface TopBarProps {
  currentProject: Project | null;
  onSelectProject: (projectId: string | null) => void;
  projects: Project[];
  onOpenNewProject: () => void;
  isBackendHealthy: boolean;
  onToggleSidebar: () => void;
  isOnline?: boolean;
}

export const TopBar: React.FC<TopBarProps> = ({
  currentProject,
  onSelectProject,
  projects,
  onOpenNewProject,
  isBackendHealthy,
  onToggleSidebar,
  isOnline = true,
}) => {
  const navigate = useNavigate();
  const { user } = useUser();
  const { signOut } = useClerk();

  const [isUserMenuOpen, setIsUserMenuOpen] = useState(false);
  const [isProjectDropdownOpen, setIsProjectDropdownOpen] = useState(false);
  const userMenuRef = useRef<HTMLDivElement>(null);
  const projectDropdownRef = useRef<HTMLDivElement>(null);

  // Close menus on click outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (userMenuRef.current && !userMenuRef.current.contains(e.target as Node)) {
        setIsUserMenuOpen(false);
      }
      if (projectDropdownRef.current && !projectDropdownRef.current.contains(e.target as Node)) {
        setIsProjectDropdownOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleSignOut = async () => {
    await signOut();
    navigate('/auth');
  };

  return (
    <header className="h-14 border-b border-border/60 bg-card/60 backdrop-blur-xl px-4 sm:px-6 flex items-center justify-between z-30 shrink-0">
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

      {/* Center: Current Project Indicator */}
      <div className="relative hidden sm:block" ref={projectDropdownRef}>
        <button
          type="button"
          onClick={() => setIsProjectDropdownOpen((prev) => !prev)}
          className="flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium border border-border/60 bg-background/50 hover:bg-muted text-foreground transition-all cursor-pointer shadow-2xs"
        >
          <FolderKanban className="h-3.5 w-3.5 text-primary" />
          <span className="max-w-[160px] truncate">
            {currentProject ? currentProject.name : 'No Project (Global)'}
          </span>
          <ChevronDown className="h-3 w-3 text-muted-foreground" />
        </button>

        {isProjectDropdownOpen && (
          <div className="absolute left-1/2 -translate-x-1/2 mt-2 w-64 rounded-xl border border-border bg-card p-1.5 shadow-xl z-50 animate-in fade-in zoom-in-95 duration-100 max-h-72 overflow-y-auto">
            <div className="px-2.5 py-1 text-[10px] font-mono uppercase text-muted-foreground">
              Select Workspace Project
            </div>

            <button
              type="button"
              onClick={() => {
                onSelectProject(null);
                setIsProjectDropdownOpen(false);
              }}
              className={`w-full flex items-center justify-between px-2.5 py-1.5 rounded-lg text-xs font-medium transition-colors cursor-pointer ${
                currentProject === null
                  ? 'bg-primary/10 text-primary font-semibold'
                  : 'text-foreground hover:bg-muted'
              }`}
            >
              <span>No Project (Global Context)</span>
            </button>

            {projects.map((proj) => (
              <button
                key={proj.project_id}
                type="button"
                onClick={() => {
                  onSelectProject(proj.project_id);
                  setIsProjectDropdownOpen(false);
                }}
                className={`w-full flex items-center justify-between px-2.5 py-1.5 rounded-lg text-xs font-medium transition-colors cursor-pointer ${
                  currentProject?.project_id === proj.project_id
                    ? 'bg-primary/10 text-primary font-semibold'
                    : 'text-foreground hover:bg-muted'
                }`}
              >
                <span className="truncate">{proj.name}</span>
              </button>
            ))}

            <div className="pt-1 mt-1 border-t border-border/40">
              <button
                type="button"
                onClick={() => {
                  setIsProjectDropdownOpen(false);
                  onOpenNewProject();
                }}
                className="w-full text-left px-2.5 py-1.5 rounded-lg text-xs font-semibold text-primary hover:bg-primary/10 transition-colors cursor-pointer"
              >
                + Create New Project
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Right: Engine Status + Account Status + Theme + Clerk Avatar */}
      <div className="flex items-center gap-2 sm:gap-3">
        {/* Backend / Local Engine Health Pill */}
        <div
          className={`hidden md:flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-mono border ${
            isBackendHealthy
              ? 'border-border/50 bg-background/50 text-foreground'
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
          className={`hidden sm:flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-mono border ${
            !isOnline
              ? 'border-amber-500/30 bg-amber-500/10 text-amber-500'
              : 'border-border/50 bg-background/50 text-foreground'
          }`}
          title={
            !isOnline
              ? 'Internet disconnected • Running in local session mode'
              : user
              ? 'Clerk Cloud Connected • Active authenticated session'
              : 'Authentication required'
          }
        >
          {!isOnline ? (
            <>
              <WifiOff className="h-3 w-3 text-amber-500" />
              <span className="font-medium text-muted-foreground">Account</span>
              <span className="text-[10px] text-amber-500 font-semibold uppercase tracking-wider">Offline</span>
            </>
          ) : user ? (
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

        {/* Clerk User Avatar & Dropdown */}
        {user && (
          <div className="relative" ref={userMenuRef}>
            <button
              type="button"
              onClick={() => setIsUserMenuOpen((prev) => !prev)}
              className="relative flex items-center justify-center h-8 w-8 rounded-full border border-border bg-muted p-0.5 overflow-hidden transition-transform hover:scale-105 cursor-pointer focus:outline-none"
              aria-label="User account menu"
            >
              {user.imageUrl ? (
                <img
                  src={user.imageUrl}
                  alt={user.fullName || 'User'}
                  className="h-full w-full rounded-full object-cover"
                  referrerPolicy="no-referrer"
                />
              ) : (
                <span className="font-mono font-bold text-xs">
                  {(user.firstName?.[0] || 'U').toUpperCase()}
                </span>
              )}
            </button>

            {isUserMenuOpen && (
              <div className="absolute right-0 mt-2 w-56 rounded-2xl border border-border bg-card/95 backdrop-blur-xl p-3 shadow-2xl z-50 animate-in fade-in zoom-in-95 duration-100 flex flex-col gap-2">
                <div className="flex items-center gap-2.5 pb-2.5 border-b border-border/50">
                  {user.imageUrl ? (
                    <img
                      src={user.imageUrl}
                      alt={user.fullName || 'User'}
                      className="h-8 w-8 rounded-full object-cover border border-border"
                      referrerPolicy="no-referrer"
                    />
                  ) : (
                    <div className="h-8 w-8 rounded-full bg-primary/10 text-primary flex items-center justify-center font-bold text-xs">
                      {(user.firstName?.[0] || 'U').toUpperCase()}
                    </div>
                  )}
                  <div className="flex flex-col min-w-0">
                    <span className="text-xs font-semibold text-foreground truncate">
                      {user.fullName || user.firstName || 'Developer'}
                    </span>
                    <span className="text-[10px] font-mono text-muted-foreground truncate">
                      {user.primaryEmailAddress?.emailAddress || ''}
                    </span>
                  </div>
                </div>

                <div className="flex flex-col gap-1">
                  <div className="px-3 py-1.5 text-[11px] text-muted-foreground font-mono flex items-center gap-1.5">
                    {isOnline ? (
                      <>
                        <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" />
                        <span>Authenticated via Clerk</span>
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
                    className="flex items-center gap-2 px-3 py-2 rounded-xl text-xs font-medium text-red-600 dark:text-red-400 hover:bg-red-500/10 transition-colors w-full text-left cursor-pointer"
                  >
                    <LogOut className="h-3.5 w-3.5" />
                    <span>Sign Out</span>
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
