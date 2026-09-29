// --- Component ---
// Built using Hyperiux Vault: https://vault.hyperiux.com
// Adapted for Prompt Compiler: deterministic horizontal pinned scrub workflow visualization
"use client";

import {
  type CSSProperties,
  useLayoutEffect,
  useMemo,
  useRef,
  useSyncExternalStore,
} from "react";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import defaultWorkflowImage from "@/assets/workflow-showcase.png";
import { Layers } from "lucide-react";

if (typeof window !== "undefined") {
  gsap.registerPlugin(ScrollTrigger);
}

export type JourneyItem = {
  id: string;
  step?: string;
  title: string;
  content: string;
  year?: string;
  month?: string;
};

export type TimelineProps = {
  eyebrow?: string;
  headline?: React.ReactNode;
  subtitle?: string;
  title?: string;
  periodLabel?: string;
  textColor?: string;
  mutedTextColor?: string;
  activeColor?: string;
  backgroundColor?: string;
  imageUrl?: string;
  imageAlt?: string;
  /** Reveal animation duration, in seconds. */
  duration?: number;
  /** Fallback reveal duration when `duration` is omitted, in seconds. */
  scrollDuration?: number;
  /** Top-row journey milestones (default: steps 01, 03, 05) */
  topItems?: JourneyItem[];
  /** Bottom-row journey milestones (default: steps 02, 04, 06) */
  bottomItems?: JourneyItem[];
};

const REDUCED_MOTION_QUERY = "(prefers-reduced-motion: reduce)";

function subscribeToReducedMotion(callback: () => void) {
  if (typeof window === "undefined") return () => {};

  const mediaQueryList = window.matchMedia(REDUCED_MOTION_QUERY);
  mediaQueryList.addEventListener("change", callback);

  return () => mediaQueryList.removeEventListener("change", callback);
}

function getReducedMotionSnapshot() {
  if (typeof window === "undefined") return false;

  return window.matchMedia?.(REDUCED_MOTION_QUERY)?.matches ?? false;
}

function getServerReducedMotionSnapshot() {
  return false;
}

function usePrefersReducedMotion() {
  return useSyncExternalStore(
    subscribeToReducedMotion,
    getReducedMotionSnapshot,
    getServerReducedMotionSnapshot,
  );
}

const internalTopJourneyData: JourneyItem[] = [
  {
    id: "step-01",
    step: "01",
    title: "Describe",
    year: "Step 01",
    month: "Describe",
    content: "Start with a rough idea, requirement, feature request, or problem statement.",
  },
  {
    id: "step-03",
    step: "03",
    title: "Add Context",
    year: "Step 03",
    month: "Add Context",
    content: "Inject confirmed project memory, architecture contracts, and local vector knowledge.",
  },
  {
    id: "step-05",
    step: "05",
    title: "Target Agent",
    year: "Step 05",
    month: "Target Agent",
    content: "Format deterministically for your selected AI agent: Cursor, Claude Code, Antigravity, Windsurf, or Codex.",
  },
];

const internalBottomJourneyData: JourneyItem[] = [
  {
    id: "step-02",
    step: "02",
    title: "Understand",
    year: "Step 02",
    month: "Understand",
    content: "Separate explicit requirements from missing information and safe architectural assumptions.",
  },
  {
    id: "step-04",
    step: "04",
    title: "Compile",
    year: "Step 04",
    month: "Compile",
    content: "Transform structured requirements into a clear, canonical, implementation-ready prompt.",
  },
  {
    id: "step-06",
    step: "06",
    title: "Refine",
    year: "Step 06",
    month: "Refine",
    content: "Validate constraints, anti-hallucination bounds, and contracts before returning the prompt.",
  },
];

