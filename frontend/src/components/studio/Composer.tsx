import React, { useRef, useEffect } from 'react';
import {
  ArrowUp,
  Paperclip,
  BookOpen,
  ChevronDown,
  Sparkles,
  HelpCircle,
  Plus,
  Loader2,
  FolderKanban,
  Bot,
} from 'lucide-react';
import type { Project, AgentPreset } from '@/types/api';

interface ComposerProps {
  input: string;
  onChangeInput: (val: string) => void;
  onSubmit: () => void;
  isCompiling: boolean;
  selectedProjectId: string | null;
  onSelectProject: (projectId: string | null) => void;
  projects: Project[];
  onOpenNewProject: () => void;
  targetAgent: string;
  onSelectTargetAgent: (agentId: string) => void;
  presets: AgentPreset[];
  enableKnowledge: boolean;
  onToggleKnowledge: () => void;
  interviewMode: boolean;
  onToggleInterviewMode: () => void;
  showQuickActions?: boolean;
}

const QUICK_ACTIONS = [
  { label: 'Build a Feature', starter: 'Build a feature that ' },
  { label: 'Modify Existing Code', starter: 'Modify the existing code to ' },
  { label: 'Debug an Issue', starter: 'Debug an issue where ' },
  { label: 'Analyze Architecture', starter: 'Analyze the architecture of ' },
  { label: 'Explain Code', starter: 'Explain how the implementation of ' },
];

