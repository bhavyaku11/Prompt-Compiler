import React, { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useClerk, useUser } from '@clerk/react';
import {
  SquarePen,
  ChevronLeft,
  HardDrive,
  Cpu,
  FolderOpen,
  RefreshCw,
  Loader2,
  Trash2,
  LogOut,
  History,
  Settings,
  Plus,
  BookOpen,
  Brain,
} from 'lucide-react';
import type { Project, CompilationHistoryItem } from '@/types/api';
import { selectProjectFolder, isTauri } from '@/api/tauri-bridge';
import { updateProject } from '@/api/projects';
import { ingestProjectDirectory } from '@/api/knowledge';
import { signOutApp } from '@/api/auth';
import { Logo } from '@/components/ui/Logo';
import { UserAvatar } from '@/components/ui/UserAvatar';

export interface SidebarProps {
  isOpen: boolean;
  onToggle: () => void;
  onNewCompilation: () => void;
  history?: CompilationHistoryItem[];
  selectedHistoryId?: string | null;
  onSelectHistory?: (item: CompilationHistoryItem) => void;
  onDeleteHistory?: (id: string) => void;
  onClearHistory?: () => void;
  projects: Project[];
  selectedProjectId: string | null;
  onSelectProject: (projectId: string | null) => void;
  onOpenNewProject: () => void;
  isBackendHealthy: boolean;
  activeProjectMemoryCount?: number;
  activeProjectKnowledgeCount?: number;
  onUpdateProject?: (project: Project) => void;
  onDeleteProject?: (projectId: string) => Promise<void> | void;
  onRefreshKnowledge?: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  isOpen,
  onToggle,
  onNewCompilation,
  history = [],
  selectedHistoryId = null,
  onSelectHistory,
  onDeleteHistory,
  onClearHistory,
  projects,
  selectedProjectId,
  onSelectProject,
  onOpenNewProject,
  isBackendHealthy,
  activeProjectMemoryCount = 0,
  activeProjectKnowledgeCount = 0,
  onUpdateProject,
  onDeleteProject,
  onRefreshKnowledge,
}) => {
  const navigate = useNavigate();
  const { user } = useUser();
  const { signOut } = useClerk();
  const [isSigningOut, setIsSigningOut] = useState(false);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [isProjectSectionOpen, setIsProjectSectionOpen] = useState(false);

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

  const [isUpdatingFolder, setIsUpdatingFolder] = useState(false);
  const [isIngesting, setIsIngesting] = useState(false);
  const [folderStatus, setFolderStatus] = useState<string | null>(null);

  const settingsRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (settingsRef.current && !settingsRef.current.contains(e.target as Node)) {
        setIsSettingsOpen(false);
      }
    };
    if (isSettingsOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [isSettingsOpen]);

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

  const selectedProject = projects.find((p) => p.project_id === selectedProjectId);

  const handleChangeFolder = async () => {
    if (!selectedProject) return;
    setIsUpdatingFolder(true);
    setFolderStatus(null);
    try {
      const selected = await selectProjectFolder(selectedProject.root_path || undefined);
      if (!selected) {
        if (!isTauri()) {
          setFolderStatus('Native folder picker requires desktop app.');
        }
        setIsUpdatingFolder(false);
        return;
      }

      const updated = await updateProject(selectedProject.project_id, {
        root_path: selected,
      });
      onUpdateProject?.(updated);
      setFolderStatus(`Folder linked: ${selected.split('/').pop() || selected}`);
    } catch (err: unknown) {
      setFolderStatus(err instanceof Error ? err.message : 'Failed to update folder');
    } finally {
      setIsUpdatingFolder(false);
    }
  };

  const handleIngestDirectory = async () => {
    if (!selectedProject || !selectedProject.root_path) return;
    setIsIngesting(true);
    setFolderStatus('Ingesting documents from project folder...');
    try {
      const res = await ingestProjectDirectory(selectedProject.project_id, {
        recursive: true,
      });
      setFolderStatus(
        `Ingested: ${res.indexed} new, ${res.unchanged} unchanged (${res.total} total)`
      );
      onRefreshKnowledge?.();
    } catch (err: unknown) {
      setFolderStatus(err instanceof Error ? err.message : 'Ingestion failed');
    } finally {
      setIsIngesting(false);
    }
  };

  return (
    <>
      {/* Mobile Drawer Backdrop */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-black/60 backdrop-blur-xs z-40 md:hidden animate-in fade-in duration-200"
          onClick={onToggle}
        />
      )}

      {/* Sidebar Container */}
      <aside
        className={`fixed md:static inset-y-0 left-0 z-50 flex flex-col justify-between border-r border-sidebar-border bg-sidebar backdrop-blur-xl transition-all duration-300 ease-in-out shrink-0 h-screen select-none ${
          isOpen ? 'w-72 translate-x-0' : '-translate-x-full md:translate-x-0 md:w-16'
        }`}
      >
        {/* ========================================================================= */}
        {/* TOP HEADER */}
        {/* ========================================================================= */}
        <div className="h-14 flex items-center justify-between px-3.5 border-b border-sidebar-border/60 shrink-0">
          {isOpen ? (
            /* EXPANDED HEADER: (logo) STUDIO on left, < on right */
            <div className="flex items-center justify-between w-full min-w-0">
              <button
                type="button"
                onClick={() => navigate('/')}
                className="flex items-center gap-2.5 text-left cursor-pointer group transition-opacity hover:opacity-90 min-w-0"
                title="Return to Home"
              >
                <Logo size="sm" />
                <span className="text-[11px] font-mono px-2 py-0.5 rounded-lg bg-card text-foreground border border-border/80 font-bold uppercase tracking-wider shrink-0 shadow-2xs">
                  STUDIO
                </span>
              </button>

              {/* Collapse button: < sign as requested in user specification */}
              <button
                type="button"
                onClick={onToggle}
                className="p-1.5 rounded-lg text-muted-foreground hover:text-foreground hover:bg-card/80 transition-colors cursor-pointer shrink-0 border border-transparent hover:border-border/60"
                title="Collapse sidebar"
                aria-label="Collapse sidebar"
              >
                <ChevronLeft className="h-4 w-4" />
              </button>
            </div>
          ) : (
            /* COLLAPSED HEADER: (logo) only */
            /* Crucial: Clicking logo in collapsed mode expands sidebar instead of redirecting */
            <div className="flex items-center justify-center w-full">
              <button
                type="button"
                onClick={onToggle}
                className="p-1 rounded-xl hover:bg-card/80 transition-all cursor-pointer group flex items-center justify-center"
                title="Click logo to expand sidebar"
                aria-label="Expand sidebar"
              >
                <Logo size="sm" />
              </button>
            </div>
          )}
        </div>

        {/* ========================================================================= */}
        {/* NEW CONVERSATION / NEW COMPILATION BUTTON */}
        {/* ========================================================================= */}
        <div className="p-3 shrink-0">
          {isOpen ? (
            /* EXPANDED: [ New Convers. 📝 ] */
            <button
              type="button"
              onClick={onNewCompilation}
              className="w-full flex items-center justify-between px-3.5 py-2.5 rounded-xl border border-border/80 bg-card hover:bg-card/80 text-foreground transition-all duration-150 shadow-2xs cursor-pointer group hover:border-primary/40"
              title="Start New Conversation / Compilation"
            >
              <span className="text-xs font-medium text-foreground tracking-tight">New Convers.</span>
              <SquarePen className="h-4 w-4 text-muted-foreground group-hover:text-primary transition-colors shrink-0" />
            </button>
          ) : (
            /* COLLAPSED: [ 📝 ] icon button */
            <div className="flex justify-center">
              <button
                type="button"
                onClick={onNewCompilation}
                className="w-10 h-10 rounded-xl bg-card border border-border/80 hover:bg-primary/10 hover:border-primary/30 hover:text-primary text-foreground transition-all duration-150 shadow-2xs flex items-center justify-center cursor-pointer group"
                title="Start New Conversation / Compilation"
                aria-label="New Conversation"
              >
                <SquarePen className="h-4 w-4 text-muted-foreground group-hover:text-primary transition-colors" />
              </button>
            </div>
          )}
        </div>

        {/* ========================================================================= */}
        {/* MIDDLE SECTION: HISTORY CONTAINER (MATCHING SKETCH) */}
        {/* ========================================================================= */}
        {isOpen ? (
          <div className="flex-1 flex flex-col min-h-0 px-3 pb-2 overflow-hidden">
            {/* Project Switcher Pill */}
            <div className="mb-2 px-1 flex items-center justify-between text-[11px]">
              <button
                type="button"
                onClick={() => setIsProjectSectionOpen((v) => !v)}
                className="flex items-center gap-1.5 text-muted-foreground hover:text-foreground transition-colors cursor-pointer truncate max-w-[190px]"
                title="Switch Workspace Project"
              >
                <FolderOpen className="h-3.5 w-3.5 text-primary shrink-0" />
                <span className="truncate font-mono font-medium">
                  {selectedProject ? selectedProject.name : 'Global Context'}
                </span>
                <span className="text-[9px] text-muted-foreground/70">▾</span>
              </button>
              <button
                type="button"
                onClick={onOpenNewProject}
                className="text-[10px] text-primary hover:underline cursor-pointer flex items-center gap-0.5"
                title="Create New Project"
              >
                <Plus className="h-3 w-3" />
                <span>Project</span>
              </button>
            </div>

            {/* Quick Project Switcher Dropdown (when opened) */}
            {isProjectSectionOpen && (
              <div className="mb-2 p-2 rounded-xl border border-border/70 bg-card/90 shadow-xs space-y-1 max-h-48 overflow-y-auto text-xs animate-in fade-in slide-in-from-top-1 duration-150">
                <button
                  type="button"
                  onClick={() => {
                    onSelectProject(null);
                    setIsProjectSectionOpen(false);
                  }}
                  className={`w-full flex items-center gap-2 px-2 py-1.5 rounded-lg text-left transition-colors cursor-pointer ${
                    selectedProjectId === null
                      ? 'bg-primary/10 text-primary font-semibold'
                      : 'text-muted-foreground hover:text-foreground hover:bg-muted/40'
                  }`}
                >
                  <HardDrive className="h-3.5 w-3.5 shrink-0" />
                  <span className="truncate">Global Context</span>
                </button>
                {projects.map((p) => (
                  <div
                    key={p.project_id}
                    className={`flex items-center justify-between px-2 py-1.5 rounded-lg text-left transition-colors ${
                      selectedProjectId === p.project_id
                        ? 'bg-primary/10 text-primary font-semibold'
                        : 'text-muted-foreground hover:text-foreground hover:bg-muted/40'
                    }`}
                  >
                    <button
                      type="button"
                      onClick={() => {
                        onSelectProject(p.project_id);
                        setIsProjectSectionOpen(false);
                      }}
                      className="flex-1 truncate cursor-pointer text-left"
                      title={p.name}
                    >
                      {p.name}
                    </button>
                    {onDeleteProject && (
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          if (window.confirm(`Delete project "${p.name}"?`)) {
                            void onDeleteProject(p.project_id);
                          }
                        }}
                        className="p-1 hover:text-red-500 rounded cursor-pointer"
                        title="Delete project"
                      >
                        <Trash2 className="h-3 w-3" />
                      </button>
                    )}
                  </div>
                ))}
              </div>
            )}

            {/* Large History Container matching sketch */}
            <div className="flex-1 flex flex-col min-h-0 rounded-2xl border border-border/80 bg-card/30 backdrop-blur-xs overflow-hidden shadow-2xs">
              {/* History Container Header */}
              <div className="flex items-center justify-between px-3 py-2 border-b border-border/60 bg-muted/20 shrink-0">
                <div className="flex items-center gap-1.5">
                  <History className="h-3.5 w-3.5 text-muted-foreground" />
                  <span className="text-xs font-semibold text-foreground tracking-tight">History</span>
                  {history.length > 0 && (
                    <span className="text-[10px] font-mono px-1.5 py-0.2 rounded-full bg-muted/80 text-muted-foreground">
                      {history.length}
                    </span>
                  )}
                </div>
                {history.length > 0 && onClearHistory && (
                  <button
                    type="button"
                    onClick={onClearHistory}
                    className="text-[10px] text-muted-foreground hover:text-red-500 transition-colors cursor-pointer"
                    title="Clear history"
                  >
                    Clear
                  </button>
                )}
              </div>

              {/* History Scrollable Items */}
              <div className="flex-1 overflow-y-auto p-2 space-y-1">
                {history.length === 0 ? (
                  <div className="h-full flex flex-col items-center justify-center p-4 text-center text-muted-foreground/70">
                    <History className="h-8 w-8 text-muted-foreground/30 mb-2" />
                    <p className="text-xs font-medium text-foreground/80">No history yet</p>
                    <p className="text-[10px] text-muted-foreground mt-0.5 max-w-[150px] leading-tight">
                      Previous conversations and compilations will appear here.
                    </p>
                  </div>
                ) : (
                  history.map((item) => {
                    const isSelected = selectedHistoryId === item.id;
                    return (
                      <div
                        key={item.id}
                        onClick={() => onSelectHistory?.(item)}
                        className={`group/item relative flex items-center justify-between p-2 rounded-xl text-left cursor-pointer transition-all duration-150 ${
                          isSelected
                            ? 'bg-primary/10 text-primary font-medium border border-primary/25 shadow-2xs'
                            : 'text-muted-foreground hover:text-foreground hover:bg-card border border-transparent hover:border-border/60'
                        }`}
                        title={item.prompt}
                      >
                        <div className="flex-1 min-w-0 pr-1">
                          <p className="text-xs truncate font-medium text-foreground leading-snug">
                            {item.prompt || 'Untitled Compilation'}
                          </p>
                          <div className="flex items-center gap-1.5 mt-0.5 text-[9px] text-muted-foreground font-mono">
                            <span className="px-1 py-0.2 rounded bg-muted/60 text-muted-foreground uppercase text-[8px] font-semibold">
                              {item.targetAgent}
                            </span>
                            <span>•</span>
                            <span>{item.timestamp}</span>
                          </div>
                        </div>

                        {onDeleteHistory && (
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              onDeleteHistory(item.id);
                            }}
                            className="opacity-0 group-hover/item:opacity-100 p-1 rounded-md hover:bg-red-500/20 text-muted-foreground hover:text-red-500 transition-all cursor-pointer shrink-0"
                            title="Delete item"
                            aria-label="Delete history item"
                          >
                            <Trash2 className="h-3 w-3" />
                          </button>
                        )}
                      </div>
                    );
                  })
                )}
              </div>
            </div>
          </div>
        ) : (
          /* Collapsed Middle: Clean empty space matching sketch */
          <div className="flex-1" />
        )}

        {/* ========================================================================= */}
        {/* BOTTOM FOOTER */}
        {/* ========================================================================= */}
        <div className="p-3 border-t border-sidebar-border bg-sidebar/95 relative shrink-0">
          {isOpen ? (
            /* EXPANDED FOOTER: [ USER NAME ] on left, [ ⚙️ ] on right */
            <div className="flex items-center justify-between gap-2">
              <button
                type="button"
                onClick={() => setIsSettingsOpen((prev) => !prev)}
                className="flex items-center gap-2.5 min-w-0 flex-1 text-left p-1 -m-1 rounded-xl hover:bg-card/70 transition-colors cursor-pointer group"
                title="Account Settings & Engine Status"
              >
                {/* Profile Picture */}
                <UserAvatar
                  imageUrl={activeUser?.imageUrl}
                  name={activeUser?.fullName || activeUser?.firstName}
                  email={activeUser?.primaryEmailAddress?.emailAddress}
                  size="md"
                />
                <div className="flex flex-col min-w-0 text-left">
                  <span className="text-xs font-semibold text-foreground truncate group-hover:text-primary transition-colors">
                    {activeUser?.fullName || activeUser?.firstName || 'Developer'}
                  </span>
                  <span className="text-[10px] font-mono text-muted-foreground truncate">
                    {activeUser?.primaryEmailAddress?.emailAddress || 'Local Developer'}
                  </span>
                </div>
              </button>

              {/* Settings Gear Icon matching sketch [ ⚙️ ] */}
              <button
                type="button"
                onClick={() => setIsSettingsOpen((prev) => !prev)}
                className={`p-2 rounded-xl text-muted-foreground hover:text-foreground hover:bg-card transition-colors cursor-pointer shrink-0 border border-transparent ${
                  isSettingsOpen ? 'bg-card text-foreground border-border/80 shadow-2xs' : ''
                }`}
                title="Settings & System Status"
                aria-label="Settings"
              >
                <Settings className="h-4 w-4" />
              </button>
            </div>
          ) : (
            /* COLLAPSED FOOTER: Profile Picture circle at the very bottom matching sketch arrow */
            <div className="flex justify-center">
              <button
                type="button"
                onClick={() => setIsSettingsOpen((prev) => !prev)}
                className="relative group p-0.5 rounded-full hover:ring-2 hover:ring-primary/40 transition-all cursor-pointer focus:outline-none"
                title={`Signed in as ${activeUser?.fullName || activeUser?.firstName || 'Developer'} • Click for Settings`}
                aria-label="Profile Picture Settings"
              >
                <UserAvatar
                  imageUrl={activeUser?.imageUrl}
                  name={activeUser?.fullName || activeUser?.firstName}
                  email={activeUser?.primaryEmailAddress?.emailAddress}
                  size="md"
                />
              </button>
            </div>
          )}

          {/* ========================================================================= */}
          {/* SETTINGS & SYSTEM STATUS POPOVER */}
          {/* ========================================================================= */}
          {isSettingsOpen && (
            <div
              ref={settingsRef}
              className={`absolute z-50 p-3.5 rounded-2xl border border-border/80 bg-card/95 backdrop-blur-xl shadow-xl w-72 space-y-3 animate-in fade-in zoom-in-95 duration-150 ${
                isOpen ? 'bottom-16 left-3' : 'bottom-3 left-18'
              }`}
            >
              {/* User Account Info */}
              <div className="flex items-center gap-2.5 pb-2.5 border-b border-border/60">
                <UserAvatar
                  imageUrl={activeUser?.imageUrl}
                  name={activeUser?.fullName || activeUser?.firstName}
                  email={activeUser?.primaryEmailAddress?.emailAddress}
                  size="lg"
                />
                <div className="flex flex-col min-w-0">
                  <span className="text-xs font-bold text-foreground truncate">
                    {activeUser?.fullName || activeUser?.firstName || 'Developer'}
                  </span>
                  <span className="text-[10px] font-mono text-muted-foreground truncate">
                    {activeUser?.primaryEmailAddress?.emailAddress || 'Local Developer'}
                  </span>
                </div>
              </div>

              {/* Local Engine Status */}
              <div className="p-2.5 rounded-xl border border-border/70 bg-muted/20 space-y-1 text-xs font-mono">
                <div className="flex items-center justify-between text-[10px] text-muted-foreground">
                  <span className="flex items-center gap-1.5 font-semibold">
                    <Cpu className="h-3 w-3 text-primary" />
                    <span>LOCAL ENGINE</span>
                  </span>
                  <span
                    className={`h-2 w-2 rounded-full ${
                      isBackendHealthy ? 'bg-emerald-500 shadow-xs shadow-emerald-500/50' : 'bg-amber-500'
                    }`}
                  />
                </div>
                <p className="text-[11px] text-foreground font-semibold truncate">
                  Ollama • qwen3:0.6b
                </p>
                <p className="text-[10px] text-muted-foreground">
                  sqlite-vec • nomic-embed-text
                </p>
              </div>

              {/* Project & Knowledge Summary if active */}
              {selectedProject && (
                <div className="p-2 rounded-xl border border-border/60 bg-muted/10 space-y-1.5 text-xs">
                  <div className="flex items-center justify-between text-[10px] font-mono">
                    <span className="text-muted-foreground uppercase">Project Folder</span>
                    <span className={selectedProject.root_path ? 'text-emerald-500 font-semibold' : 'text-amber-500'}>
                      {selectedProject.root_path ? 'Linked' : 'Unlinked'}
                    </span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <button
                      type="button"
                      onClick={handleChangeFolder}
                      disabled={isUpdatingFolder}
                      className="flex-1 py-1 px-2 text-[10px] font-medium rounded-lg border border-border bg-card hover:bg-muted text-foreground transition-colors cursor-pointer flex items-center justify-center gap-1 shadow-2xs"
                    >
                      {isUpdatingFolder ? <Loader2 className="h-3 w-3 animate-spin" /> : <FolderOpen className="h-3 w-3" />}
                      <span>{selectedProject.root_path ? 'Change Folder' : 'Link Folder'}</span>
                    </button>
                    {selectedProject.root_path && (
                      <button
                        type="button"
                        onClick={handleIngestDirectory}
                        disabled={isIngesting}
                        className="py-1 px-2 text-[10px] font-medium rounded-lg bg-primary/10 hover:bg-primary/20 text-primary border border-primary/20 transition-colors cursor-pointer flex items-center gap-1 shadow-2xs"
                      >
                        {isIngesting ? <Loader2 className="h-3 w-3 animate-spin" /> : <RefreshCw className="h-3 w-3" />}
                        <span>Ingest</span>
                      </button>
                    )}
                  </div>
                  {folderStatus && (
                    <p className="text-[9px] text-muted-foreground leading-tight">{folderStatus}</p>
                  )}
                  <div className="flex items-center justify-between text-[10px] text-muted-foreground pt-1 border-t border-border/40">
                    <span className="flex items-center gap-1"><BookOpen className="h-3 w-3" /> Sources: {activeProjectKnowledgeCount}</span>
                    <span className="flex items-center gap-1"><Brain className="h-3 w-3" /> Memories: {activeProjectMemoryCount}</span>
                  </div>
                </div>
              )}

              {/* Sign Out Button */}
              <button
                type="button"
                onClick={handleSignOut}
                disabled={isSigningOut}
                className="w-full flex items-center justify-center gap-2 py-2 px-3 rounded-xl border border-red-500/20 bg-red-500/10 hover:bg-red-500/20 text-red-600 dark:text-red-400 text-xs font-semibold transition-colors cursor-pointer shadow-2xs disabled:opacity-50"
              >
                {isSigningOut ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <LogOut className="h-3.5 w-3.5" />
                )}
                <span>Sign Out</span>
              </button>
            </div>
          )}
        </div>
      </aside>
    </>
  );
};

export default Sidebar;
