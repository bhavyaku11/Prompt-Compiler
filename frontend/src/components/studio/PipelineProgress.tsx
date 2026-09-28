import React, { useEffect, useState } from 'react';
import { Terminal, CheckCircle2, Loader2, Sparkles } from 'lucide-react';

interface PipelineProgressProps {
  targetAgent: string;
  hasKnowledge: boolean;
  hasProject: boolean;
  isComplete?: boolean;
}

const PIPELINE_STAGES = [
  { id: 'req', label: 'Requirement Analysis & Intent Extraction' },
  { id: 'rag', label: 'Semantic Context & Knowledge Retrieval' },
  { id: 'synth', label: 'Canonical Prompt Synthesis' },
  { id: 'critic', label: 'Quality Verification & Constraint Checks' },
  { id: 'format', label: 'Target Agent Preset Formatting' },
];

/** Format elapsed seconds as "Xs" or "Xm Ys". */
function formatElapsed(secs: number): string {
  if (secs < 60) return `${secs}s`;
  return `${Math.floor(secs / 60)}m ${secs % 60}s`;
}

/**
 * Honest pipeline progress card.
 *
 * While the backend is running (isComplete=false):
 *   - Shows a spinner and "Local Ollama inference in progress…"
 *   - Lists all pipeline stages as pending (numbered badges only)
 *   - Counts elapsed real seconds in the footer so the user has truthful
 *     feedback about how long the request has been running.
 *
 * This replaces the previous timer-based implementation that advanced through
 * stages every 2.8 s and permanently clamped at "Target Agent Preset
 * Formatting — Processing…" after 11.2 s, regardless of what the backend
 * was actually doing.
 *
 * When the HTTP response arrives (isComplete=true):
 *   - All stages gain emerald checkmarks.
 *   - Footer shows "Ready for Agent".
 */
export const PipelineProgress: React.FC<PipelineProgressProps> = ({
  targetAgent,
  hasKnowledge,
  hasProject,
  isComplete = false,
}) => {
  const [elapsed, setElapsed] = useState(0);

  // Count real seconds elapsed while the backend is processing.
  // Stops automatically when isComplete flips to true.
  useEffect(() => {
    if (isComplete) return;
    const interval = setInterval(() => {
      setElapsed((prev) => prev + 1);
    }, 1000);
    return () => clearInterval(interval);
  }, [isComplete]);

  return (
    <div className="w-full max-w-xl mx-auto p-6 rounded-2xl border border-border/80 bg-card/80 backdrop-blur-xl shadow-2xl text-left animate-in fade-in zoom-in-95 duration-200">
      {/* Card header */}
      <div className="flex items-center justify-between pb-4 border-b border-border/40">
        <div className="flex items-center gap-2.5">
          <div className="h-7 w-7 rounded-lg bg-primary/10 text-primary flex items-center justify-center">
            {isComplete ? (
              <CheckCircle2 className="h-4 w-4 text-emerald-500" />
            ) : (
              <Loader2 className="h-4 w-4 animate-spin" />
            )}
          </div>
          <div>
            <h3 className="text-sm font-semibold text-foreground flex items-center gap-2">
              <span>{isComplete ? 'Compilation complete!' : 'Compiling your prompt\u2026'}</span>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-primary/10 text-primary uppercase font-bold tracking-wider">
                {targetAgent}
              </span>
            </h3>
            <p className="text-xs text-muted-foreground font-mono">
              {isComplete
                ? 'Deterministic local-first AI compilation pipeline'
                : 'Local Ollama inference in progress\u2026'}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-1.5 text-[11px] font-mono text-muted-foreground">
          {hasProject && (
            <span className="px-2 py-0.5 rounded bg-muted/60 text-foreground border border-border/40">
              Project Context
            </span>
          )}
          {hasKnowledge && (
            <span className="px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-500 border border-emerald-500/20">
              RAG Active
            </span>
          )}
        </div>
      </div>

      {/* Pipeline stage list
          While running: all stages shown as pending (numbered badge only).
          We do NOT claim any stage is "Processing…" because the backend
          does not surface per-stage telemetry; asserting a specific stage
          would be a false claim.
          When complete: all stages gain emerald checkmarks. */}
      <div className="mt-4 space-y-2.5">
        {PIPELINE_STAGES.map((stage, idx) => (
          <div
            key={stage.id}
            className={`flex items-center justify-between px-3 py-2 rounded-xl transition-all duration-300 text-xs font-mono ${
              isComplete ? 'text-foreground/90' : 'text-muted-foreground/50'
            }`}
          >
            <div className="flex items-center gap-2.5">
              {isComplete ? (
                <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500 shrink-0" />
              ) : (
                <span className="h-3.5 w-3.5 rounded-full border border-muted-foreground/30 flex items-center justify-center text-[9px] shrink-0">
                  {idx + 1}
                </span>
              )}
              <span>{stage.label}</span>
            </div>
          </div>
        ))}
      </div>

      {/* Card footer */}
      <div className="mt-4 pt-3 border-t border-border/30 flex items-center justify-between text-[11px] text-muted-foreground font-mono">
        <span className="flex items-center gap-1.5">
          <Terminal className="h-3.5 w-3.5 text-muted-foreground" />
          <span>Local Ollama • qwen3:0.6b</span>
        </span>
        <span className="flex items-center gap-1 text-primary">
          <Sparkles className="h-3 w-3" />
          <span>
            {isComplete
              ? 'Ready for Agent'
              : elapsed > 0
              ? formatElapsed(elapsed)
              : 'Deterministic Invariants'}
          </span>
        </span>
      </div>
    </div>
  );
};
