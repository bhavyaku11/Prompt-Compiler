"use client";

import Timeline from "@/components/ui/timeline";
import { workflowTopItems, workflowBottomItems } from "./workflowData";
import workflowImage from "@/assets/workflow-showcase.png";
import { Terminal, Sparkles } from "lucide-react";
import { useTheme } from "@/context/ThemeContext";

export interface WorkflowTimelineProps {
  activeColor?: string;
  duration?: number;
}

export const WorkflowTimeline = ({
  activeColor,
  duration = 1.2,
}: WorkflowTimelineProps) => {
  const { isDark } = useTheme();
  // Pure monochrome silver-white in dark mode matching the footer theme, pitch black in light mode
  const resolvedColor = activeColor || (isDark ? "#ffffff" : "#09090b");

  return (
    <section className="relative w-full z-10">
      {/* GSAP Horizontal Scrub Timeline with Integrated Pinned Header */}
      <Timeline
        eyebrow="Deterministic Compilation Pipeline"
        headline={
          <>
            Six stages. Zero hallucinations.{" "}
            <span className="text-neutral-500 dark:text-neutral-400 font-normal">
              One continuous compilation.
            </span>
          </>
        }
        subtitle="Keep scrolling to trace pipeline execution — constraints verified, memory bound, ready-to-run prompts rendered."
        title="Compiler Pipeline"
        periodLabel="Pipeline 01 — 06"
        backgroundColor={isDark ? "#000000" : "#ffffff"}
        textColor={isDark ? "#f8fafc" : "#09090b"}
        mutedTextColor={isDark ? "#a1a1aa" : "#52525b"}
        activeColor={resolvedColor}
        imageUrl={workflowImage}
        imageAlt="Prompt Compiler Developer Workflow"
        duration={duration}
        topItems={workflowTopItems}
        bottomItems={workflowBottomItems}
      />

      {/* Lead-out section: graceful transition below the pinned section */}
      <div className="relative flex min-h-[30vh] flex-col items-center justify-center px-6 py-14 text-center max-w-3xl mx-auto border-t border-neutral-200 dark:border-white/10">
        <div className="flex items-center gap-2 text-xs font-mono text-emerald-600 dark:text-emerald-400 mb-3 px-3 py-1 rounded-full bg-emerald-500/[0.08] border border-emerald-500/20">
          <Terminal className="h-3.5 w-3.5" />
          <span>Deterministic Output Guaranteed</span>
        </div>
        <p className="text-xl sm:text-2xl font-medium text-foreground tracking-tight mb-2">
          From ambiguous requirement to implementation-ready prompt in milliseconds.
        </p>
        <p className="text-sm text-neutral-600 dark:text-neutral-300 font-mono flex items-center gap-1.5">
          <Sparkles className="h-3.5 w-3.5 text-neutral-500 dark:text-neutral-400" />
          Formatted for Cursor, Claude Code, Antigravity, Windsurf, or Codex agents.
        </p>
      </div>
    </section>
  );
};

export default WorkflowTimeline;
