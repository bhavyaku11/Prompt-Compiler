"use client";

import * as React from "react";
import { useEffect, useRef } from "react";
import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { MagneticButton } from "@/components/ui/magnetic-button";

// Register ScrollTrigger safely for React / browser environment
if (typeof window !== "undefined") {
  gsap.registerPlugin(ScrollTrigger);
}

// -------------------------------------------------------------------------
// 1. THEME-ADAPTIVE INLINE STYLES (Supports Light Mode & Dark Mode)
// -------------------------------------------------------------------------
const STYLES = `
@keyframes footer-breathe {
  0% { transform: translate(-50%, -50%) scale(1); opacity: 0.6; }
  100% { transform: translate(-50%, -50%) scale(1.12); opacity: 0.9; }
}

@keyframes footer-scroll-marquee {
  from { transform: translateX(0); }
  to { transform: translateX(-50%); }
}

.animate-footer-breathe {
  animation: footer-breathe 8s ease-in-out infinite alternate;
}

.animate-footer-scroll-marquee {
  animation: footer-scroll-marquee 35s linear infinite;
}

/* Developer Grid Pattern in Footer matching 21st.dev reference */
.footer-bg-grid {
  background-size: 52px 52px;
  background-image: 
    linear-gradient(to right, rgba(0, 0, 0, 0.045) 1px, transparent 1px),
    linear-gradient(to bottom, rgba(0, 0, 0, 0.045) 1px, transparent 1px);
  mask-image: radial-gradient(ellipse 90% 85% at 50% 50%, #000 50%, rgba(0, 0, 0, 0.5) 85%, transparent 100%);
  -webkit-mask-image: radial-gradient(ellipse 90% 85% at 50% 50%, #000 50%, rgba(0, 0, 0, 0.5) 85%, transparent 100%);
}

.dark .footer-bg-grid {
  background-image: 
    linear-gradient(to right, rgba(255, 255, 255, 0.045) 1px, transparent 1px),
    linear-gradient(to bottom, rgba(255, 255, 255, 0.045) 1px, transparent 1px);
}

/* Ambient Neutral Monochrome Spotlight (Matching 21st.dev reference) */
.footer-aurora {
  background: radial-gradient(
    ellipse 65% 55% at 50% 45%, 
    rgba(0, 0, 0, 0.04) 0%, 
    rgba(0, 0, 0, 0.01) 45%, 
    transparent 75%
  );
}

.dark .footer-aurora {
  background: radial-gradient(
    ellipse 65% 55% at 50% 45%, 
    rgba(255, 255, 255, 0.075) 0%, 
    rgba(255, 255, 255, 0.018) 45%, 
    transparent 75%
  );
}

/* Glass Pill Theming */
.footer-glass-pill {
  background: linear-gradient(145deg, rgba(0, 0, 0, 0.035) 0%, rgba(0, 0, 0, 0.015) 100%);
  box-shadow: 
      0 10px 30px -10px rgba(0, 0, 0, 0.08), 
      inset 0 1px 1px rgba(255, 255, 255, 0.9), 
      inset 0 -1px 2px rgba(0, 0, 0, 0.04);
  border: 1px solid rgba(0, 0, 0, 0.09);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  transition: all 0.35s cubic-bezier(0.16, 1, 0.3, 1);
  color: #18181b;
}

.footer-glass-pill:hover {
  background: linear-gradient(145deg, rgba(0, 0, 0, 0.06) 0%, rgba(0, 0, 0, 0.02) 100%);
  border-color: rgba(0, 0, 0, 0.2);
  box-shadow: 
      0 20px 40px -10px rgba(0, 0, 0, 0.12), 
      inset 0 1px 1px rgba(255, 255, 255, 1);
  color: #000000;
}

.dark .footer-glass-pill {
  background: linear-gradient(145deg, rgba(255, 255, 255, 0.04) 0%, rgba(255, 255, 255, 0.015) 100%);
  box-shadow: 
      0 10px 30px -10px rgba(0, 0, 0, 0.6), 
      inset 0 1px 1px rgba(255, 255, 255, 0.12), 
      inset 0 -1px 2px rgba(0, 0, 0, 0.8);
  border: 1px solid rgba(255, 255, 255, 0.12);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  color: #f3f4f6;
}

.dark .footer-glass-pill:hover {
  background: linear-gradient(145deg, rgba(255, 255, 255, 0.08) 0%, rgba(255, 255, 255, 0.025) 100%);
  border-color: rgba(255, 255, 255, 0.25);
  box-shadow: 
      0 20px 40px -10px rgba(0, 0, 0, 0.8), 
      inset 0 1px 1px rgba(255, 255, 255, 0.25);
  color: #ffffff;
}

/* Giant Background Text Masking: Solid volumetric fill matching SOBERS in 21st.dev */
.footer-giant-bg-text {
  font-size: 23vw;
  line-height: 0.74;
  font-weight: 900;
  letter-spacing: -0.04em;
  color: transparent;
  background: linear-gradient(180deg, rgba(0, 0, 0, 0.08) 0%, rgba(0, 0, 0, 0.02) 75%, transparent 100%);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
}

.dark .footer-giant-bg-text {
  color: transparent;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.12) 0%, rgba(255, 255, 255, 0.025) 75%, transparent 100%);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
}

/* Metallic Chrome Title Fill matching Ready to begin? in 21st.dev */
.footer-text-glow {
  color: #09090b;
}

.dark .footer-text-glow {
  color: #ffffff;
}

@supports (-webkit-background-clip: text) {
  .footer-text-glow {
    background: linear-gradient(180deg, #09090b 10%, #27272a 45%, #52525b 75%, #71717a 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
  }
  .dark .footer-text-glow {
    background: linear-gradient(180deg, #ffffff 15%, #e2e8f0 45%, #94a3b8 72%, #475569 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    filter: drop-shadow(0px 2px 20px rgba(0, 0, 0, 0.9)) drop-shadow(0px 0px 30px rgba(255, 255, 255, 0.15));
  }
}
`;

