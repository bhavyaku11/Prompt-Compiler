import React from 'react';
import {
  Laptop,
  Layers,
  Cpu,
  Database,
  Bot,
  ArrowDown,
  ShieldCheck,
  Sparkles,
  Search,
  CheckCircle2,
  FileCode2,
} from 'lucide-react';

export const ArchitectureFlowchart: React.FC = () => {
  return (
    <div className="w-full rounded-3xl border border-border/80 bg-card/60 backdrop-blur-xl p-5 sm:p-8 space-y-8 shadow-sm">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 border-b border-border/60">
        <div>
          <span className="text-[10px] font-mono font-semibold uppercase tracking-wider px-2.5 py-0.5 rounded-full bg-emerald-500/10 text-emerald-500 border border-emerald-500/20">
            System Topology Flowchart
          </span>
          <h3 className="text-base sm:text-lg font-bold text-foreground mt-1.5">
            Prompt Compiler End-to-End Architecture
          </h3>
        </div>
        <div className="flex items-center gap-2 text-xs font-mono text-muted-foreground">
          <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
          <span>Local Engine • Zero Cloud Telemetry</span>
        </div>
      </div>

      {/* FLOWCHART STAGES */}
      <div className="space-y-6">
        {/* =================================================================== */}
        {/* LAYER 1: CLIENT RUNTIME (TAURI 2 DESKTOP APPLICATION) */}
        {/* =================================================================== */}
        <div className="p-4 sm:p-5 rounded-2xl border border-indigo-500/30 bg-indigo-500/5 space-y-3">
          <div className="flex items-center justify-between">
            <span className="flex items-center gap-2 text-xs font-bold text-indigo-400 font-mono uppercase tracking-wider">
              <Laptop className="h-4 w-4" />
              <span>Layer 1: Desktop Shell & Presentation</span>
            </span>
            <span className="text-[10px] font-mono text-muted-foreground">Tauri v2 • Native macOS / Desktop</span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <div className="p-3.5 rounded-xl border border-border bg-card/80 space-y-1">
              <div className="flex items-center gap-1.5 text-xs font-bold text-foreground">
                <Layers className="h-3.5 w-3.5 text-indigo-400" />
                <span>React 19 & Vite UI</span>
              </div>
              <p className="text-[11px] text-muted-foreground leading-relaxed">
                Studio Composer, collapsible navigation sidebar, interview cards, real-time status pills.
              </p>
            </div>

            <div className="p-3.5 rounded-xl border border-border bg-card/80 space-y-1">
              <div className="flex items-center gap-1.5 text-xs font-bold text-foreground">
                <Sparkles className="h-3.5 w-3.5 text-primary" />
                <span>Agent Preset Configurator</span>
              </div>
              <p className="text-[11px] text-muted-foreground leading-relaxed">
                Cursor Composer, Claude Code CLI, Windsurf Cascade, and Copilot Workspace adapters.
              </p>
            </div>

            <div className="p-3.5 rounded-xl border border-border bg-card/80 space-y-1">
              <div className="flex items-center gap-1.5 text-xs font-bold text-foreground">
                <FileCode2 className="h-3.5 w-3.5 text-emerald-400" />
                <span>Native Rust Bridge</span>
              </div>
              <p className="text-[11px] text-muted-foreground leading-relaxed">
                Native folder picker dialog, window bounds, OS notifications, and sidecar process supervisor.
              </p>
            </div>
          </div>
        </div>

        {/* CONNECTION ARROW */}
        <div className="flex justify-center items-center gap-2 text-muted-foreground font-mono text-xs">
          <div className="h-6 w-px bg-border" />
          <div className="flex items-center gap-1.5 px-3 py-0.5 rounded-full border border-border bg-muted/30 text-[10px]">
            <span>Local IPC & HTTP Bridge (127.0.0.1:18000)</span>
            <ArrowDown className="h-3 w-3" />
          </div>
          <div className="h-6 w-px bg-border" />
        </div>

        {/* =================================================================== */}
        {/* LAYER 2: FASTAPI COMPILER ENGINE SIDECAR */}
        {/* =================================================================== */}
        <div className="p-4 sm:p-5 rounded-2xl border border-primary/30 bg-primary/5 space-y-3">
          <div className="flex items-center justify-between">
            <span className="flex items-center gap-2 text-xs font-bold text-primary font-mono uppercase tracking-wider">
              <Cpu className="h-4 w-4" />
              <span>Layer 2: Local Python FastAPI Sidecar Engine</span>
            </span>
            <span className="text-[10px] font-mono text-muted-foreground">PyInstaller Standalone Executable</span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
            <div className="p-3 rounded-xl border border-border bg-card/80 space-y-1">
              <span className="text-[10px] font-mono text-primary font-semibold">STAGE 1</span>
              <h5 className="text-xs font-bold text-foreground">Input Normalizer</h5>
              <p className="text-[11px] text-muted-foreground leading-relaxed">
                Extracts intent, task classification (Feature, Debug, Architecture), and extracts initial constraints.
              </p>
            </div>

            <div className="p-3 rounded-xl border border-border bg-card/80 space-y-1">
              <span className="text-[10px] font-mono text-indigo-400 font-semibold">STAGE 2</span>
              <h5 className="text-xs font-bold text-foreground">Interview Engine</h5>
              <p className="text-[11px] text-muted-foreground leading-relaxed">
                Detects ambiguities and generates interactive multiple-choice questions when choices exist.
              </p>
            </div>

            <div className="p-3 rounded-xl border border-border bg-card/80 space-y-1">
              <span className="text-[10px] font-mono text-emerald-400 font-semibold">STAGE 3</span>
              <h5 className="text-xs font-bold text-foreground">Template & Synthesizer</h5>
              <p className="text-[11px] text-muted-foreground leading-relaxed">
                Fills canonical structure: objective, requirements, boundaries, constraints, acceptance criteria.
              </p>
            </div>

            <div className="p-3 rounded-xl border border-border bg-card/80 space-y-1">
              <span className="text-[10px] font-mono text-amber-400 font-semibold">STAGE 4</span>
              <h5 className="text-xs font-bold text-foreground">Critic & Validator</h5>
              <p className="text-[11px] text-muted-foreground leading-relaxed">
                Verifies zero hallucinations, guards against fabricated dependencies, formats agent markdown.
              </p>
            </div>
          </div>
        </div>

        {/* CONNECTION ARROW */}
        <div className="flex justify-center items-center gap-2 text-muted-foreground font-mono text-xs">
          <div className="h-6 w-px bg-border" />
          <div className="flex items-center gap-1.5 px-3 py-0.5 rounded-full border border-border bg-muted/30 text-[10px]">
            <span>Embedded Vector Queries & Local LLM Invocations</span>
            <ArrowDown className="h-3 w-3" />
          </div>
          <div className="h-6 w-px bg-border" />
        </div>

        {/* =================================================================== */}
        {/* LAYER 3: DATA STORAGE & LOCAL AI INFERENCE */}
        {/* =================================================================== */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Storage Box */}
          <div className="p-4 sm:p-5 rounded-2xl border border-emerald-500/30 bg-emerald-500/5 space-y-3">
            <div className="flex items-center justify-between">
              <span className="flex items-center gap-2 text-xs font-bold text-emerald-500 font-mono uppercase tracking-wider">
                <Database className="h-4 w-4" />
                <span>Vector & Memory Store</span>
              </span>
              <span className="text-[10px] font-mono text-muted-foreground">Embedded SQLite</span>
            </div>

            <div className="space-y-2">
              <div className="p-3 rounded-xl border border-border bg-card/80 space-y-1">
                <div className="flex items-center gap-1.5 text-xs font-bold text-foreground">
                  <Search className="h-3.5 w-3.5 text-emerald-500" />
                  <span>SQLite-Vec Extension</span>
                </div>
                <p className="text-[11px] text-muted-foreground leading-relaxed">
                  Fast native vector similarity search on embeddings. Stores repository context, ADRs, coding guidelines, and past memories.
                </p>
              </div>

              <div className="p-3 rounded-xl border border-border bg-card/80 space-y-1">
                <div className="flex items-center gap-1.5 text-xs font-bold text-foreground">
                  <ShieldCheck className="h-3.5 w-3.5 text-emerald-500" />
                  <span>Zero Cloud Storage</span>
                </div>
                <p className="text-[11px] text-muted-foreground leading-relaxed">
                  Database files reside in local user application directories (<code className="text-[10px]">~/.prompt-compiler/</code>).
                </p>
              </div>
            </div>
          </div>

          {/* AI Inference Box */}
          <div className="p-4 sm:p-5 rounded-2xl border border-amber-500/30 bg-amber-500/5 space-y-3">
            <div className="flex items-center justify-between">
              <span className="flex items-center gap-2 text-xs font-bold text-amber-500 font-mono uppercase tracking-wider">
                <Bot className="h-4 w-4" />
                <span>Local AI Inference Engine</span>
              </span>
              <span className="text-[10px] font-mono text-muted-foreground">Ollama Daemon (127.0.0.1:11434)</span>
            </div>

            <div className="space-y-2">
              <div className="p-3 rounded-xl border border-border bg-card/80 space-y-1">
                <div className="flex items-center gap-1.5 text-xs font-bold text-foreground">
                  <Cpu className="h-3.5 w-3.5 text-amber-500" />
                  <span>Qwen 3 (0.6B / 4B)</span>
                </div>
                <p className="text-[11px] text-muted-foreground leading-relaxed">
                  Sub-second local generation tailored for reasoning, schema extraction, intent analysis, and structured Markdown synthesis.
                </p>
              </div>

              <div className="p-3 rounded-xl border border-border bg-card/80 space-y-1">
                <div className="flex items-center gap-1.5 text-xs font-bold text-foreground">
                  <CheckCircle2 className="h-3.5 w-3.5 text-amber-500" />
                  <span>nomic-embed-text (768 Dim)</span>
                </div>
                <p className="text-[11px] text-muted-foreground leading-relaxed">
                  High-performance text embedding model for chunking, indexing, and semantic document similarity.
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* FOOTER SUMMARY */}
      <div className="p-3.5 rounded-xl border border-border bg-muted/20 flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-xs font-mono text-muted-foreground">
        <span>Execution Flow: UI Input &rarr; Sidecar Pipeline &rarr; Vector Retrieval &rarr; Ollama Synthesis &rarr; Validated Prompt</span>
        <span className="text-emerald-500 font-semibold">100% Offline Capable</span>
      </div>
    </div>
  );
};

export default ArchitectureFlowchart;
