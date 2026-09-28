import { useState, useEffect, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth, useUser } from '@clerk/react';
import {
  Bot,
  AlertTriangle,
  RotateCcw,
  Sparkles,
  Clock,
  WifiOff,
} from 'lucide-react';

import { TopBar } from '@/components/studio/TopBar';
import { Sidebar } from '@/components/studio/Sidebar';
import { Composer } from '@/components/studio/Composer';
import { CompiledPromptCard } from '@/components/studio/CompiledPromptCard';
import { MetadataAccordion } from '@/components/studio/MetadataAccordion';
import { PipelineProgress } from '@/components/studio/PipelineProgress';
import { NewProjectModal } from '@/components/studio/NewProjectModal';
import { InterviewSessionCard } from '@/components/studio/InterviewSessionCard';

import {
  compilePrompt,
  startInterview,
  submitInterviewAnswers,
  compileFromInterview,
  getAgentPresets,
  getProjects,
  deleteProject,
  getHealth,
  getProjectMemories,
  getKnowledgeSources,
  ApiError,
} from '@/api';

import type {
  Project,
  AgentPreset,
  CompileResponse,
  InterviewSessionResponse,
  InterviewAnswer,
} from '@/types/api';

export function StudioView() {
  const navigate = useNavigate();
  const { isLoaded, isSignedIn } = useAuth();
  const { user } = useUser();
  const displayName = user?.firstName || user?.username || (user?.fullName ? user.fullName.split(' ')[0] : 'there');

  // Core Studio State
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null);
  const [presets, setPresets] = useState<AgentPreset[]>([]);
  const [targetAgent, setTargetAgent] = useState<string>('cursor');
  const [enableKnowledge, setEnableKnowledge] = useState<boolean>(true);
  const [interviewMode, setInterviewMode] = useState<boolean>(false);

  // Composer & Execution State
  const [input, setInput] = useState<string>('');
  const [isCompiling, setIsCompiling] = useState<boolean>(false);
  const [isPipelineComplete, setIsPipelineComplete] = useState<boolean>(false);
  const [result, setResult] = useState<CompileResponse | null>(null);
  const [compiledAt, setCompiledAt] = useState<string>('');
  const [activeInterviewSession, setActiveInterviewSession] = useState<InterviewSessionResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [submittedPrompt, setSubmittedPrompt] = useState<string>('');

  // UI & Infrastructure State
  const [isBackendHealthy, setIsBackendHealthy] = useState<boolean>(true);
  const [isSidebarOpen, setIsSidebarOpen] = useState<boolean>(true);
  const [isNewProjectModalOpen, setIsNewProjectModalOpen] = useState<boolean>(false);
  const [projectMemoryCount, setProjectMemoryCount] = useState<number>(0);
  const [projectKnowledgeCount, setProjectKnowledgeCount] = useState<number>(0);
  const [isOnline, setIsOnline] = useState<boolean>(
    typeof navigator !== 'undefined' ? navigator.onLine : true
  );
  const [loadTimedOut, setLoadTimedOut] = useState<boolean>(false);

  const scrollContainerRef = useRef<HTMLDivElement>(null);

  // Network online/offline monitoring
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

  // Bounded timeout for Clerk auth readiness
  useEffect(() => {
    if (isLoaded) return;
    const timer = setTimeout(() => {
      setLoadTimedOut(true);
    }, 6000);
    return () => clearTimeout(timer);
  }, [isLoaded]);

  // Load backend data (presets, projects, health)
  const loadInitialData = useCallback(async () => {
    try {
      // 1. Health
      try {
        const health = await getHealth();
        setIsBackendHealthy(health.status === 'ok');
      } catch {
        setIsBackendHealthy(false);
      }

      // 2. Presets
      try {
        const agentPresets = await getAgentPresets();
        setPresets(agentPresets);
        if (agentPresets.length > 0 && !agentPresets.some((p) => p.id === targetAgent)) {
          setTargetAgent(agentPresets[0].id);
        }
      } catch (err) {
        console.warn('Could not load presets from backend:', err);
      }

      // 3. Projects
      try {
        const projectList = await getProjects(50, 0);
        setProjects(projectList);
      } catch (err) {
        console.warn('Could not load projects from backend:', err);
      }
    } catch {
      // general error
    }
  }, [targetAgent]);

  // Periodic health check of local engine
  useEffect(() => {
    const checkHealth = async () => {
      try {
        const health = await getHealth();
        setIsBackendHealthy(health.status === 'ok');
      } catch {
        setIsBackendHealthy(false);
      }
    };
    const interval = setInterval(checkHealth, 5000);
    return () => clearInterval(interval);
  }, []);

  // Listen for backend-ready events (e.g. from Tauri sidecar or port probing)
  useEffect(() => {
    const handleBackendReady = () => {
      setIsBackendHealthy(true);
      void loadInitialData();
    };
    window.addEventListener('prompt-compiler:backend-ready', handleBackendReady);
    return () => {
      window.removeEventListener('prompt-compiler:backend-ready', handleBackendReady);
    };
  }, [loadInitialData]);

  // Listen for backend 401 Unauthorized / session expiration events
  useEffect(() => {
    const handleAuthRequired = (e: Event) => {
      const customEvent = e as CustomEvent<{ status: number; message: string }>;
      setError(customEvent.detail?.message || 'Authentication required or session expired. Please sign in again.');
    };
    window.addEventListener('prompt-compiler:auth-required', handleAuthRequired);
    return () => {
      window.removeEventListener('prompt-compiler:auth-required', handleAuthRequired);
    };
  }, []);

  // Authentication check
  useEffect(() => {
    if (isLoaded && !isSignedIn) {
      navigate('/auth', { replace: true });
    }
  }, [isLoaded, isSignedIn, navigate]);

  useEffect(() => {
    let isMounted = true;
    if (isLoaded && isSignedIn) {
      void (async () => {
        if (isMounted) {
          await loadInitialData();
        }
      })();
    }
    return () => {
      isMounted = false;
    };
  }, [isLoaded, isSignedIn, loadInitialData]);

  // Update memory and knowledge count when selected project changes
  useEffect(() => {
    let isCurrent = true;
    if (!selectedProjectId) {
      void Promise.resolve().then(() => {
        if (isCurrent) {
          setProjectMemoryCount(0);
          setProjectKnowledgeCount(0);
        }
      });
      return () => {
        isCurrent = false;
      };
    }

    getProjectMemories(selectedProjectId)
      .then((mems) => {
        if (isCurrent) setProjectMemoryCount(mems.length);
      })
      .catch(() => {
        if (isCurrent) setProjectMemoryCount(0);
      });

    getKnowledgeSources(selectedProjectId)
      .then((srcs) => {
        if (isCurrent) setProjectKnowledgeCount(srcs.length);
      })
      .catch(() => {
        if (isCurrent) setProjectKnowledgeCount(0);
      });

    return () => {
      isCurrent = false;
    };
  }, [selectedProjectId]);

  // Auto-scroll to bottom of workspace when compilation completes
  useEffect(() => {
    if (result && scrollContainerRef.current) {
      setTimeout(() => {
        scrollContainerRef.current?.scrollTo({
          top: scrollContainerRef.current.scrollHeight,
          behavior: 'smooth',
        });
      }, 100);
    }
  }, [result]);

  // Handle compilation submission
  const handleCompile = async () => {
    const trimmedInput = input.trim();
    if (!trimmedInput || isCompiling) return;

    setError(null);
    setIsCompiling(true);
    setIsPipelineComplete(false);
    setSubmittedPrompt(trimmedInput);
    setActiveInterviewSession(null);

    try {
      if (interviewMode) {
        // Start interview clarification session via POST /api/interview/start
        const session = await startInterview({
          input: trimmedInput,
          project_id: selectedProjectId,
          target_agent: targetAgent,
          enable_knowledge_retrieval: enableKnowledge,
        });

        if (session.status === 'ready' || !session.questions || session.questions.length === 0) {
          // If no questions are needed, compile directly from the interview session
          const response = await compileFromInterview(session.session_id);
          setIsPipelineComplete(true);
          await new Promise((resolve) => setTimeout(resolve, 350));
          setResult(response);
          setCompiledAt(new Date().toLocaleTimeString());
          setInput('');
        } else {
          // Questions require clarification by user
          setActiveInterviewSession(session);
        }
      } else {
        const response = await compilePrompt({
          input: trimmedInput,
          project_id: selectedProjectId,
          target_agent: targetAgent,
          enable_knowledge_retrieval: enableKnowledge,
        });

        // Mark visual pipeline complete briefly, then transition to compiled prompt card
        setIsPipelineComplete(true);
        await new Promise((resolve) => setTimeout(resolve, 350));
        setResult(response);
        setCompiledAt(new Date().toLocaleTimeString());
        setInput(''); // Clear input for next instruction
      }
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else if (err instanceof Error) {
        setError(err.message);
      } else {
        setError('An unexpected error occurred during prompt compilation.');
      }
    } finally {
      setIsCompiling(false);
      setIsPipelineComplete(false);
    }
  };

  const handleSubmitInterviewAnswers = async (answers: InterviewAnswer[]) => {
    if (!activeInterviewSession) return;

    setError(null);
    setIsCompiling(true);

    try {
      const updatedSession = await submitInterviewAnswers(
        activeInterviewSession.session_id,
        { answers }
      );

      if (
        updatedSession.status === 'ready' ||
        !updatedSession.questions ||
        updatedSession.questions.length === 0
      ) {
        // All questions clarified! Compile final prompt
        const response = await compileFromInterview(updatedSession.session_id);
        setIsPipelineComplete(true);
        await new Promise((resolve) => setTimeout(resolve, 350));
        setResult(response);
        setCompiledAt(new Date().toLocaleTimeString());
        setActiveInterviewSession(null);
        setInput('');
      } else {
        // Advance to next turn questions
        setActiveInterviewSession(updatedSession);
      }
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else if (err instanceof Error) {
        setError(err.message);
      } else {
        setError('Failed to submit interview answers. Please try again.');
      }
    } finally {
      setIsCompiling(false);
      setIsPipelineComplete(false);
    }
  };

  const handleSkipInterviewAndCompile = async () => {
    if (!activeInterviewSession) return;

    setError(null);
    setIsCompiling(true);

    try {
      const response = await compileFromInterview(activeInterviewSession.session_id);
      setIsPipelineComplete(true);
      await new Promise((resolve) => setTimeout(resolve, 350));
      setResult(response);
      setCompiledAt(new Date().toLocaleTimeString());
      setActiveInterviewSession(null);
      setInput('');
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else if (err instanceof Error) {
        setError(err.message);
      } else {
        setError('Failed to compile prompt from interview session.');
      }
    } finally {
      setIsCompiling(false);
      setIsPipelineComplete(false);
    }
  };

  const handleCancelInterview = () => {
    setActiveInterviewSession(null);
    setError(null);
    setIsCompiling(false);
  };

  const handleNewCompilation = () => {
    setResult(null);
    setCompiledAt('');
    setActiveInterviewSession(null);
    setError(null);
    setIsCompiling(false);
    setIsPipelineComplete(false);
    setInput('');
    setSubmittedPrompt('');
  };

  const handleProjectCreated = (newProject: Project) => {
    setProjects((prev) => [newProject, ...prev]);
    setSelectedProjectId(newProject.project_id);
  };

  const handleUpdateProject = (updated: Project) => {
    setProjects((prev) =>
      prev.map((p) => (p.project_id === updated.project_id ? updated : p))
    );
  };

  const handleDeleteProject = useCallback(
    async (projectId: string) => {
      try {
        await deleteProject(projectId);
        setProjects((prev) => prev.filter((p) => p.project_id !== projectId));
        if (selectedProjectId === projectId) {
          setSelectedProjectId(null);
        }
      } catch (err: unknown) {
        setError(err instanceof Error ? err.message : 'Failed to delete project');
      }
    },
    [selectedProjectId]
  );

  const handleRefreshKnowledge = useCallback(async () => {
    if (!selectedProjectId) return;
    try {
      const srcs = await getKnowledgeSources(selectedProjectId);
      setProjectKnowledgeCount(srcs.length);
    } catch {
      // ignore
    }
  }, [selectedProjectId]);

  // If loading took too long or offline while trying to initialize Clerk
  if (!isLoaded && (loadTimedOut || !isOnline)) {
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
                ? 'Unable to connect to Clerk authentication services while offline. Please connect to the internet to refresh your session.'
                : 'Verifying your session with Clerk timed out. Please check your network connection and try again.'}
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
              onClick={() => navigate('/auth')}
              className="flex items-center justify-center gap-1.5 px-4 py-2.5 rounded-xl border border-border text-foreground font-semibold text-xs hover:bg-muted transition-colors cursor-pointer"
            >
              <span>Sign In</span>
            </button>
          </div>
        </div>
      </div>
    );
  }

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
    return null;
  }

  const selectedProject = projects.find((p) => p.project_id === selectedProjectId) || null;

  return (
    <div className="h-screen w-full flex bg-background text-foreground overflow-hidden selection:bg-neutral-800 selection:text-white dark:selection:bg-white dark:selection:text-black">
      {/* Left Collapsible Sidebar (Extends to the very top!) */}
      <Sidebar
        isOpen={isSidebarOpen}
        onToggle={() => setIsSidebarOpen((prev) => !prev)}
        onNewCompilation={handleNewCompilation}
        projects={projects}
        selectedProjectId={selectedProjectId}
        onSelectProject={setSelectedProjectId}
        onOpenNewProject={() => setIsNewProjectModalOpen(true)}
        isBackendHealthy={isBackendHealthy}
        activeProjectMemoryCount={projectMemoryCount}
        activeProjectKnowledgeCount={projectKnowledgeCount}
        onUpdateProject={handleUpdateProject}
        onDeleteProject={handleDeleteProject}
        onRefreshKnowledge={handleRefreshKnowledge}
      />

      {/* Right Column: TopBar + Workspace */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden relative">
        {/* Top Application Header */}
        <TopBar
          isBackendHealthy={isBackendHealthy}
          onToggleSidebar={() => setIsSidebarOpen((prev) => !prev)}
          isOnline={isOnline}
        />

        {/* Center Main Workspace */}
        <main
          ref={scrollContainerRef}
          className="flex-1 overflow-y-auto flex flex-col justify-between relative bg-background"
        >
          {/* Background Grid Accent */}
          <div
            className="absolute inset-0 bg-grid-pattern opacity-30 pointer-events-none"
            aria-hidden="true"
          />

          {/* Main Content Area */}
          <div className="relative z-10 w-full max-w-4xl mx-auto px-4 py-8 sm:px-8 flex-1 flex flex-col">
            {/* Case A: Active Interview Session */}
            {activeInterviewSession && !isCompiling && (
              <div className="flex-1 flex flex-col justify-center my-auto">
                <InterviewSessionCard
                  session={activeInterviewSession}
                  originalInput={submittedPrompt || input}
                  isSubmitting={isCompiling}
                  onSubmitAnswers={handleSubmitInterviewAnswers}
                  onSkipAndCompile={handleSkipInterviewAndCompile}
                  onCancel={handleCancelInterview}
                />
              </div>
            )}

            {/* Case B: Empty State (No prompt submitted yet and no active interview) */}
            {!result && !activeInterviewSession && !isCompiling && (
              <div className="flex-1 flex flex-col items-center justify-center text-center my-auto animate-in fade-in duration-300">
                {/* Personalized Greeting */}
                <h1 className="text-3xl sm:text-5xl font-extrabold tracking-tight text-foreground max-w-2xl leading-[1.15] mb-8">
                  Hi, {displayName}!!
                </h1>

                {/* Empty State Composer with Quick Action Chips */}
                <Composer
                  input={input}
                  onChangeInput={setInput}
                  onSubmit={handleCompile}
                  isCompiling={isCompiling}
                  selectedProjectId={selectedProjectId}
                  onSelectProject={setSelectedProjectId}
                  projects={projects}
                  onOpenNewProject={() => setIsNewProjectModalOpen(true)}
                  targetAgent={targetAgent}
                  onSelectTargetAgent={setTargetAgent}
                  presets={presets}
                  enableKnowledge={enableKnowledge}
                  onToggleKnowledge={() => setEnableKnowledge((prev) => !prev)}
                  interviewMode={interviewMode}
                  onToggleInterviewMode={() => setInterviewMode((prev) => !prev)}
                  showQuickActions={true}
                />
              </div>
            )}

            {/* Case B: Loading State */}
            {isCompiling && (
              <div className="flex-1 flex flex-col items-center justify-center my-auto">
                <PipelineProgress
                  targetAgent={targetAgent}
                  hasKnowledge={enableKnowledge}
                  hasProject={selectedProjectId !== null}
                  isComplete={isPipelineComplete}
                />
              </div>
            )}

            {/* Case C: Error State Banner */}
            {error && !isCompiling && (
              <div className="mb-6 p-4 rounded-2xl border border-red-500/30 bg-red-500/10 text-red-600 dark:text-red-400 text-xs flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 animate-in fade-in duration-200">
                <div className="flex items-start gap-2.5">
                  <AlertTriangle className="h-4 w-4 mt-0.5 shrink-0" />
                  <div>
                    <span className="font-bold block mb-0.5">Compilation Failure</span>
                    <span>{error}</span>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={handleCompile}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-red-600 text-white font-semibold text-xs hover:bg-red-700 transition-colors shrink-0 cursor-pointer shadow-xs"
                >
                  <RotateCcw className="h-3.5 w-3.5" />
                  <span>Retry</span>
                </button>
              </div>
            )}

            {/* Case D: Active Result State */}
            {result && !isCompiling && (
              <div className="space-y-6 pb-6 animate-in fade-in duration-300">
                {/* User Request Card */}
                <div className="p-4 sm:p-5 rounded-2xl border border-border/80 bg-card/60 backdrop-blur-md shadow-xs text-left">
                  <div className="flex items-center justify-between pb-2 border-b border-border/30 text-xs font-mono text-muted-foreground">
                    <div className="flex items-center gap-2">
                      <span className="h-2 w-2 rounded-full bg-primary" />
                      <span className="font-bold text-foreground uppercase tracking-wider">
                        Original Requirement
                      </span>
                    </div>
                    <div className="flex items-center gap-1.5 text-[11px]">
                      <Clock className="h-3 w-3" />
                      <span>{compiledAt || 'Just now'}</span>
                    </div>
                  </div>
                  <p className="mt-3 text-sm text-foreground/90 font-mono leading-relaxed whitespace-pre-wrap">
                    {submittedPrompt || result.input}
                  </p>
                </div>

                {/* Pipeline Summary Bar */}
                <div className="flex flex-wrap items-center justify-between gap-2 px-4 py-2.5 rounded-xl border border-border/60 bg-muted/30 text-xs font-mono">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="flex items-center gap-1.5 text-foreground font-semibold">
                      <Bot className="h-3.5 w-3.5 text-primary" />
                      <span>{(result.target_agent || targetAgent || 'generic').toUpperCase()}</span>
                    </span>
                    <span className="text-muted-foreground/40">•</span>
                    {result.task_type && (
                      <span className="text-muted-foreground">
                        Task: <strong className="text-foreground">{result.task_type}</strong>
                      </span>
                    )}
                    {selectedProject && (
                      <>
                        <span className="text-muted-foreground/40">•</span>
                        <span className="text-muted-foreground">
                          Project: <strong className="text-foreground">{selectedProject.name}</strong>
                        </span>
                      </>
                    )}
                  </div>

                  <div className="flex items-center gap-2 text-[11px] text-muted-foreground">
                    {(result.knowledge_references?.length ?? 0) > 0 ? (
                      <span className="text-emerald-500 font-semibold">
                        {result.knowledge_references?.length ?? 0} Knowledge Sources Used
                      </span>
                    ) : (
                      <span>No RAG Injected</span>
                    )}
                    {(result.refinement_attempts ?? 0) > 0 && (
                      <>
                        <span>•</span>
                        <span className="text-amber-500 font-semibold flex items-center gap-1">
                          <Sparkles className="h-3 w-3" />
                          {result.refinement_attempts} Refined
                        </span>
                      </>
                    )}
                  </div>
                </div>

                {/* Requirement / Context Visibility Accordion */}
                <MetadataAccordion
                  requirements={result.requirements}
                  validation={result.validation}
                  knowledgeReferences={result.knowledge_references ?? []}
                  refinementAttempts={result.refinement_attempts ?? 0}
                />

                {/* Compiled Prompt Output Card */}
                <CompiledPromptCard
                  prompt={result.result || ''}
                  targetAgent={result.target_agent || targetAgent || 'generic'}
                  taskType={result.task_type}
                  templateName={result.template_name}
                  refinementAttempts={result.refinement_attempts ?? 0}
                />
              </div>
            )}
          </div>

          {/* Bottom Anchored Composer (when result is present) */}
          {result && !isCompiling && (
            <div className="sticky bottom-0 z-20 w-full bg-gradient-to-t from-background via-background/95 to-transparent pt-4 pb-6 px-4 sm:px-8 border-t border-border/40 backdrop-blur-md">
              <Composer
                input={input}
                onChangeInput={setInput}
                onSubmit={handleCompile}
                isCompiling={isCompiling}
                selectedProjectId={selectedProjectId}
                onSelectProject={setSelectedProjectId}
                projects={projects}
                onOpenNewProject={() => setIsNewProjectModalOpen(true)}
                targetAgent={targetAgent}
                onSelectTargetAgent={setTargetAgent}
                presets={presets}
                enableKnowledge={enableKnowledge}
                onToggleKnowledge={() => setEnableKnowledge((prev) => !prev)}
                interviewMode={interviewMode}
                onToggleInterviewMode={() => setInterviewMode((prev) => !prev)}
                showQuickActions={false}
              />
            </div>
          )}
        </main>
      </div>

      {/* New Project Modal */}
      <NewProjectModal
        isOpen={isNewProjectModalOpen}
        onClose={() => setIsNewProjectModalOpen(false)}
        onProjectCreated={handleProjectCreated}
      />
    </div>
  );
}

export default StudioView;