// -------------------------------------------------------------------------
// 2. MAGNETIC BUTTON PRIMITIVE (Re-exported from shared UI component)
// -------------------------------------------------------------------------
export { MagneticButton, type MagneticButtonProps } from "@/components/ui/magnetic-button";


// -------------------------------------------------------------------------
// 3. CINEMATIC FOOTER BASE COMPONENT
// -------------------------------------------------------------------------
export interface MotionFooterProps {
  marqueeItems?: React.ReactNode;
  headingText?: string;
  subheadingText?: string;
  giantBackgroundText?: string;
  primaryActions?: React.ReactNode;
  secondaryLinks?: React.ReactNode;
  copyrightText?: string;
  badgeText?: React.ReactNode;
  onScrollToTop?: () => void;
}

export function MotionFooter({
  marqueeItems,
  headingText = "Ready to compile?",
  subheadingText = "Turn rough requirements into deterministic, implementation-ready prompts.",
  giantBackgroundText = "COMPILE",
  primaryActions,
  secondaryLinks,
  copyrightText = "© 2026 Prompt Compiler. All rights reserved.",
  badgeText,
  onScrollToTop,
}: MotionFooterProps) {
  const wrapperRef = useRef<HTMLDivElement>(null);
  const giantTextRef = useRef<HTMLDivElement>(null);
  const headingRef = useRef<HTMLDivElement>(null);
  const linksRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (typeof window === "undefined") return;
    if (!wrapperRef.current) return;

    const prefersReduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (prefersReduced) {
      if (giantTextRef.current) gsap.set(giantTextRef.current, { opacity: 1, scale: 1, y: 0 });
      if (headingRef.current) gsap.set(headingRef.current, { opacity: 1, y: 0 });
      if (linksRef.current) gsap.set(linksRef.current, { opacity: 1, y: 0 });
      return;
    }

    const ctx = gsap.context(() => {
      // Background Parallax on giant typography
      gsap.fromTo(
        giantTextRef.current,
        { y: "12vh", scale: 0.85, opacity: 0 },
        {
          y: "0vh",
          scale: 1,
          opacity: 1,
          ease: "power1.out",
          scrollTrigger: {
            trigger: wrapperRef.current,
            start: "top 85%",
            end: "bottom bottom",
            scrub: 1,
          },
        }
      );

      // Content Reveal triggered smoothly when footer enters view
      gsap.fromTo(
        [headingRef.current, linksRef.current],
        { y: 30, opacity: 0 },
        {
          y: 0,
          opacity: 1,
          stagger: 0.15,
          duration: 0.7,
          ease: "power2.out",
          scrollTrigger: {
            trigger: wrapperRef.current,
            start: "top 85%",
            toggleActions: "play none none reverse",
          },
        }
      );
    }, wrapperRef);

    return () => ctx.revert();
  }, []);

  const defaultScrollToTop = () => {
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const handleScrollTop = onScrollToTop || defaultScrollToTop;

  return (
    <>
      <style dangerouslySetInnerHTML={{ __html: STYLES }} />
      
      {/* 
        The "Curtain Reveal" Wrapper:
        It sits in standard flow. Because it has clip-path, its contents
        are ONLY visible within its bounding box as the user scrolls down.
      */}
      <div
        ref={wrapperRef}
        className="relative h-screen min-h-[640px] w-full"
        style={{ clipPath: "polygon(0% 0, 100% 0%, 100% 100%, 0 100%)" }}
      >
        {/* The actual footer stays fixed to the viewport underneath everything */}
        <footer className="fixed bottom-0 left-0 flex h-screen min-h-[640px] w-full flex-col justify-between overflow-hidden bg-white dark:bg-[#000000] text-foreground transition-colors duration-300">
          
          {/* Ambient Light & Grid Background */}
          <div className="footer-aurora absolute left-1/2 top-1/2 h-[60vh] w-[80vw] -translate-x-1/2 -translate-y-1/2 animate-footer-breathe rounded-[50%] blur-[80px] pointer-events-none z-0" />
          <div className="footer-bg-grid absolute inset-0 z-0 pointer-events-none" />

          {/* Giant background text (COMPILE) matching 21st.dev reference */}
          <div
            ref={giantTextRef}
            className="footer-giant-bg-text absolute -bottom-[3vh] sm:-bottom-[4vh] left-1/2 -translate-x-1/2 whitespace-nowrap z-0 pointer-events-none select-none tracking-tighter"
          >
            {giantBackgroundText}
          </div>

          {/* 1. Diagonal Sleek Marquee (Top of footer) */}
          <div className="absolute top-10 left-0 w-full overflow-hidden border-y border-neutral-300 dark:border-white/10 bg-white/95 dark:bg-[#050505]/95 backdrop-blur-md py-3.5 z-10 -rotate-1 scale-105 shadow-xl transition-colors duration-300">
            <div className="flex w-max animate-footer-scroll-marquee text-xs md:text-sm font-bold tracking-[0.28em] text-neutral-800 dark:text-neutral-200 uppercase select-none">
              {marqueeItems}
              {marqueeItems}
            </div>
          </div>

          {/* 2. Main Center Content */}
          <div className="relative z-10 flex flex-1 flex-col items-center justify-center px-6 mt-16 sm:mt-20 w-full max-w-5xl mx-auto text-center">
            <div ref={headingRef} className="space-y-4 mb-10">
              <h2 className="text-5xl sm:text-7xl md:text-8xl font-black footer-text-glow tracking-tighter text-center">
                {headingText}
              </h2>
              {subheadingText && (
                <p className="max-w-xl mx-auto text-sm sm:text-base md:text-lg text-neutral-700 dark:text-neutral-300 font-normal leading-relaxed">
                  {subheadingText}
                </p>
              )}
            </div>

            {/* Interactive Magnetic Pills Layout */}
            <div ref={linksRef} className="flex flex-col items-center gap-6 w-full">
              {/* Primary Actions */}
              {primaryActions}

              {/* Secondary Navigation Links */}
              {secondaryLinks}
            </div>
          </div>

          {/* 3. Bottom Bar / Credits (Seamless, floating directly over giant background text and grid) */}
          <div className="relative z-20 w-full pb-8 px-6 md:px-12 flex flex-col md:flex-row items-center justify-between gap-6">
            
            {/* Copyright */}
            <div className="text-neutral-600 dark:text-neutral-300 text-[10px] md:text-xs font-mono font-semibold tracking-widest uppercase order-2 md:order-1">
              {copyrightText}
            </div>

            {/* Status / Feature Badge */}
            <div className="footer-glass-pill px-6 py-3 rounded-full flex items-center gap-2 order-1 md:order-2 cursor-default">
              {badgeText}
            </div>

            {/* Back to top */}
            <MagneticButton
              as="button"
              type="button"
              onClick={handleScrollTop}
              aria-label="Scroll back to top"
              className="w-12 h-12 rounded-full footer-glass-pill flex items-center justify-center text-neutral-700 dark:text-neutral-300 hover:text-black dark:hover:text-white group order-3"
            >
              <svg className="w-5 h-5 transform group-hover:-translate-y-1.5 transition-transform duration-300 stroke-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 10l7-7m0 0l7 7m-7-7v18" />
              </svg>
            </MagneticButton>

          </div>
        </footer>
      </div>
    </>
  );
}

export default MotionFooter;
