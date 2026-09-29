import React, { useState, useMemo, useEffect } from 'react';
import { useNavigate, useParams, Link } from 'react-router-dom';
import {
  BookOpen,
  Boxes,
  Workflow,
  Cpu,
  ChevronRight,
  Terminal,
  Search,
  Menu,
  X,
  ArrowRight,
  ArrowLeft,
  Sparkles,
  HelpCircle,
  FolderGit2,
  Compass,
  AlertTriangle,
  Lightbulb,
  ShieldCheck,
  Code,
  Copy,
  Check,
  Database,
  Bot,
  Laptop,
} from 'lucide-react';
import { Logo } from '@/components/ui/Logo';
import { ThemeToggle } from '@/components/ui/theme-toggle';
import { MagneticButton } from '@/components/ui/magnetic-button';
import { ArchitectureFlowchart } from '@/components/docs/ArchitectureFlowchart';

type DocSection = 'product' | 'workflow' | 'architecture' | 'documentation' | 'overview';

interface DocItem {
  id: DocSection;
  title: string;
  badge: string;
  description: string;
  icon: React.ComponentType<{ className?: string }>;
  path: string;
}

const docItems: DocItem[] = [
  {
    id: 'product',
    title: 'Product',
    badge: 'Problem & Solution',
    description: 'Problem statement, our core idea, and the complete compiler solution.',
    icon: Boxes,
    path: '/docs/product',
  },
  {
    id: 'workflow',
    title: 'Workflow',
    badge: 'Application Pipeline',
    description: 'End-to-end execution workflow of the application from intent to compiled prompt.',
    icon: Workflow,
    path: '/docs/workflow',
  },
  {
    id: 'architecture',
    title: 'Architecture',
    badge: 'System Design & Flowchart',
    description: 'System topology, multi-tier execution model, and visual architecture flowchart.',
    icon: Cpu,
    path: '/docs/architecture',
  },
  {
    id: 'documentation',
    title: 'Documentation',
    badge: 'Master Guide',
    description: 'Complete documentation for Prompt Compiler — setup, features, presets, API, and guide.',
    icon: BookOpen,
    path: '/docs/documentation',
  },
];

