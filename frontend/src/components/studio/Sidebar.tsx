import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useUser } from '@clerk/react';
import {
  Plus,
  BookOpen,
  Brain,
  ChevronLeft,
  ChevronRight,
  HardDrive,
  Cpu,
  Layers,
  FolderOpen,
  RefreshCw,
  Loader2,
  Trash2,
} from 'lucide-react';
import type { Project } from '@/types/api';
import { selectProjectFolder, isTauri } from '@/api/tauri-bridge';
import { updateProject } from '@/api/projects';
import { ingestProjectDirectory } from '@/api/knowledge';
import { Logo } from '@/components/ui/Logo';

interface SidebarProps {
  isOpen: boolean;
  onToggle: () => void;
  onNewCompilation: () => void;
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
  const [isUpdatingFolder, setIsUpdatingFolder] = useState(false);
  const [isIngesting, setIsIngesting] = useState(false);
  const [folderStatus, setFolderStatus] = useState<string | null>(null);

  const selectedProject = projects.find((p) => p.project_id === selectedProjectId);

  const handleChangeFolder = async () => {
    if (!selectedProject) return;
    setIsUpdatingFolder(true);
    setFolderStatus(null);
    try {
      const selected = await selectProjectFolder(selectedProject.root_path || undefined);
      if (!selected) {
        if (!isTauri()) {
          setFolderStatus('Native folder picker requires the desktop app.');
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
        className={`fixed md:static inset-y-0 left-0 z-50 flex flex-col justify-between border-r border-sidebar-border bg-sidebar backdrop-blur-xl transition-all duration-300 ease-in-out shrink-0 ${
          isOpen ? 'w-72 translate-x-0' : '-translate-x-full md:translate-x-0 md:w-16'
        }`}
      >
        {/* Top: Header & New Compilation */}
        <div className="flex flex-col gap-3.5 p-3.5 border-b border-sidebar-border/60">
          {/* Brand Logo & Collapse Toggle */}
          <div className="flex items-center justify-between gap-1">
            {isOpen ? (
              <button
                type="button"
                onClick={() => navigate('/')}
                className="flex items-center gap-2 px-1 text-left cursor-pointer group transition-opacity hover:opacity-90 min-w-0"
                title="Return to Home"
              >
                <Logo size="sm" />
                <span className="text-xs font-bold tracking-tight text-foreground font-mono whitespace-nowrap">
                  Prompt Compiler
                </span>
                <span className="text-[9px] font-mono px-1.5 py-0.5 rounded-full bg-primary/10 text-primary border border-primary/20 font-semibold uppercase tracking-wider shrink-0">
                  Studio
                </span>
              </button>
            ) : (
              <button
                type="button"
                onClick={() => navigate('/')}
                className="mx-auto cursor-pointer group transition-opacity hover:opacity-90"
                title="Return to Home"
              >
                <Logo size="sm" />
              </button>
            )}

            {/* Toggle Arrow (Desktop) */}
            <button
              type="button"
              onClick={onToggle}
              className={`hidden md:flex p-1 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted transition-colors cursor-pointer shrink-0 ${
                !isOpen ? 'mt-2 mx-auto' : ''
              }`}
              title={isOpen ? 'Collapse sidebar' : 'Expand sidebar'}
              aria-label={isOpen ? 'Collapse sidebar' : 'Expand sidebar'}
            >
              {isOpen ? <ChevronLeft className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
            </button>
          </div>

          {/* New Compilation Action Button */}
          <button
            type="button"
            onClick={onNewCompilation}
            className={`flex items-center justify-center gap-2 rounded-xl text-xs font-semibold bg-primary text-primary-foreground hover:opacity-90 transition-all duration-150 shadow-xs cursor-pointer ${
              isOpen ? 'w-full py-2 px-3' : 'w-9 h-9 mx-auto'
            }`}
            title="Start New Compilation"
          >
            <Plus className="h-4 w-4 stroke-[2.5]" />
            {isOpen && <span>New Compilation</span>}
          </button>
        </div>

        {/* Middle Navigation Groups */}
        <div className="flex-1 overflow-y-auto px-3 py-2 space-y-4 text-left">
          {/* Workspace */}
          <div className="space-y-1">
            {isOpen && (
              <span className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground/70 px-2 block">
                Workspace
              </span>
            )}
            <button
              type="button"
              className={`w-full flex items-center gap-2.5 px-2.5 py-1.5 rounded-lg text-xs font-semibold bg-card text-foreground shadow-2xs border border-border/80 transition-colors cursor-pointer ${
                !isOpen ? 'justify-center' : ''
              }`}
              title="Studio Workspace"
            >
              <Layers className="h-4 w-4 shrink-0 text-primary" />
              {isOpen && <span>Studio</span>}
            </button>
          </div>

          {/* Project Management */}
          <div className="space-y-1">
            {isOpen && (
              <div className="flex items-center justify-between px-2">
                <span className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground/70">
                  Project
                </span>
                <span className="text-[10px] font-mono text-muted-foreground">
                  {projects.length}
                </span>
              </div>
            )}

            <button
              type="button"
              onClick={() => onSelectProject(null)}
              className={`w-full flex items-center gap-2.5 px-2.5 py-1.5 rounded-lg text-xs font-medium transition-all cursor-pointer ${
                selectedProjectId === null
                  ? 'bg-card text-foreground font-semibold shadow-2xs border border-border/80'
                  : 'text-muted-foreground hover:text-foreground hover:bg-card/40'
              } ${!isOpen ? 'justify-center' : ''}`}
              title="Global Context (No Project)"
            >
              <HardDrive className="h-4 w-4 shrink-0 text-muted-foreground" />
              {isOpen && <span className="truncate">Global Context</span>}
            </button>

            {/* List first 4 projects or selected project */}
            {isOpen && (
              <div className="space-y-0.5 pl-2 pt-1 border-l border-border/40 ml-3">
                {projects.map((p) => (
                  <div
                    key={p.project_id}
                    className={`group/proj w-full flex items-center justify-between px-2 py-1 rounded-md text-[11px] transition-colors ${
                      selectedProjectId === p.project_id
                        ? 'text-primary font-bold bg-primary/10'
                        : 'text-muted-foreground hover:text-foreground hover:bg-muted/30'
                    }`}
                  >
                    <button
                      type="button"
                      onClick={() => onSelectProject(p.project_id)}
                      className="flex-1 text-left truncate cursor-pointer mr-1"
                      title={p.name}
                    >
                      <span className="truncate block max-w-[130px]">{p.name}</span>
                    </button>

                    {onDeleteProject && (
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          if (
                            window.confirm(
                              `Delete project "${p.name}"? This will remove all associated memories and documents.`
                            )
                          ) {
                            void onDeleteProject(p.project_id);
                          }
                        }}
                        className="opacity-0 group-hover/proj:opacity-100 p-0.5 rounded hover:bg-red-500/20 text-muted-foreground hover:text-red-500 transition-all cursor-pointer shrink-0"
                        title={`Delete ${p.name}`}
                        aria-label={`Delete ${p.name}`}
                      >
                        <Trash2 className="h-3 w-3" />
                      </button>
                    )}
                  </div>
                ))}

                <button
                  type="button"
                  onClick={onOpenNewProject}
                  className="w-full flex items-center gap-1.5 px-2 py-1 rounded-md text-[11px] text-primary hover:bg-primary/10 transition-colors cursor-pointer mt-1 font-medium"
                >
                  <Plus className="h-3 w-3" />
                  <span>New Project</span>
                </button>
              </div>
            )}

            {/* Selected Project Folder Section */}
            {isOpen && selectedProject && (
              <div className="mt-2 p-2 rounded-xl border border-border/60 bg-muted/20 space-y-1.5 text-xs">
                <div className="flex items-center justify-between text-[10px] font-mono">
                  <span className="text-muted-foreground uppercase tracking-wider">
                    Project Folder
                  </span>
                  {selectedProject.root_path ? (
                    <span className="text-emerald-500 font-medium">Linked</span>
                  ) : (
                    <span className="text-amber-500 font-medium">Unlinked</span>
                  )}
                </div>

                <div
                  className="px-2 py-1 rounded-lg bg-background border border-border/40 font-mono text-[10px] text-foreground truncate cursor-help"
                  title={selectedProject.root_path || 'No local directory linked to project'}
                >
                  {selectedProject.root_path || (
                    <span className="text-muted-foreground italic">No folder chosen</span>
                  )}
                </div>

                <div className="flex items-center gap-1.5 pt-0.5">
                  <button
                    type="button"
                    onClick={handleChangeFolder}
                    disabled={isUpdatingFolder}
                    className="flex-1 py-1 px-2 text-[10px] font-medium rounded-lg border border-border bg-card hover:bg-muted text-foreground transition-colors cursor-pointer flex items-center justify-center gap-1 truncate shadow-xs disabled:opacity-50"
                    title={isTauri() ? 'Choose directory via native picker' : 'Native picker available in desktop app'}
                  >
                    {isUpdatingFolder ? (
                      <Loader2 className="h-3 w-3 animate-spin shrink-0" />
                    ) : (
                      <FolderOpen className="h-3 w-3 shrink-0 text-muted-foreground" />
                    )}
                    <span>{selectedProject.root_path ? 'Change Folder' : 'Choose Folder'}</span>
                  </button>

                  {selectedProject.root_path && (
                    <button
                      type="button"
                      onClick={handleIngestDirectory}
                      disabled={isIngesting}
                      className="py-1 px-2 text-[10px] font-medium rounded-lg bg-primary/10 hover:bg-primary/20 text-primary border border-primary/20 transition-colors cursor-pointer flex items-center gap-1 shrink-0 shadow-xs disabled:opacity-50"
                      title="Ingest supported project files into vector knowledge base"
                    >
                      {isIngesting ? (
                        <Loader2 className="h-3 w-3 animate-spin shrink-0" />
                      ) : (
                        <RefreshCw className="h-3 w-3 shrink-0" />
                      )}
                      <span>Ingest</span>
                    </button>
                  )}
                </div>

                {folderStatus && (
                  <p className="text-[9px] text-muted-foreground leading-tight pt-0.5 break-words">
                    {folderStatus}
                  </p>
                )}
              </div>
            )}
          </div>

          {/* Knowledge Section */}
          <div className="space-y-1">
            {isOpen && (
              <span className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground/70 px-2 block">
                Knowledge
              </span>
            )}
            <div
              className={`w-full flex items-center justify-between px-2.5 py-1.5 rounded-lg text-xs font-medium text-muted-foreground ${
                !isOpen ? 'justify-center' : ''
              }`}
              title={
                selectedProject
                  ? `Knowledge Base: ${activeProjectKnowledgeCount} sources indexed`
                  : 'Knowledge Base: Select a project'
              }
            >
              <div className="flex items-center gap-2.5">
                <BookOpen className="h-4 w-4 shrink-0" />
                {isOpen && <span>Knowledge Base</span>}
              </div>
              {isOpen && (
                <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-muted/60 text-muted-foreground">
                  {selectedProject ? activeProjectKnowledgeCount : '—'}
                </span>
              )}
            </div>
          </div>

          {/* Project Memory Section */}
          <div className="space-y-1">
            {isOpen && (
              <span className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground/70 px-2 block">
                Memory
              </span>
            )}
            <div
              className={`w-full flex items-center justify-between px-2.5 py-1.5 rounded-lg text-xs font-medium text-muted-foreground ${
                !isOpen ? 'justify-center' : ''
              }`}
              title={
                selectedProject
                  ? `Project Memory: ${activeProjectMemoryCount} active items`
                  : 'Project Memory: Select a project'
              }
            >
              <div className="flex items-center gap-2.5">
                <Brain className="h-4 w-4 shrink-0" />
                {isOpen && <span>Project Memory</span>}
              </div>
              {isOpen && (
                <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-muted/60 text-muted-foreground">
                  {selectedProject ? activeProjectMemoryCount : '—'}
                </span>
              )}
            </div>
          </div>

          {/* Local Engine Status Box */}
          {isOpen && (
            <div className="p-3 rounded-xl border border-border/80 bg-card shadow-2xs space-y-1.5 text-xs font-mono">
              <div className="flex items-center justify-between text-[10px] text-muted-foreground">
                <span className="flex items-center gap-1.5">
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
          )}
        </div>

        {/* Bottom User Profile */}
        <div className="p-3 border-t border-sidebar-border bg-sidebar/90">
          {isOpen ? (
            <div className="flex items-center gap-2.5">
              {user?.imageUrl ? (
                <img
                  src={user.imageUrl}
                  alt={user.fullName || 'User'}
                  className="h-7 w-7 rounded-full object-cover border border-border shrink-0"
                  referrerPolicy="no-referrer"
                />
              ) : (
                <div className="h-7 w-7 rounded-full bg-primary/10 text-primary flex items-center justify-center font-bold text-xs shrink-0">
                  {(user?.firstName?.[0] || 'U').toUpperCase()}
                </div>
              )}
              <div className="flex flex-col min-w-0 text-left">
                <span className="text-xs font-semibold text-foreground truncate">
                  {user?.fullName || user?.firstName || 'Developer'}
                </span>
                <span className="text-[10px] font-mono text-muted-foreground truncate">
                  {user?.primaryEmailAddress?.emailAddress || 'Local Developer'}
                </span>
              </div>
            </div>
          ) : (
            <div className="flex justify-center">
              {user?.imageUrl ? (
                <img
                  src={user.imageUrl}
                  alt={user.fullName || 'User'}
                  className="h-7 w-7 rounded-full object-cover border border-border"
                  referrerPolicy="no-referrer"
                />
              ) : (
                <div className="h-7 w-7 rounded-full bg-primary/10 text-primary flex items-center justify-center font-bold text-xs">
                  {(user?.firstName?.[0] || 'U').toUpperCase()}
                </div>
              )}
            </div>
          )}
        </div>
      </aside>
    </>
  );
};
