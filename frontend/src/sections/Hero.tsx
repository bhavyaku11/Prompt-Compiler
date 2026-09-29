import { useNavigate } from 'react-router-dom';
import { useAuth } from '@clerk/react';
import { Terminal, ArrowUpRight, Sparkles, CheckCircle2, ShieldCheck, Cpu } from 'lucide-react';
import { GithubIcon } from '@/components/ui/icons';
import { MagneticButton } from '@/components/ui/magnetic-button';
import { getDesktopToken } from '@/api/auth';

export const Hero = () => {
  const navigate = useNavigate();
  const { isSignedIn } = useAuth();
  const isAuthed = isSignedIn || Boolean(getDesktopToken());

  const handleStartCompiling = () => {
    navigate(isAuthed ? '/studio' : '/auth');
  };


  return (
    <section className="relative z-10 flex min-h-[calc(100vh-68px)] flex-col items-center justify-center px-6 pt-6 pb-6 sm:pt-10 sm:pb-8 max-w-5xl mx-auto w-full text-center">
      {/* Main Headline */}
      <div className="mb-4 sm:mb-5">
        <h1 className="text-4xl sm:text-6xl md:text-7xl font-bold tracking-tight leading-[1.02] text-foreground">
          Turn rough ideas into <br className="hidden sm:inline" />
          <span className="text-neutral-600 dark:text-neutral-400">implementation-ready prompts.</span>
        </h1>
      </div>

      {/* Supporting Text */}
      <p className="max-w-2xl text-base sm:text-lg text-neutral-600 dark:text-neutral-400 leading-relaxed font-normal mb-6">
        Extract confirmed requirements, eliminate hallucinations, and compile structured prompts for AI coding agents.
      </p>

      {/* Call to Action Buttons: Styled using Footer Glass Pill Theme with Magnetic Floating Effect */}
      <div className="flex flex-col sm:flex-row items-center justify-center gap-4 w-full sm:w-auto mb-6">
        {/* Primary CTA - Start Compiling */}
        <MagneticButton
          as="button"
          type="button"
          onClick={handleStartCompiling}
          aria-label="Start Compiling Prompts"
          className="footer-glass-pill group relative flex h-13 sm:h-14 w-full sm:w-auto min-w-[210px] items-center justify-center gap-3 rounded-full px-8 text-base font-semibold shadow-xl transition-colors duration-200"
        >
          <Terminal className="h-5 w-5 text-neutral-800 dark:text-neutral-200 group-hover:scale-110 transition-transform duration-200 stroke-[2.2] pointer-events-none" />
          <span className="pointer-events-none">Start Compiling</span>
          <Sparkles className="h-4 w-4 text-emerald-500 dark:text-emerald-400 group-hover:rotate-12 transition-transform duration-200 pointer-events-none" />
        </MagneticButton>

        {/* Secondary CTA - View on GitHub */}
        <MagneticButton
          as="a"
          href="https://github.com/bhavyaku11/Prompt-Compiler"
          target="_blank"
          rel="noopener noreferrer"
          aria-label="View on GitHub"
          className="footer-glass-pill group relative flex h-13 sm:h-14 w-full sm:w-auto min-w-[190px] items-center justify-center gap-3 rounded-full px-8 text-base font-semibold shadow-xl transition-colors duration-200"
        >
          <GithubIcon className="h-5 w-5 text-neutral-700 dark:text-neutral-300 group-hover:text-black dark:group-hover:text-white transition-colors pointer-events-none" />
          <span className="pointer-events-none">View on GitHub</span>
          <ArrowUpRight className="h-4 w-4 text-neutral-500 dark:text-neutral-400 group-hover:translate-x-0.5 group-hover:-translate-y-0.5 transition-transform pointer-events-none" />
        </MagneticButton>
      </div>

      {/* The High-Contrast Interactive Transformation Showcase Block */}
      {/* Dynamic contrast: dark card on light background, white card on dark background */}
      <div 
        data-magnetic
        role="button"
        tabIndex={0}
        onClick={handleStartCompiling}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            handleStartCompiling();
          }
        }}
        aria-label="Open Studio - Rough Idea to Agent Prompt"
        className="relative flex h-18 sm:h-20 w-full max-w-md sm:max-w-lg items-center justify-between overflow-hidden rounded-2xl bg-neutral-900 text-white dark:bg-white dark:text-black px-6 sm:px-8 shadow-2xl mb-6 transition-transform duration-200 hover:scale-[1.02] cursor-pointer group border border-neutral-800 dark:border-white/20 select-none"
      >
        <span className="text-lg sm:text-xl font-bold tracking-tight text-white dark:text-black text-left pointer-events-none">
          Rough Idea → Agent Prompt
        </span>

        {/* Inverted icon circle */}
        <div className="flex h-11 w-11 sm:h-12 sm:w-12 shrink-0 items-center justify-center rounded-full bg-white text-black dark:bg-black dark:text-white transition-transform duration-200 group-hover:scale-105 ml-4 pointer-events-none">
          <ArrowUpRight className="h-5 w-5 stroke-[2]" />
        </div>
      </div>

      {/* Agent Presets & Value Pillars */}
      <div className="flex flex-wrap items-center justify-center gap-2 sm:gap-3 text-xs font-mono text-neutral-600 dark:text-neutral-400 mb-5">
        <span className="text-neutral-900 dark:text-neutral-200 font-semibold flex items-center gap-1.5">
          <Cpu className="h-3.5 w-3.5 text-neutral-700 dark:text-neutral-300" />
          Target Agent Presets:
        </span>
        {['Cursor', 'Claude Code', 'Antigravity', 'Windsurf', 'Codex'].map((agent) => (
          <span 
            key={agent}
            data-magnetic
            className="px-3 py-1 rounded-md border border-neutral-300 dark:border-white/10 bg-neutral-100 dark:bg-white/[0.04] text-neutral-800 dark:text-neutral-200 hover:border-neutral-400 dark:hover:border-white/25 hover:text-black dark:hover:text-white transition-colors cursor-default"
          >
            {agent}
          </span>
        ))}
      </div>

      {/* Trust & Guarantee indicators */}
      <div className="flex flex-wrap items-center justify-center gap-6 sm:gap-8 text-xs text-neutral-800 dark:text-neutral-200 font-medium">
        <div className="flex items-center gap-2">
          <CheckCircle2 className="h-4 w-4 text-emerald-600 dark:text-emerald-400" />
          <span>Local Ollama Engine</span>
        </div>
        <div className="flex items-center gap-2">
          <ShieldCheck className="h-4 w-4 text-emerald-600 dark:text-emerald-400" />
          <span>Strict Precedence</span>
        </div>
        <div className="flex items-center gap-2">
          <Sparkles className="h-4 w-4 text-emerald-600 dark:text-emerald-400" />
          <span>Deterministic Memory</span>
        </div>
      </div>

    </section>
  );
};

export default Hero;
