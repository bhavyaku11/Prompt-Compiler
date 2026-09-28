import { MagneticCursor } from '@/components/ui/magnetic-cursor';
import { Navbar } from '@/sections/Navbar';
import { Hero } from '@/sections/Hero';
import { WorkflowTimeline } from '@/sections/WorkflowTimeline';
import { LandingFooter } from '@/sections/LandingFooter';

export function LandingView() {
  return (
    <MagneticCursor
      magneticFactor={0.35}
      disableOnTouch={true}
    >
      <div className="relative min-h-screen w-full bg-background text-foreground font-sans selection:bg-neutral-800 selection:text-white dark:selection:bg-white dark:selection:text-black flex flex-col justify-between overflow-x-clip transition-colors duration-300">
        
        {/* Subtle Developer Grid Background */}
        <div 
          className="absolute inset-0 z-0 bg-grid-pattern opacity-60 pointer-events-none" 
          aria-hidden="true"
        />

        {/* Radial vignette overlay to smoothly dim edges */}
        <div 
          className="absolute inset-0 z-0 bg-vignette pointer-events-none" 
          aria-hidden="true"
        />

        {/* Navigation Bar */}
        <Navbar />

        {/* Main Content: Hero followed by Workflow Timeline */}
        <main className="relative z-10 flex flex-1 flex-col items-center justify-center bg-transparent">
          <Hero />
          <WorkflowTimeline />
        </main>

        {/* Cinematic Landing Footer */}
        <LandingFooter />

      </div>
    </MagneticCursor>
  );
}

export default LandingView;
