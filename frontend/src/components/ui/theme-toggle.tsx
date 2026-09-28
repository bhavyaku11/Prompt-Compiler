"use client";

import { useTheme } from "@/context/ThemeContext";
import { Sun, Moon } from "lucide-react";
import { MagneticButton } from "@/components/ui/magnetic-button";

export function ThemeToggle({ className }: { className?: string }) {
  const { theme, toggleTheme } = useTheme();
  const isDark = theme === "dark";

  return (
    <MagneticButton
      as="button"
      type="button"
      onClick={toggleTheme}
      aria-label={`Switch to ${isDark ? "light" : "dark"} mode`}
      className={`relative flex h-9 w-9 items-center justify-center rounded-full border border-neutral-300 dark:border-white/15 bg-neutral-100/80 dark:bg-white/5 text-neutral-700 dark:text-neutral-200 backdrop-blur-md transition-colors duration-200 hover:bg-neutral-200 dark:hover:bg-white/10 hover:border-neutral-400 dark:hover:border-white/30 ${className || ""}`}
    >
      {isDark ? (
        <Sun className="h-4 w-4 transition-transform duration-300 hover:rotate-45 text-amber-300 pointer-events-none" />
      ) : (
        <Moon className="h-4 w-4 transition-transform duration-300 hover:-rotate-12 text-neutral-800 pointer-events-none" />
      )}
    </MagneticButton>
  );
}

export default ThemeToggle;
