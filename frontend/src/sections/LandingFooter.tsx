import { useNavigate } from "react-router-dom";
import { MotionFooter, MagneticButton } from "@/components/ui/motion-footer";
import { GithubIcon } from "@/components/ui/icons";
import { Terminal, ArrowUpRight, Sparkles } from "lucide-react";

export function LandingFooter() {
  const navigate = useNavigate();
  const marqueeItems = (
    <div className="flex items-center space-x-12 px-6">
      <span className="text-neutral-900 dark:text-neutral-200 font-bold">PROMPT COMPILER</span>
      <span className="text-neutral-400 dark:text-neutral-500">✦</span>
      <span className="text-neutral-900 dark:text-neutral-200 font-bold">LOCAL-FIRST AI</span>
      <span className="text-neutral-400 dark:text-neutral-500">✦</span>
      <span className="text-neutral-900 dark:text-neutral-200 font-bold">PRIVATE BY DEFAULT</span>
      <span className="text-neutral-400 dark:text-neutral-500">✦</span>
      <span className="text-neutral-900 dark:text-neutral-200 font-bold">BUILT FOR DEVELOPERS</span>
      <span className="text-neutral-400 dark:text-neutral-500">✦</span>
      <span className="text-neutral-900 dark:text-neutral-200 font-bold">FROM IDEA TO IMPLEMENTATION</span>
      <span className="text-neutral-400 dark:text-neutral-500">✦</span>
      <span className="text-neutral-900 dark:text-neutral-200 font-bold">COMPILE WITH CLARITY</span>
      <span className="text-neutral-400 dark:text-neutral-500">✦</span>
    </div>
  );

  const handleStartCompiling = () => {
    // Smoothly scroll back to top hero to begin prompt compilation
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const primaryActions = (
    <div className="flex flex-wrap items-center justify-center gap-4 w-full">
      {/* Primary Action Button */}
      <MagneticButton
        as="button"
        type="button"
        onClick={handleStartCompiling}
        className="footer-glass-pill px-8 sm:px-10 py-3.5 sm:py-4 rounded-full font-semibold text-sm md:text-base flex items-center gap-3 group hover:text-black dark:hover:text-white"
      >
        <Terminal className="w-5 h-5 text-neutral-800 dark:text-neutral-200 group-hover:scale-110 transition-transform duration-200 stroke-[2.2]" />
        <span>Start Compiling</span>
        <Sparkles className="w-4 h-4 text-emerald-500 dark:text-emerald-400 group-hover:rotate-12 transition-transform duration-200" />
      </MagneticButton>

      {/* Secondary Action Link */}
      <MagneticButton
        as="a"
        href="https://github.com/bhavyaku11/Prompt-Compiler"
        target="_blank"
        rel="noopener noreferrer"
        className="footer-glass-pill px-8 sm:px-10 py-3.5 sm:py-4 rounded-full text-neutral-800 dark:text-neutral-200 font-semibold text-sm md:text-base flex items-center gap-3 group hover:text-black dark:hover:text-white"
      >
        <GithubIcon className="w-4.5 h-4.5 text-neutral-400 dark:text-neutral-300 group-hover:text-black dark:group-hover:text-white transition-colors" />
        <span>View on GitHub</span>
        <ArrowUpRight className="w-3.5 h-3.5 text-neutral-500 dark:text-neutral-400 group-hover:translate-x-0.5 group-hover:-translate-y-0.5 transition-transform" />
      </MagneticButton>
    </div>
  );

  const secondaryLinks = (
    <div className="flex flex-wrap items-center justify-center gap-2 sm:gap-4 md:gap-6 w-full mt-2">
      <MagneticButton
        as="button"
        type="button"
        onClick={() => navigate("/docs/product")}
        className="footer-glass-pill px-5 py-2.5 rounded-full text-neutral-600 dark:text-neutral-400 font-medium text-xs md:text-sm hover:text-black dark:hover:text-white cursor-pointer transition-colors"
      >
        Product
      </MagneticButton>

      <MagneticButton
        as="button"
        type="button"
        onClick={() => navigate("/docs/workflow")}
        className="footer-glass-pill px-5 py-2.5 rounded-full text-neutral-600 dark:text-neutral-400 font-medium text-xs md:text-sm hover:text-black dark:hover:text-white cursor-pointer transition-colors"
      >
        Workflow
      </MagneticButton>

      <MagneticButton
        as="button"
        type="button"
        onClick={() => navigate("/docs/architecture")}
        className="footer-glass-pill px-5 py-2.5 rounded-full text-neutral-600 dark:text-neutral-400 font-medium text-xs md:text-sm hover:text-black dark:hover:text-white cursor-pointer transition-colors"
      >
        Architecture
      </MagneticButton>

      <MagneticButton
        as="a"
        href="https://github.com/bhavyaku11/Prompt-Compiler"
        target="_blank"
        rel="noopener noreferrer"
        className="footer-glass-pill px-5 py-2.5 rounded-full text-neutral-600 dark:text-neutral-400 font-medium text-xs md:text-sm hover:text-black dark:hover:text-white cursor-pointer transition-colors"
      >
        GitHub
      </MagneticButton>

      <MagneticButton
        as="button"
        type="button"
        onClick={() => navigate("/docs/documentation")}
        className="footer-glass-pill px-5 py-2.5 rounded-full text-neutral-600 dark:text-neutral-400 font-medium text-xs md:text-sm hover:text-black dark:hover:text-white cursor-pointer transition-colors"
      >
        Documentation
      </MagneticButton>
    </div>
  );

  const badgeText = (
    <>
      <span className="flex h-1.5 w-1.5 rounded-full bg-emerald-500 dark:bg-emerald-400 animate-pulse" />
      <span className="text-neutral-600 dark:text-neutral-300 text-[10px] md:text-xs font-mono font-medium tracking-wider uppercase">
        Local Engine • Offline First
      </span>
    </>
  );

  return (
    <MotionFooter
      marqueeItems={marqueeItems}
      headingText="Ready to compile?"
      subheadingText="Transform rough ideas into canonical, implementation-ready prompts with local vector memory."
      giantBackgroundText="COMPILE"
      primaryActions={primaryActions}
      secondaryLinks={secondaryLinks}
      copyrightText="© 2026 PROMPT COMPILER. ALL RIGHTS RESERVED."
      badgeText={badgeText}
      onScrollToTop={() => window.scrollTo({ top: 0, behavior: "smooth" })}
    />
  );
}

export default LandingFooter;