export const DocsView: React.FC = () => {
  const navigate = useNavigate();
  const { section } = useParams<{ section?: string }>();
  const [searchQuery, setSearchQuery] = useState('');
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const [copiedCode, setCopiedCode] = useState<string | null>(null);

  // If user navigates to /docs/github, redirect directly to user's GitHub
  useEffect(() => {
    if (section && section.toLowerCase() === 'github') {
      window.location.href = 'https://github.com/bhavyaku11/Prompt-Compiler';
    }
  }, [section]);

  const activeSection: DocSection = useMemo(() => {
    if (!section) return 'product';
    const s = section.toLowerCase();
    if (s === 'workflow') return 'workflow';
    if (s === 'architecture') return 'architecture';
    if (s === 'documentation' || s === 'overview' || s === 'docs') return 'documentation';
    return 'product';
  }, [section]);

  const currentDoc = docItems.find((item) => item.id === activeSection) || docItems[0];

  const handleCopy = (text: string, id: string) => {
    navigator.clipboard.writeText(text);
    setCopiedCode(id);
    setTimeout(() => setCopiedCode(null), 2000);
  };

  const filteredItems = useMemo(() => {
    if (!searchQuery.trim()) return docItems;
    const query = searchQuery.toLowerCase();
    return docItems.filter(
      (item) =>
        item.title.toLowerCase().includes(query) ||
        item.description.toLowerCase().includes(query) ||
        item.badge.toLowerCase().includes(query)
    );
  }, [searchQuery]);

  const currentIndex = docItems.findIndex((item) => item.id === activeSection);
  const prevDoc = currentIndex > 0 ? docItems[currentIndex - 1] : null;
  const nextDoc = currentIndex < docItems.length - 1 ? docItems[currentIndex + 1] : null;

  return (
    <div className="min-h-screen bg-background text-foreground font-sans flex flex-col selection:bg-neutral-800 selection:text-white dark:selection:bg-white dark:selection:text-black">
      {/* Background Developer Grid Pattern */}
      <div className="fixed inset-0 bg-grid-pattern opacity-40 pointer-events-none z-0" aria-hidden="true" />

      {/* ========================================================================= */}
      {/* TOP HEADER */}
      {/* ========================================================================= */}
      <header className="sticky top-0 z-40 w-full border-b border-border/80 bg-background/90 backdrop-blur-xl px-4 sm:px-8 h-16 flex items-center justify-between">
        {/* Left: Brand Logo & Title */}
        <div className="flex items-center gap-3.5">
          <button
            type="button"
            onClick={() => setIsMobileMenuOpen((prev) => !prev)}
            className="p-1.5 rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted md:hidden cursor-pointer"
            aria-label="Toggle docs navigation"
          >
            {isMobileMenuOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </button>

          <Link
            to="/"
            className="flex items-center gap-3 group focus:outline-none"
            title="Return to Prompt Compiler Home"
          >
            <Logo size="md" />
            <div className="flex items-center gap-2">
              <span className="font-bold text-foreground tracking-tight text-base sm:text-lg group-hover:text-primary transition-colors">
                Prompt Compiler
              </span>
              <span className="text-[10px] font-mono font-semibold uppercase tracking-wider px-2 py-0.5 rounded-md bg-primary/10 text-primary border border-primary/20">
                Docs
              </span>
            </div>
          </Link>
        </div>

        {/* Right: Theme Toggle + Back to Home */}
        <div className="flex items-center gap-2.5 sm:gap-3">
          {/* Theme Toggle Button */}
          <ThemeToggle />

          {/* Back to Home Button */}
          <MagneticButton
            as="button"
            type="button"
            onClick={() => navigate('/')}
            aria-label="Back to Prompt Compiler Home"
            className="footer-glass-pill h-9 px-3.5 sm:px-4 rounded-full text-xs font-mono font-medium flex items-center gap-1.5 sm:gap-2 cursor-pointer transition-colors duration-200 shadow-sm text-foreground"
          >
            <ArrowLeft className="h-3.5 w-3.5 pointer-events-none" />
            <span className="pointer-events-none">Back to Home</span>
          </MagneticButton>
        </div>
      </header>

      {/* ========================================================================= */}
      {/* BODY LAYOUT: SIDEBAR + MAIN CONTENT + ON-THIS-PAGE TOC */}
      {/* ========================================================================= */}
      <div className="flex-1 flex max-w-7xl w-full mx-auto relative z-10">
        {/* ======================================================================= */}
        {/* LEFT SIDEBAR NAVIGATION */}
        {/* ======================================================================= */}
        <aside
          className={`fixed inset-y-16 left-0 z-30 w-72 bg-card/95 md:bg-transparent backdrop-blur-xl md:backdrop-blur-none border-r border-border/70 p-5 flex flex-col gap-6 transform transition-transform duration-200 ease-in-out md:translate-x-0 md:static md:w-64 lg:w-72 shrink-0 ${
            isMobileMenuOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'
          }`}
        >
          {/* Search Box */}
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search documentation..."
              className="w-full pl-9 pr-3 py-1.5 text-xs rounded-xl border border-border bg-background focus:outline-none focus:ring-1 focus:ring-primary text-foreground placeholder:text-muted-foreground/60 transition-colors"
            />
          </div>

          {/* Navigation Links - Simple, Clean List in Exact Sequence */}
          <div className="flex-1 overflow-y-auto space-y-1.5 pr-1 custom-scrollbar">
            <nav className="space-y-1">
              {filteredItems.map((item) => {
                const Icon = item.icon;
                const isActive = activeSection === item.id;
                return (
                  <Link
                    key={item.id}
                    to={item.path}
                    onClick={() => setIsMobileMenuOpen(false)}
                    className={`flex items-center gap-3 px-3.5 py-2.5 rounded-xl text-sm font-medium transition-all ${
                      isActive
                        ? 'bg-primary/10 text-primary font-semibold border border-primary/20 shadow-2xs'
                        : 'text-muted-foreground hover:text-foreground hover:bg-muted/50 border border-transparent'
                    }`}
                  >
                    <Icon className={`h-4 w-4 shrink-0 ${isActive ? 'text-primary' : 'text-muted-foreground'}`} />
                    <span className="flex-1">{item.title}</span>
                    {isActive && <ChevronRight className="h-3.5 w-3.5 text-primary" />}
                  </Link>
                );
              })}
            </nav>
          </div>
        </aside>

        {/* Overlay backdrop for mobile menu */}
        {isMobileMenuOpen && (
          <div
            onClick={() => setIsMobileMenuOpen(false)}
            className="fixed inset-0 bg-black/50 backdrop-blur-xs z-20 md:hidden"
            aria-hidden="true"
          />
        )}

        {/* ======================================================================= */}
        {/* MAIN DOCUMENTATION CONTENT */}
        {/* ======================================================================= */}
        <main className="flex-1 min-w-0 px-4 sm:px-8 lg:px-12 py-8 overflow-y-auto">
          {/* Breadcrumb Path */}
          <nav className="flex items-center gap-2 text-xs font-mono text-muted-foreground mb-6" aria-label="Breadcrumb">
            <Link to="/" className="hover:text-foreground transition-colors">Home</Link>
            <ChevronRight className="h-3.5 w-3.5 opacity-50" />
            <Link to="/docs" className="hover:text-foreground transition-colors">Docs</Link>
            <ChevronRight className="h-3.5 w-3.5 opacity-50" />
            <span className="text-foreground font-semibold">{currentDoc.title}</span>
          </nav>

          {/* Section Header */}
          <header className="space-y-3 pb-8 border-b border-border/80">
            <div className="flex items-center gap-2.5">
              <span className="text-xs font-mono font-semibold uppercase tracking-wider px-2.5 py-0.5 rounded-full bg-primary/10 text-primary border border-primary/20">
                {currentDoc.badge}
              </span>
              <span className="text-xs text-muted-foreground font-mono">Prompt Compiler v0.1.0</span>
            </div>
            <h1 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-foreground">
              {currentDoc.title}
            </h1>
            <p className="text-base text-muted-foreground leading-relaxed max-w-3xl">
              {currentDoc.description}
            </p>
          </header>

          {/* =================================================================== */}
          {/* CONTENT BY SECTION */}
          {/* =================================================================== */}
          <article className="py-8 space-y-12">
            {/* ================================================================= */}
            {/* 1. PRODUCT SECTION */}
            {/* ================================================================= */}
            {activeSection === 'product' && (
              <div className="space-y-10 animate-in fade-in duration-200">
                {/* Introduction */}
                <section className="space-y-4">
                  <h2 className="text-xl sm:text-2xl font-bold text-foreground">
                    About Prompt Compiler
                  </h2>
                  <p className="text-sm text-muted-foreground leading-relaxed">
                    <strong>Prompt Compiler</strong> is an offline, local-first development tool that converts rough, informal, or incomplete human requirements into deterministic, structured, implementation-ready prompts designed for modern AI coding agents such as <strong>Cursor Composer</strong>, <strong>Claude Code</strong>, <strong>Windsurf Cascade</strong>, and <strong>GitHub Copilot</strong>.
                  </p>
                </section>

                {/* THE PROBLEM STATEMENT */}
                <section className="space-y-4">
                  <div className="flex items-center gap-2 text-red-500 font-mono text-xs font-bold uppercase tracking-wider">
                    <AlertTriangle className="h-4 w-4" />
                    <span>The Problem Statement</span>
                  </div>
                  <h3 className="text-lg font-bold text-foreground">
                    The AI Prompting Gap in Modern Software Engineering
                  </h3>
                  <div className="p-5 rounded-2xl border border-red-500/20 bg-red-500/5 space-y-3 text-xs text-foreground/90 leading-relaxed">
                    <p>
                      Software developers and vibe coders frequently prompt AI coding agents with short, ambiguous sentences such as <em>&ldquo;add auth to my app&rdquo;</em>, <em>&ldquo;make a responsive dashboard&rdquo;</em>, or <em>&ldquo;fix this bug&rdquo;</em>.
                    </p>
                    <p>
                      Because AI coding agents lack complete project context and explicit technical constraints, they are forced to <strong>guess missing requirements</strong>. This leads to severe development friction:
                    </p>
                    <ul className="list-disc list-inside space-y-1.5 pl-2 text-muted-foreground">
                      <li><strong>Hallucinated Dependencies:</strong> Agents invent database columns, non-existent libraries, or incompatible framework conventions that break the project build.</li>
                      <li><strong>Destructive File Overwrites:</strong> Without strict boundaries, agents refactor unrelated files, wipe custom logic, or drop critical error handling.</li>
                      <li><strong>Circular Debug Loops:</strong> Developers spend 30 to 45 minutes repeatedly writing follow-up prompts to undo mistakes that should have been prevented from the start.</li>
                      <li><strong>Cloud Privacy Exposure:</strong> Using cloud-based prompt refiners uploads proprietary business logic, schemas, and API tokens to third-party providers.</li>
                    </ul>
                  </div>
                </section>

                {/* OUR IDEA */}
                <section className="space-y-4">
                  <div className="flex items-center gap-2 text-indigo-500 font-mono text-xs font-bold uppercase tracking-wider">
                    <Lightbulb className="h-4 w-4" />
                    <span>Our Idea</span>
                  </div>
                  <h3 className="text-lg font-bold text-foreground">
                    Treat Prompting as a Rigorous Compiler Pipeline
                  </h3>
                  <p className="text-sm text-muted-foreground leading-relaxed">
                    In traditional computing, programming languages have <strong>compilers</strong> (like Clang or Rustc) that transform loose human text into rigorous machine bytecode through parsing, syntax analysis, type-checking, and optimization.
                  </p>
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 pt-2">
                    <div className="p-4 rounded-xl border border-border bg-card/60 space-y-1.5">
                      <span className="text-[10px] font-mono text-primary font-bold">1. PARSE & LEX</span>
                      <h4 className="text-xs font-bold text-foreground">Intent Extraction</h4>
                      <p className="text-[11px] text-muted-foreground leading-relaxed">
                        Decompose rough sentences into structured Abstract Syntax of intent, domain, and detected unknowns.
                      </p>
                    </div>
                    <div className="p-4 rounded-xl border border-border bg-card/60 space-y-1.5">
                      <span className="text-[10px] font-mono text-indigo-400 font-bold">2. TYPECHECK</span>
                      <h4 className="text-xs font-bold text-foreground">Codebase Verification</h4>
                      <p className="text-[11px] text-muted-foreground leading-relaxed">
                        Verify assumptions against local files, database schemas, and architectural guidelines via vector memory.
                      </p>
                    </div>
                    <div className="p-4 rounded-xl border border-border bg-card/60 space-y-1.5">
                      <span className="text-[10px] font-mono text-emerald-400 font-bold">3. CODEGEN</span>
                      <h4 className="text-xs font-bold text-foreground">Agent Target Syntax</h4>
                      <p className="text-[11px] text-muted-foreground leading-relaxed">
                        Generate dialect-specific instructions (Cursor rules, Claude CLI parameters, Windsurf Cascade directives).
                      </p>
                    </div>
                  </div>
                </section>

                {/* OUR SOLUTION */}
                <section className="space-y-4">
                  <div className="flex items-center gap-2 text-emerald-500 font-mono text-xs font-bold uppercase tracking-wider">
                    <ShieldCheck className="h-4 w-4" />
                    <span>Our Solution</span>
                  </div>
                  <h3 className="text-lg font-bold text-foreground">
                    The Prompt Compiler System
                  </h3>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div className="p-5 rounded-2xl border border-border/80 bg-card/60 space-y-2">
                      <div className="flex items-center gap-2">
                        <span className="h-2 w-2 rounded-full bg-primary" />
                        <h4 className="text-xs font-bold text-foreground uppercase tracking-wide">
                          Zero-Hallucination Extraction
                        </h4>
                      </div>
                      <p className="text-xs text-muted-foreground leading-relaxed">
                        The compiler engine separates input into <em>Confirmed Requirements</em>, <em>Safe Defaults</em>, and <em>Explicit Unknowns</em>. It never fabricates requirements that the user did not specify.
                      </p>
                    </div>

                    <div className="p-5 rounded-2xl border border-border/80 bg-card/60 space-y-2">
                      <div className="flex items-center gap-2">
                        <span className="h-2 w-2 rounded-full bg-indigo-500" />
                        <h4 className="text-xs font-bold text-foreground uppercase tracking-wide">
                          Adaptive Interview Mode
                        </h4>
                      </div>
                      <p className="text-xs text-muted-foreground leading-relaxed">
                        When critical architectural choices are ambiguous, the engine pauses and asks 1 to 3 targeted multiple-choice questions directly in the UI before generating code prompts.
                      </p>
                    </div>

                    <div className="p-5 rounded-2xl border border-border/80 bg-card/60 space-y-2">
                      <div className="flex items-center gap-2">
                        <span className="h-2 w-2 rounded-full bg-emerald-500" />
                        <h4 className="text-xs font-bold text-foreground uppercase tracking-wide">
                          Local Vector Memory (sqlite-vec)
                        </h4>
                      </div>
                      <p className="text-xs text-muted-foreground leading-relaxed">
                        Ingests your local project repository, indexing documentation, architectural decision records (ADRs), and schemas so prompts reference exact code facts.
                      </p>
                    </div>

                    <div className="p-5 rounded-2xl border border-border/80 bg-card/60 space-y-2">
                      <div className="flex items-center gap-2">
                        <span className="h-2 w-2 rounded-full bg-amber-500" />
                        <h4 className="text-xs font-bold text-foreground uppercase tracking-wide">
                          100% Offline & Private
                        </h4>
                      </div>
                      <p className="text-xs text-muted-foreground leading-relaxed">
                        Powered by a local Ollama daemon and local embeddings on <code className="text-[10px]">127.0.0.1</code>. Your proprietary source code never leaves your workstation.
                      </p>
                    </div>
                  </div>
                </section>
              </div>
            )}

            {/* ================================================================= */}
            {/* 2. WORKFLOW SECTION */}
            {/* ================================================================= */}
            {activeSection === 'workflow' && (
              <div className="space-y-10 animate-in fade-in duration-200">
                <section className="space-y-4">
                  <h2 className="text-xl sm:text-2xl font-bold text-foreground">
                    Application Execution Workflow
                  </h2>
                  <p className="text-sm text-muted-foreground leading-relaxed">
                    The Prompt Compiler operates through a structured multi-phase pipeline designed to eliminate ambiguity, enrich context from local vector memory, and validate prompt soundness before export.
                  </p>
                </section>

                {/* THE 6-STEP WORKFLOW LIFECYCLE */}
                <section className="space-y-6">
                  <h3 className="text-lg font-bold text-foreground flex items-center gap-2">
                    <Workflow className="h-5 w-5 text-indigo-500" />
                    <span>End-to-End Pipeline Phases</span>
                  </h3>

                  <div className="space-y-4">
                    {/* Phase 1 */}
                    <div className="p-5 rounded-2xl border border-border bg-card/60 space-y-3">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2.5">
                          <span className="px-2.5 py-1 rounded-xl bg-primary/10 text-primary font-mono font-bold text-xs border border-primary/20">
                            PHASE 01
                          </span>
                          <h4 className="text-sm font-bold text-foreground">
                            Input Ingestion & Task Classification
                          </h4>
                        </div>
                        <span className="text-[10px] font-mono text-muted-foreground hidden sm:inline">Normalizer</span>
                      </div>
                      <p className="text-xs text-muted-foreground leading-relaxed">
                        The developer provides raw text in the Studio Composer or clicks a category starter chip (<em>Build a Feature</em>, <em>Modify Existing Code</em>, <em>Debug an Issue</em>, <em>Analyze Architecture</em>, or <em>Explain Code</em>). The engine normalizes whitespace, classifies task type, and analyzes core intent.
                      </p>
                    </div>

                    {/* Phase 2 */}
                    <div className="p-5 rounded-2xl border border-border bg-card/60 space-y-3">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2.5">
                          <span className="px-2.5 py-1 rounded-xl bg-indigo-500/10 text-indigo-500 font-mono font-bold text-xs border border-indigo-500/20">
                            PHASE 02
                          </span>
                          <h4 className="text-sm font-bold text-foreground">
                            Project Vector Search & Knowledge Retrieval
                          </h4>
                        </div>
                        <span className="text-[10px] font-mono text-muted-foreground hidden sm:inline">sqlite-vec Engine</span>
                      </div>
                      <p className="text-xs text-muted-foreground leading-relaxed">
                        If a project directory is linked, the engine performs cosine similarity searches over embedded code files and documentation chunks. It retrieves relevant database models, routing tables, and conventions to ground the prompt in codebase reality.
                      </p>
                    </div>

                    {/* Phase 3 */}
                    <div className="p-5 rounded-2xl border border-border bg-card/60 space-y-3">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2.5">
                          <span className="px-2.5 py-1 rounded-xl bg-purple-500/10 text-purple-500 font-mono font-bold text-xs border border-purple-500/20">
                            PHASE 03
                          </span>
                          <h4 className="text-sm font-bold text-foreground">
                            Adaptive Clarification Interview (Optional / Triggered)
                          </h4>
                        </div>
                        <span className="text-[10px] font-mono text-muted-foreground hidden sm:inline">Interview Loop</span>
                      </div>
                      <p className="text-xs text-muted-foreground leading-relaxed">
                        If key technical details are ambiguous or the user has toggled <strong>Interview Mode</strong>, the interview engine asks 1 to 3 targeted multiple-choice questions. User responses are fed into the compiler state, resolving choices before compilation.
                      </p>
                    </div>

                    {/* Phase 4 */}
                    <div className="p-5 rounded-2xl border border-border bg-card/60 space-y-3">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2.5">
                          <span className="px-2.5 py-1 rounded-xl bg-emerald-500/10 text-emerald-500 font-mono font-bold text-xs border border-emerald-500/20">
                            PHASE 04
                          </span>
                          <h4 className="text-sm font-bold text-foreground">
                            Canonical Prompt Synthesis
                          </h4>
                        </div>
                        <span className="text-[10px] font-mono text-muted-foreground hidden sm:inline">Generator</span>
                      </div>
                      <p className="text-xs text-muted-foreground leading-relaxed">
                        The generator synthesizes requirements into a canonical prompt structure: <strong>Objective</strong>, <strong>Architecture & Scope Boundaries</strong>, <strong>Technical Specifications</strong>, <strong>Non-Negotiable Constraints</strong>, and <strong>Testable Verification Criteria</strong>.
                      </p>
                    </div>

                    {/* Phase 5 */}
                    <div className="p-5 rounded-2xl border border-border bg-card/60 space-y-3">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2.5">
                          <span className="px-2.5 py-1 rounded-xl bg-amber-500/10 text-amber-500 font-mono font-bold text-xs border border-amber-500/20">
                            PHASE 05
                          </span>
                          <h4 className="text-sm font-bold text-foreground">
                            Critic Validation & Hallucination Guard
                          </h4>
                        </div>
                        <span className="text-[10px] font-mono text-muted-foreground hidden sm:inline">Validator</span>
                      </div>
                      <p className="text-xs text-muted-foreground leading-relaxed">
                        A secondary verification pass inspects the generated output to ensure no unauthorized requirements were fabricated, checking that constraints are rigorously enforced and safe defaults are marked.
                      </p>
                    </div>

                    {/* Phase 6 */}
                    <div className="p-5 rounded-2xl border border-border bg-card/60 space-y-3">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2.5">
                          <span className="px-2.5 py-1 rounded-xl bg-cyan-500/10 text-cyan-500 font-mono font-bold text-xs border border-cyan-500/20">
                            PHASE 06
                          </span>
                          <h4 className="text-sm font-bold text-foreground">
                            Agent Preset Formatting & One-Click Copy
                          </h4>
                        </div>
                        <span className="text-[10px] font-mono text-muted-foreground hidden sm:inline">Export</span>
                      </div>
                      <p className="text-xs text-muted-foreground leading-relaxed">
                        The compiled prompt is formatted specifically for the chosen agent (e.g. Cursor Composer with <code className="text-[11px]">@file</code> references, Claude Code CLI flags, or Windsurf rules), rendered with syntax highlighting, saved to local history, and copied in one click.
                      </p>
                    </div>
                  </div>
                </section>

                {/* WORKFLOW COMPARISON TABLE */}
                <section className="space-y-4">
                  <h3 className="text-base font-bold text-foreground">
                    Workflow Comparison: Standard Chat vs. Prompt Compiler
                  </h3>
                  <div className="overflow-x-auto rounded-2xl border border-border">
                    <table className="w-full text-left text-xs border-collapse">
                      <thead>
                        <tr className="bg-muted/40 border-b border-border text-muted-foreground font-mono">
                          <th className="p-3.5 font-semibold">Aspect</th>
                          <th className="p-3.5 font-semibold text-red-500">Unstructured Prompting</th>
                          <th className="p-3.5 font-semibold text-emerald-500">Prompt Compiler Workflow</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-border/60">
                        <tr>
                          <td className="p-3.5 font-medium text-foreground">Requirement Gathering</td>
                          <td className="p-3.5 text-muted-foreground">Vague guesses made by the coding agent</td>
                          <td className="p-3.5 text-foreground font-medium">Deterministic extraction + targeted interview</td>
                        </tr>
                        <tr>
                          <td className="p-3.5 font-medium text-foreground">Context Injection</td>
                          <td className="p-3.5 text-muted-foreground">Manual file copying into chat window</td>
                          <td className="p-3.5 text-foreground font-medium">Automatic local vector retrieval via sqlite-vec</td>
                        </tr>
                        <tr>
                          <td className="p-3.5 font-medium text-foreground">Scope Boundaries</td>
                          <td className="p-3.5 text-muted-foreground">None — agent modifies arbitrary files</td>
                          <td className="p-3.5 text-foreground font-medium">Explicit boundaries and forbidden modifications</td>
                        </tr>
                        <tr>
                          <td className="p-3.5 font-medium text-foreground">Privacy & Telemetry</td>
                          <td className="p-3.5 text-muted-foreground">Code sent to remote cloud APIs</td>
                          <td className="p-3.5 text-foreground font-medium">100% local inference on 127.0.0.1</td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                </section>
              </div>
            )}

            {/* ================================================================= */}
            {/* 3. ARCHITECTURE SECTION */}
            {/* ================================================================= */}
            {activeSection === 'architecture' && (
              <div className="space-y-10 animate-in fade-in duration-200">
                <section className="space-y-4">
                  <h2 className="text-xl sm:text-2xl font-bold text-foreground">
                    System Architecture & Flowchart
                  </h2>
                  <p className="text-sm text-muted-foreground leading-relaxed">
                    Prompt Compiler is designed from the ground up as a dual-tier desktop application combining a high-performance <strong>Tauri v2 native shell</strong> and an offline <strong>Python FastAPI sidecar engine</strong> with embedded <strong>sqlite-vec</strong>.
                  </p>
                </section>

                {/* THE VISUAL FLOWCHART COMPONENT */}
                <section className="space-y-4">
                  <ArchitectureFlowchart />
                </section>

                {/* SYSTEM LAYERS DETAILED BREAKDOWN */}
                <section className="space-y-6 pt-4">
                  <h3 className="text-lg font-bold text-foreground">
                    Core Architectural Subsystems
                  </h3>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {/* Subsystem 1 */}
                    <div className="p-5 rounded-2xl border border-border bg-card/60 space-y-2.5">
                      <div className="flex items-center gap-2 text-indigo-400">
                        <Laptop className="h-4 w-4" />
                        <h4 className="text-xs font-bold text-foreground uppercase tracking-wide">
                          1. Tauri v2 Desktop Host
                        </h4>
                      </div>
                      <p className="text-xs text-muted-foreground leading-relaxed">
                        Compiled as a native macOS application bundle with Rust. Supervised via Tauri's <code className="text-[11px]">externalBin</code> configuration. Controls native file pickers, window lifecycle, and manages sidecar process startup and shutdown.
                      </p>
                    </div>

                    {/* Subsystem 2 */}
                    <div className="p-5 rounded-2xl border border-border bg-card/60 space-y-2.5">
                      <div className="flex items-center gap-2 text-primary">
                        <Cpu className="h-4 w-4" />
                        <h4 className="text-xs font-bold text-foreground uppercase tracking-wide">
                          2. FastAPI Sidecar Service
                        </h4>
                      </div>
                      <p className="text-xs text-muted-foreground leading-relaxed">
                        Packaged into a standalone Mach-O executable with PyInstaller. Binds exclusively to <code className="text-[11px]">127.0.0.1:18000</code>. Provides clean asynchronous REST endpoints for requirement compilation, document ingestion, and interview flows.
                      </p>
                    </div>

                    {/* Subsystem 3 */}
                    <div className="p-5 rounded-2xl border border-border bg-card/60 space-y-2.5">
                      <div className="flex items-center gap-2 text-emerald-400">
                        <Database className="h-4 w-4" />
                        <h4 className="text-xs font-bold text-foreground uppercase tracking-wide">
                          3. SQLite & SQLite-Vec Storage
                        </h4>
                      </div>
                      <p className="text-xs text-muted-foreground leading-relaxed">
                        Embedded vector extension compiled directly into SQLite. Stores 768-dimensional vector embeddings without requiring heavy external database containers or network daemons.
                      </p>
                    </div>

                    {/* Subsystem 4 */}
                    <div className="p-5 rounded-2xl border border-border bg-card/60 space-y-2.5">
                      <div className="flex items-center gap-2 text-amber-400">
                        <Bot className="h-4 w-4" />
                        <h4 className="text-xs font-bold text-foreground uppercase tracking-wide">
                          4. Local Ollama LLM Runtime
                        </h4>
                      </div>
                      <p className="text-xs text-muted-foreground leading-relaxed">
                        Interfaces locally with Ollama over HTTP at <code className="text-[11px]">127.0.0.1:11434</code>. Utilizes <strong>Qwen 3 (0.6B / 4B)</strong> for reasoning, structuring, and critic verification, plus <strong>nomic-embed-text</strong> for document embeddings.
                      </p>
                    </div>
                  </div>
                </section>
              </div>
            )}

            {/* ================================================================= */}
            {/* 4. DOCUMENTATION (MASTER MANUAL) SECTION */}
            {/* ================================================================= */}
            {activeSection === 'documentation' && (
              <div className="space-y-12 animate-in fade-in duration-200">
                {/* Notice Banner */}
                <div className="p-5 rounded-2xl border border-primary/20 bg-primary/5 flex items-start gap-3.5 text-xs text-foreground">
                  <BookOpen className="h-5 w-5 text-primary shrink-0 mt-0.5" />
                  <div className="space-y-1">
                    <p className="font-bold text-sm">Prompt Compiler Documentation Manual</p>
                    <p className="text-muted-foreground leading-relaxed">
                      Complete reference guide containing setup instructions, studio operations, agent presets, API endpoints, and troubleshooting.
                    </p>
                  </div>
                </div>

                {/* CHAPTER 1: PREREQUISITES & SETUP */}
                <section className="space-y-4">
                  <h2 className="text-xl font-bold text-foreground flex items-center gap-2">
                    <Compass className="h-5 w-5 text-primary" />
                    <span>1. Prerequisites & Quick Start</span>
                  </h2>
                  <p className="text-xs text-muted-foreground leading-relaxed">
                    Prompt Compiler executes entirely on your workstation. Ensure you have the local Ollama engine installed and the required models pulled.
                  </p>

                  <div className="space-y-3">
                    <div className="p-4 rounded-xl border border-border bg-card/80 space-y-2">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-mono font-bold text-foreground">Step 1: Pull Local LLM & Embedding Models</span>
                        <button
                          type="button"
                          onClick={() => handleCopy('ollama pull qwen3:0.6b\nollama pull nomic-embed-text', 'code1')}
                          className="flex items-center gap-1 text-[11px] font-mono text-muted-foreground hover:text-foreground cursor-pointer"
                        >
                          {copiedCode === 'code1' ? <Check className="h-3 w-3 text-emerald-500" /> : <Copy className="h-3 w-3" />}
                          <span>{copiedCode === 'code1' ? 'Copied' : 'Copy'}</span>
                        </button>
                      </div>
                      <pre className="p-3 rounded-lg bg-background text-[11px] font-mono text-primary overflow-x-auto">
                        ollama pull qwen3:0.6b{'\n'}ollama pull nomic-embed-text
                      </pre>
                    </div>

                    <div className="p-4 rounded-xl border border-border bg-card/80 space-y-2">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-mono font-bold text-foreground">Step 2: Launch Prompt Compiler Desktop</span>
                        <button
                          type="button"
                          onClick={() => handleCopy('open "/Applications/Prompt Compiler.app"', 'code2')}
                          className="flex items-center gap-1 text-[11px] font-mono text-muted-foreground hover:text-foreground cursor-pointer"
                        >
                          {copiedCode === 'code2' ? <Check className="h-3 w-3 text-emerald-500" /> : <Copy className="h-3 w-3" />}
                          <span>{copiedCode === 'code2' ? 'Copied' : 'Copy'}</span>
                        </button>
                      </div>
                      <pre className="p-3 rounded-lg bg-background text-[11px] font-mono text-emerald-500 overflow-x-auto">
                        open "/Applications/Prompt Compiler.app"
                      </pre>
                    </div>
                  </div>
                </section>

                {/* CHAPTER 2: STUDIO OPERATING GUIDE */}
                <section className="space-y-4">
                  <h2 className="text-xl font-bold text-foreground flex items-center gap-2">
                    <Terminal className="h-5 w-5 text-indigo-500" />
                    <span>2. Studio Features & Knowledge Linking</span>
                  </h2>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div className="p-4 rounded-xl border border-border bg-card/60 space-y-2">
                      <h4 className="text-xs font-bold text-foreground flex items-center gap-1.5">
                        <FolderGit2 className="h-4 w-4 text-primary" />
                        <span>Link Project Folders</span>
                      </h4>
                      <p className="text-xs text-muted-foreground leading-relaxed">
                        Click <strong>+ Project</strong> or the folder picker in the bottom-left sidebar. Prompt Compiler reads your repository structure and indexes schemas and markdown documentation into <code className="text-[10px]">sqlite-vec</code>.
                      </p>
                    </div>

                    <div className="p-4 rounded-xl border border-border bg-card/60 space-y-2">
                      <h4 className="text-xs font-bold text-foreground flex items-center gap-1.5">
                        <HelpCircle className="h-4 w-4 text-indigo-400" />
                        <span>Adaptive Interview Mode</span>
                      </h4>
                      <p className="text-xs text-muted-foreground leading-relaxed">
                        Toggle the <strong>Interview Mode</strong> button beside the composer to force interactive clarifying questions before compiling, ideal for complex greenfield feature requests.
                      </p>
                    </div>
                  </div>
                </section>

                {/* CHAPTER 3: AGENT PRESETS */}
                <section className="space-y-4">
                  <h2 className="text-xl font-bold text-foreground flex items-center gap-2">
                    <Sparkles className="h-5 w-5 text-amber-500" />
                    <span>3. Supported AI Agent Presets</span>
                  </h2>
                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 text-xs">
                    <div className="p-4 rounded-xl border border-border bg-card/60 space-y-1">
                      <h4 className="font-bold text-foreground">Cursor Composer</h4>
                      <p className="text-muted-foreground text-[11px] leading-relaxed">
                        Formats with <code className="text-[10px]">@files</code> tags, file boundaries, step-by-step checklists, and rules.
                      </p>
                    </div>
                    <div className="p-4 rounded-xl border border-border bg-card/60 space-y-1">
                      <h4 className="font-bold text-foreground">Claude Code CLI</h4>
                      <p className="text-muted-foreground text-[11px] leading-relaxed">
                        Formats concise bash instructions, command-line arguments, and specific test execution directives.
                      </p>
                    </div>
                    <div className="p-4 rounded-xl border border-border bg-card/60 space-y-1">
                      <h4 className="font-bold text-foreground">Windsurf Cascade</h4>
                      <p className="text-muted-foreground text-[11px] leading-relaxed">
                        Applies Cascade rule syntax, file target trees, and test-driven development checkpoints.
                      </p>
                    </div>
                    <div className="p-4 rounded-xl border border-border bg-card/60 space-y-1">
                      <h4 className="font-bold text-foreground">Generic Markdown</h4>
                      <p className="text-muted-foreground text-[11px] leading-relaxed">
                        Clean standard GitHub Markdown structure compatible with any web LLM or developer interface.
                      </p>
                    </div>
                  </div>
                </section>

                {/* CHAPTER 4: REST API REFERENCE */}
                <section className="space-y-4">
                  <h2 className="text-xl font-bold text-foreground flex items-center gap-2">
                    <Code className="h-5 w-5 text-emerald-500" />
                    <span>4. Sidecar REST API Contract</span>
                  </h2>
                  <div className="overflow-x-auto rounded-2xl border border-border">
                    <table className="w-full text-left text-xs border-collapse">
                      <thead>
                        <tr className="bg-muted/40 border-b border-border text-muted-foreground font-mono">
                          <th className="p-3 font-semibold">Method</th>
                          <th className="p-3 font-semibold">Endpoint</th>
                          <th className="p-3 font-semibold">Description</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-border/60 font-mono text-[11px]">
                        <tr>
                          <td className="p-3 font-bold text-emerald-500">GET</td>
                          <td className="p-3 text-foreground">/api/health</td>
                          <td className="p-3 text-muted-foreground font-sans">Returns sidecar readiness and service status.</td>
                        </tr>
                        <tr>
                          <td className="p-3 font-bold text-primary">POST</td>
                          <td className="p-3 text-foreground">/api/compile</td>
                          <td className="p-3 text-muted-foreground font-sans">Main compilation endpoint with context injection.</td>
                        </tr>
                        <tr>
                          <td className="p-3 font-bold text-primary">POST</td>
                          <td className="p-3 text-foreground">/api/interview/start</td>
                          <td className="p-3 text-muted-foreground font-sans">Initializes adaptive clarification questionnaire.</td>
                        </tr>
                        <tr>
                          <td className="p-3 font-bold text-emerald-500">GET</td>
                          <td className="p-3 text-foreground">/api/projects</td>
                          <td className="p-3 text-muted-foreground font-sans">Lists managed project repositories and vector stats.</td>
                        </tr>
                        <tr>
                          <td className="p-3 font-bold text-primary">POST</td>
                          <td className="p-3 text-foreground">/api/documents/ingest-directory</td>
                          <td className="p-3 text-muted-foreground font-sans">Chunks and embeds project folder files into sqlite-vec.</td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                </section>
              </div>
            )}
          </article>

          {/* =================================================================== */}
          {/* BOTTOM PAGINATION NAVIGATION */}
          {/* =================================================================== */}
          <footer className="pt-8 mt-12 border-t border-border/80 flex items-center justify-between gap-4">
            {prevDoc ? (
              <Link
                to={prevDoc.path}
                className="flex items-center gap-2 px-4 py-2.5 rounded-xl border border-border bg-card/70 hover:bg-card text-xs font-semibold text-foreground transition-all hover:-translate-x-0.5 shadow-2xs"
              >
                <ArrowLeft className="h-4 w-4 text-muted-foreground" />
                <div className="text-left">
                  <span className="text-[10px] text-muted-foreground font-mono block">Previous</span>
                  <span>{prevDoc.title}</span>
                </div>
              </Link>
            ) : <div />}

            {nextDoc && (
              <Link
                to={nextDoc.path}
                className="flex items-center gap-2 px-4 py-2.5 rounded-xl border border-border bg-card/70 hover:bg-card text-xs font-semibold text-foreground transition-all hover:translate-x-0.5 shadow-2xs text-right"
              >
                <div>
                  <span className="text-[10px] text-muted-foreground font-mono block">Next</span>
                  <span>{nextDoc.title}</span>
                </div>
                <ArrowRight className="h-4 w-4 text-muted-foreground" />
              </Link>
            )}
          </footer>
        </main>
      </div>
    </div>
  );
};

export default DocsView;