export default function Timeline({
  eyebrow,
  headline,
  subtitle,
  title = "Compiler Pipeline",
  periodLabel = "Workflow 01 — 06",
  textColor = "var(--color-foreground, #f8fafc)",
  mutedTextColor = "var(--color-muted-foreground, #a1a1aa)",
  activeColor = "#ffffff",
  backgroundColor = "#000000",
  imageUrl = defaultWorkflowImage,
  imageAlt = "Prompt Compiler workflow architecture visual",
  topItems = internalTopJourneyData,
  bottomItems = internalBottomJourneyData,
}: TimelineProps) {
  const sectionRef = useRef<HTMLElement>(null);
  const wholeSliderRef = useRef<HTMLDivElement>(null);
  const reducedMotion = usePrefersReducedMotion();

  const sectionStyle: CSSProperties = {
    color: textColor,
    backgroundColor,
  };
  const activeStyle: CSSProperties = {
    backgroundColor: activeColor,
  };
  const mutedTextStyle: CSSProperties = {
    color: mutedTextColor,
  };

  const allJourneyItems: JourneyItem[] = useMemo(() => {
    return [...topItems, ...bottomItems].sort((a, b) => {
      const aOrder = parseInt(a.step || a.id.replace(/\D/g, "") || "0", 10);
      const bOrder = parseInt(b.step || b.id.replace(/\D/g, "") || "0", 10);
      return aOrder - bOrder;
    });
  }, [topItems, bottomItems]);

  useLayoutEffect(() => {
    const section = sectionRef.current;
    const slider = wholeSliderRef.current;
    if (!section || !slider) return;

    // Use gsap.context to collect and cleanly revert all tweens & ScrollTriggers
    const ctx = gsap.context(() => {
      const isMobile = window.innerWidth < 600;

      // Exact pixel translation needed so that the entire horizontal track travels across the screen
      const getScrollDistance = () => {
        const totalWidth = slider.scrollWidth;
        const viewWidth = window.innerWidth;
        const extraPadding = isMobile ? 40 : 120;
        return Math.max(0, totalWidth - viewWidth + extraPadding);
      };

      // Set initial states
      if (reducedMotion) {
        gsap.set(".journey-line", { width: "98%" });
        allJourneyItems.forEach((item) => {
          gsap.set(`.jl-${item.id}`, { scaleY: 1 });
          gsap.set(`.jd-${item.id}`, { scale: 1 });
          gsap.set(`.card-content-${item.id}`, { opacity: 1, y: 0, scale: 1 });
        });
      } else {
        gsap.set(".journey-line", { width: "0%" });
        allJourneyItems.forEach((item) => {
          const isTop = topItems.some((topItem) => topItem.id === item.id);
          gsap.set(`.jl-${item.id}`, {
            scaleY: 0,
            transformOrigin: isTop ? "bottom center" : "top center",
          });
          gsap.set(`.jd-${item.id}`, { scale: 0, transformOrigin: "center center" });
          // Initially hide all cards so they reveal strictly one by one as user scrolls down
          gsap.set(`.card-content-${item.id}`, {
            opacity: 0,
            y: isTop ? -28 : 28,
            scale: 0.92,
          });
        });
      }

      // Master Timeline pinned to the viewport
      // As the user scrolls downwards, ScrollTrigger holds the section in place
      // and converts vertical scroll distance directly into horizontal movement!
      const masterTl = gsap.timeline({
        scrollTrigger: {
          trigger: section,
          pin: true,
          start: "top top",
          end: () => `+=${Math.max(1400, getScrollDistance() * (isMobile ? 1.5 : 1.35))}`,
          scrub: 0.8,
          invalidateOnRefresh: true,
          anticipatePin: 1,
        },
        defaults: {
          ease: "none",
        },
      });

      // 1. Horizontal track slides to the left
      masterTl.to(slider, {
        x: () => -getScrollDistance(),
        ease: "none",
        duration: 1,
      }, 0);

      // 2. Center connecting line draws horizontally across the track
      if (!reducedMotion) {
        masterTl.to(".journey-line", {
          width: isMobile ? "82%" : "98%",
          ease: "none",
          duration: 0.85,
        }, 0);

        // 3. Stagger milestone reveals one by one as the scroll reaches each card
        const totalItems = Math.max(1, allJourneyItems.length);
        allJourneyItems.forEach((item, index) => {
          const isTop = topItems.some((topItem) => topItem.id === item.id);
          // Distributed evenly along timeline progress from 0.05 to 0.78
          const itemStart = 0.05 + (index / totalItems) * 0.72;
          const itemDuration = 0.10;

          // Stem line grows from the central rail to the card
          masterTl.fromTo(`.jl-${item.id}`,
            { scaleY: 0 },
            {
              scaleY: 1,
              duration: itemDuration * 0.7,
              ease: "power2.out",
            },
            itemStart
          );

          // Dot pops in
          masterTl.fromTo(`.jd-${item.id}`,
            { scale: 0 },
            {
              scale: 1,
              duration: itemDuration * 0.7,
              ease: "back.out(2)",
            },
            itemStart + itemDuration * 0.2
          );

          // Card content (badge, title, description) smoothly fades and glides in
          masterTl.fromTo(`.card-content-${item.id}`,
            {
              opacity: 0,
              y: isTop ? -28 : 28,
              scale: 0.92,
            },
            {
              opacity: 1,
              y: 0,
              scale: 1,
              duration: itemDuration,
              ease: "power2.out",
            },
            itemStart + itemDuration * 0.15
          );
        });
      }
    }, section);

    // Refresh ScrollTrigger when images load and on window resize
    const handleResize = () => {
      ScrollTrigger.refresh();
    };

    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      ctx.revert();
    };
  }, [reducedMotion, allJourneyItems, topItems, bottomItems]);

  return (
    <section
      ref={sectionRef}
      id="workflow-timeline"
      className="relative w-full h-screen overflow-hidden select-none bg-background transition-colors duration-300 flex flex-col justify-between py-4 sm:py-6"
      style={sectionStyle}
    >
      {/* Pinned Section Header */}
      {(eyebrow || headline || subtitle) && (
        <div className="w-full px-6 max-w-4xl mx-auto text-center shrink-0 z-20 pt-1 sm:pt-2">
          {eyebrow && (
            <div 
              data-magnetic
              className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-neutral-300 dark:border-white/15 bg-neutral-100/90 dark:bg-white/[0.06] text-neutral-800 dark:text-neutral-200 mb-2 backdrop-blur-sm"
            >
              <Layers className="h-3.5 w-3.5" />
              <span className="text-[11px] font-mono font-medium tracking-wide uppercase">
                {eyebrow}
              </span>
            </div>
          )}

          {headline && (
            <h2 className="text-2xl sm:text-3xl md:text-4xl font-semibold tracking-tight text-foreground leading-tight mb-1.5">
              {headline}
            </h2>
          )}

          {subtitle && (
            <p className="text-xs sm:text-sm text-neutral-600 dark:text-neutral-400 max-w-2xl mx-auto font-mono">
              {subtitle}
            </p>
          )}
        </div>
      )}

      {/* Horizontal Scrub Slider Track */}
      <div className="flex-1 w-full flex items-center overflow-hidden">
        <div
          ref={wholeSliderRef}
          className="flex h-[52vh] min-h-[420px] max-h-[560px] w-max items-center gap-[4vw] px-[6vw] max-[600px]:h-[78vh] max-[600px]:gap-[8vw] max-[600px]:px-[6vw] shrink-0"
        >
          {/* Visual Showcase Card: Pixel Art Developer Scene */}
          <div className="h-full w-[24vw] min-w-[280px] max-w-[380px] shrink-0 overflow-hidden rounded-2xl max-[600px]:h-[44vh] max-[600px]:w-[80vw] border border-neutral-200 dark:border-white/10 shadow-2xl bg-black flex flex-col group">
            <div className="relative flex-1 w-full overflow-hidden bg-black">
              <img
                src={imageUrl}
                alt={imageAlt}
                draggable={false}
                className="h-full w-full object-cover [image-rendering:pixelated] transition-transform duration-700 group-hover:scale-105"
              />
              <div className="absolute inset-x-0 bottom-0 h-12 bg-gradient-to-t from-black to-transparent pointer-events-none" />
            </div>
            <div className="w-full bg-black px-5 py-4 border-t border-white/10 shrink-0">
              <span className="inline-block text-[10px] font-mono font-semibold uppercase tracking-widest text-neutral-200 bg-white/[0.08] px-2 py-0.5 rounded border border-white/15">
                Core Engine
              </span>
              <p className="text-white text-base font-semibold mt-1.5 tracking-tight">Prompt Compilation Pipeline</p>
              <p className="text-neutral-400 text-xs mt-0.5 font-mono">Continuous deterministic transformation</p>
            </div>
          </div>

          {/* Interactive Timeline Track */}
          <div className="relative h-full flex flex-col justify-between shrink-0">
            {/* Central glowing horizontal guide line */}
            <div className="w-full absolute left-0 top-1/2 -translate-y-1/2 flex items-center pointer-events-none z-10">
              <div
                className="h-[10px] w-[10px] rounded-full shadow-[0_0_12px_rgba(0,0,0,0.4)] dark:shadow-[0_0_12px_rgba(255,255,255,0.75)] shrink-0"
                style={activeStyle}
              />
              <div
                className="h-[2px] w-[0%] rounded-full journey-line shadow-[0_0_10px_rgba(0,0,0,0.3)] dark:shadow-[0_0_10px_rgba(255,255,255,0.5)]"
                style={activeStyle}
              />
              <div
                className="h-[10px] w-[10px] rounded-full shadow-[0_0_12px_rgba(0,0,0,0.4)] dark:shadow-[0_0_12px_rgba(255,255,255,0.75)] shrink-0"
                style={activeStyle}
              />
            </div>

            {/* Top Row: Title + Odd Stages (01, 03, 05) */}
            <div className="flex h-[45%] items-end justify-start gap-[3vw] pb-[2.5vw]">
              {/* Title Block */}
              <div className="w-[18vw] min-w-[220px] shrink-0">
                <h2 className="text-3xl sm:text-4xl md:text-5xl font-semibold leading-[0.95] tracking-tight text-foreground">
                  {title}
                </h2>
              </div>

              {/* Top Stage Cards */}
              <div className="flex items-end gap-[8vw] max-[600px]:gap-[12vw]">
                {topItems.map((item) => (
                  <div
                    key={`top-${item.id}`}
                    className="relative w-[24vw] min-w-[280px] max-w-[360px] shrink-0 max-[600px]:w-[70vw]"
                  >
                    {/* Stem & Dot leading down to the central line */}
                    <div className="absolute left-0 bottom-[-2.5vw] top-0 flex flex-col items-center pointer-events-none">
                      <div
                        className={`size-3 rounded-full shadow-[0_0_10px_rgba(0,0,0,0.4)] dark:shadow-[0_0_10px_rgba(255,255,255,0.75)] jd-${item.id}`}
                        style={activeStyle}
                      />
                      <div
                        className={`w-px flex-1 origin-bottom rounded-full jl-${item.id}`}
                        style={activeStyle}
                      />
                    </div>

                    <div className={`card-content-${item.id} pl-6 space-y-2`}>
                      <div className="inline-flex items-center gap-2">
                        <span className="text-xs font-mono font-semibold px-2 py-0.5 rounded bg-neutral-200/80 text-neutral-800 border border-neutral-300 dark:bg-white/[0.08] dark:text-neutral-200 dark:border-white/15">
                          {item.step || "Step"}
                        </span>
                        <h4
                          className={`title-${item.id} text-xl sm:text-2xl font-semibold tracking-tight text-foreground`}
                        >
                          {item.title}
                        </h4>
                      </div>
                      <p
                        className={`description-${item.id} text-sm sm:text-base leading-relaxed text-neutral-700 dark:text-neutral-300`}
                        style={mutedTextStyle}
                      >
                        {item.content}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Bottom Row: Period Label + Even Stages (02, 04, 06) */}
            <div className="flex h-[45%] items-start justify-start gap-[3vw] pt-[2.5vw]">
              {/* Period Label Block */}
              <div className="w-[18vw] min-w-[220px] shrink-0">
                <p
                  className="text-sm sm:text-base font-mono tracking-wider uppercase text-neutral-600 dark:text-neutral-300 font-semibold"
                  style={mutedTextStyle}
                >
                  {periodLabel}
                </p>
              </div>

              {/* Bottom Stage Cards */}
              <div className="flex items-start gap-[8vw] max-[600px]:gap-[12vw] ml-[4vw]">
                {bottomItems.map((item) => (
                  <div
                    key={`bottom-${item.id}`}
                    className="relative w-[24vw] min-w-[280px] max-w-[360px] shrink-0 max-[600px]:w-[70vw]"
                  >
                    {/* Stem & Dot leading up from the central line */}
                    <div className="absolute left-0 top-[-2.5vw] bottom-0 flex flex-col items-center pointer-events-none">
                      <div
                        className={`w-px flex-1 origin-top rounded-full jl-${item.id}`}
                        style={activeStyle}
                      />
                      <div
                        className={`size-3 rounded-full shadow-[0_0_10px_rgba(0,0,0,0.4)] dark:shadow-[0_0_10px_rgba(255,255,255,0.75)] jd-${item.id}`}
                        style={activeStyle}
                      />
                    </div>

                    <div className={`card-content-${item.id} pl-6 space-y-2 pt-4`}>
                      <div className="inline-flex items-center gap-2">
                        <span className="text-xs font-mono font-semibold px-2 py-0.5 rounded bg-neutral-200/80 text-neutral-800 border border-neutral-300 dark:bg-white/[0.08] dark:text-neutral-200 dark:border-white/15">
                          {item.step || "Step"}
                        </span>
                        <h4
                          className={`title-${item.id} text-xl sm:text-2xl font-semibold tracking-tight text-foreground`}
                        >
                          {item.title}
                        </h4>
                      </div>
                      <p
                        className={`description-${item.id} text-sm sm:text-base leading-relaxed text-neutral-700 dark:text-neutral-300`}
                        style={mutedTextStyle}
                      >
                        {item.content}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </div>

          </div>
        </div>
      </div>
    </section>
  );
}