export const Composer: React.FC<ComposerProps> = ({
  input,
  onChangeInput,
  onSubmit,
  isCompiling,
  selectedProjectId,
  onSelectProject,
  projects,
  onOpenNewProject,
  targetAgent,
  onSelectTargetAgent,
  presets,
  enableKnowledge,
  onToggleKnowledge,
  interviewMode,
  onToggleInterviewMode,
  showQuickActions = false,
}) => {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const [isAgentMenuOpen, setIsAgentMenuOpen] = React.useState(false);
  const [isProjectMenuOpen, setIsProjectMenuOpen] = React.useState(false);

  // Auto-resize textarea between 80px and 220px
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = 'auto';
    const newHeight = Math.min(Math.max(el.scrollHeight, 80), 220);
    el.style.height = `${newHeight}px`;
  }, [input]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (input.trim() && !isCompiling) {
        onSubmit();
      }
    }
  };

  const selectedProject = projects.find((p) => p.project_id === selectedProjectId);
  const selectedPreset = presets.find((p) => p.id === targetAgent) || {
    id: targetAgent,
    name: targetAgent.replace('_', ' ').replace(/\b\w/g, (c) => c.toUpperCase()),
  };

  return (
    <div className="w-full max-w-3xl mx-auto flex flex-col gap-3">
      {/* Quick Action Chips (rendered in empty state) */}
      {showQuickActions && (
        <div className="flex flex-wrap items-center justify-center gap-2 px-2 animate-in fade-in duration-300">
          {QUICK_ACTIONS.map((action) => (
            <button
              key={action.label}
              type="button"
              onClick={() => {
                onChangeInput(action.starter);
                textareaRef.current?.focus();
              }}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium border border-border/80 bg-card text-foreground/90 hover:text-foreground hover:bg-secondary hover:border-primary/40 transition-all cursor-pointer shadow-2xs hover:shadow-xs active:scale-95"
            >
              <Sparkles className="h-3 w-3 text-primary" />
              <span>{action.label}</span>
            </button>
          ))}
        </div>
      )}

      {/* Main Composer Box */}
      <div className="relative rounded-2xl border border-border/90 bg-card shadow-xl shadow-slate-200/50 dark:shadow-2xl dark:shadow-black/70 transition-all duration-200 focus-within:border-primary/50 focus-within:ring-2 focus-within:ring-primary/20">
        {/* Textarea */}
        <textarea
          ref={textareaRef}
          value={input}
          onChange={(e) => onChangeInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Describe what you want to build..."
          rows={3}
          disabled={isCompiling}
          className="w-full resize-none bg-transparent px-4 pt-3.5 pb-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none leading-relaxed min-h-[80px] max-h-[220px]"
        />

        {/* Toolbar */}
        <div className="flex flex-wrap items-center justify-between gap-2 px-3 py-2.5 border-t border-border/70 bg-toolbar rounded-b-2xl">
          {/* Left Controls */}
          <div className="flex items-center gap-1.5">
            {/* Attach button */}
            <button
              type="button"
              title="Project document ingestion (supported: .md, .txt, .py, .ts, .json)"
              onClick={() => {
                // Informative note on project attachment
                alert(
                  selectedProject
                    ? `Project Ingestion: Files under project root are automatically indexed into vector knowledge.`
                    : `Please select a project to enable local repository file ingestion.`
                );
              }}
              className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium text-muted-foreground hover:text-foreground hover:bg-card hover:shadow-2xs transition-all cursor-pointer"
            >
              <Paperclip className="h-3.5 w-3.5" />
              <span className="hidden sm:inline">Attach</span>
            </button>

            {/* Interview Mode Toggle */}
            <button
              type="button"
              onClick={onToggleInterviewMode}
              title="Optional multi-turn clarification interview mode"
              className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium transition-all cursor-pointer border ${
                interviewMode
                  ? 'bg-amber-500/15 text-amber-500 border-amber-500/40 font-semibold shadow-2xs'
                  : 'text-muted-foreground hover:text-foreground border-border/70 bg-card hover:bg-secondary shadow-2xs'
              }`}
            >
              <HelpCircle className="h-3.5 w-3.5" />
              <span className="hidden md:inline">Interview Mode</span>
            </button>
          </div>

          {/* Right Controls */}
          <div className="flex items-center gap-1.5 sm:gap-2">
            {/* Project Selector Dropdown */}
            <div className="relative">
              <button
                type="button"
                onClick={() => {
                  setIsProjectMenuOpen((prev) => !prev);
                  setIsAgentMenuOpen(false);
                }}
                className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium border border-border/80 bg-card hover:bg-secondary text-foreground transition-all cursor-pointer max-w-[140px] sm:max-w-[180px] shadow-2xs"
              >
                <FolderKanban className="h-3.5 w-3.5 text-primary shrink-0" />
                <span className="truncate">
                  {selectedProject ? selectedProject.name : 'No Project'}
                </span>
                <ChevronDown className="h-3 w-3 text-muted-foreground shrink-0" />
              </button>

              {isProjectMenuOpen && (
                <>
                  <div
                    className="fixed inset-0 z-30"
                    onClick={() => setIsProjectMenuOpen(false)}
                  />
                  <div className="absolute right-0 bottom-full mb-2 w-56 rounded-xl border border-border bg-card p-1.5 shadow-xl z-40 animate-in fade-in duration-100 max-h-60 overflow-y-auto">
                    <button
                      type="button"
                      onClick={() => {
                        onSelectProject(null);
                        setIsProjectMenuOpen(false);
                      }}
                      className={`w-full flex items-center justify-between px-2.5 py-1.5 rounded-lg text-xs font-medium transition-colors cursor-pointer ${
                        selectedProjectId === null
                          ? 'bg-primary/10 text-primary'
                          : 'text-foreground hover:bg-muted'
                      }`}
                    >
                      <span>No Project (Global)</span>
                    </button>

                    {projects.map((proj) => (
                      <button
                        key={proj.project_id}
                        type="button"
                        onClick={() => {
                          onSelectProject(proj.project_id);
                          setIsProjectMenuOpen(false);
                        }}
                        className={`w-full flex items-center justify-between px-2.5 py-1.5 rounded-lg text-xs font-medium transition-colors cursor-pointer ${
                          selectedProjectId === proj.project_id
                            ? 'bg-primary/10 text-primary'
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
                          setIsProjectMenuOpen(false);
                          onOpenNewProject();
                        }}
                        className="w-full flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-semibold text-primary hover:bg-primary/10 transition-colors cursor-pointer"
                      >
                        <Plus className="h-3.5 w-3.5" />
                        <span>Create Project</span>
                      </button>
                    </div>
                  </div>
                </>
              )}
            </div>

            {/* Target Agent Preset Selector */}
            <div className="relative">
              <button
                type="button"
                onClick={() => {
                  setIsAgentMenuOpen((prev) => !prev);
                  setIsProjectMenuOpen(false);
                }}
                className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium border border-border/80 bg-card hover:bg-secondary text-foreground transition-all cursor-pointer shadow-2xs"
              >
                <Bot className="h-3.5 w-3.5 text-primary shrink-0" />
                <span className="truncate">{selectedPreset.name}</span>
                <ChevronDown className="h-3 w-3 text-muted-foreground shrink-0" />
              </button>

              {isAgentMenuOpen && (
                <>
                  <div
                    className="fixed inset-0 z-30"
                    onClick={() => setIsAgentMenuOpen(false)}
                  />
                  <div className="absolute right-0 bottom-full mb-2 w-52 rounded-xl border border-border bg-card p-1.5 shadow-xl z-40 animate-in fade-in duration-100">
                    {presets.length > 0 ? (
                      presets.map((preset) => (
                        <button
                          key={preset.id}
                          type="button"
                          onClick={() => {
                            onSelectTargetAgent(preset.id);
                            setIsAgentMenuOpen(false);
                          }}
                          className={`w-full flex items-center justify-between px-2.5 py-1.5 rounded-lg text-xs font-medium transition-colors cursor-pointer ${
                            targetAgent === preset.id
                              ? 'bg-primary/10 text-primary font-semibold'
                              : 'text-foreground hover:bg-muted'
                          }`}
                        >
                          <span>{preset.name}</span>
                        </button>
                      ))
                    ) : (
                      ['cursor', 'claude_code', 'cline', 'windsurf', 'generic'].map((id) => (
                        <button
                          key={id}
                          type="button"
                          onClick={() => {
                            onSelectTargetAgent(id);
                            setIsAgentMenuOpen(false);
                          }}
                          className={`w-full flex items-center justify-between px-2.5 py-1.5 rounded-lg text-xs font-medium transition-colors cursor-pointer ${
                            targetAgent === id
                              ? 'bg-primary/10 text-primary'
                              : 'text-foreground hover:bg-muted'
                          }`}
                        >
                          <span className="capitalize">{id.replace('_', ' ')}</span>
                        </button>
                      ))
                    )}
                  </div>
                </>
              )}
            </div>

            {/* Knowledge Toggle Chip */}
            <button
              type="button"
              onClick={onToggleKnowledge}
              title={
                enableKnowledge
                  ? 'Semantic Knowledge Retrieval Enabled'
                  : 'Semantic Knowledge Retrieval Disabled'
              }
              className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium transition-all cursor-pointer border ${
                enableKnowledge
                  ? 'bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border-emerald-500/40 shadow-2xs font-semibold'
                  : 'text-muted-foreground hover:text-foreground border-border/80 bg-card hover:bg-secondary shadow-2xs'
              }`}
            >
              <BookOpen className="h-3.5 w-3.5" />
              <span className="hidden sm:inline">Knowledge</span>
            </button>

            {/* Send / Compile Button */}
            <button
              type="button"
              disabled={isCompiling || !input.trim()}
              onClick={onSubmit}
              className="flex items-center justify-center h-8 w-8 sm:h-8.5 sm:w-8.5 rounded-xl bg-neutral-900 text-white dark:bg-white dark:text-neutral-950 font-bold transition-all duration-200 hover:scale-105 active:scale-95 disabled:opacity-30 disabled:scale-100 disabled:cursor-not-allowed shadow-md cursor-pointer shrink-0"
              title="Compile Prompt (Enter)"
            >
              {isCompiling ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <ArrowUp className="h-4 w-4 stroke-[2.5]" />
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
