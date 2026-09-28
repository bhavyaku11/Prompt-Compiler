import React, { useState } from 'react';
import { Copy, Check, Download, Maximize2, Minimize2, Sparkles, Terminal } from 'lucide-react';
import { MarkdownRenderer } from './MarkdownRenderer';

interface CompiledPromptCardProps {
  prompt: string;
  targetAgent: string;
  taskType?: string | null;
  templateName?: string | null;
  refinementAttempts?: number;
}

export const CompiledPromptCard: React.FC<CompiledPromptCardProps> = ({
  prompt,
  targetAgent,
  taskType,
  refinementAttempts = 0,
}) => {
  const [copied, setCopied] = useState(false);
  const [isExpanded, setIsExpanded] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(prompt);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // clipboard error
    }
  };

  const handleDownload = () => {
    const filename = `prompt-compiler-${targetAgent || 'generic'}-${Date.now()}.md`;
    const blob = new Blob([prompt], { type: 'text/markdown;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', filename);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  return (
    <>
      <div
        className={`w-full rounded-2xl border border-border bg-card shadow-xl shadow-slate-200/50 dark:shadow-2xl dark:shadow-black/70 transition-all duration-200 overflow-hidden flex flex-col ${
          isExpanded ? 'fixed inset-4 z-50 max-w-none h-auto' : ''
        }`}
      >
        {/* Header Bar */}
        <div className="flex items-center justify-between px-4 py-3 sm:px-6 sm:py-3.5 border-b border-border/70 bg-toolbar">
          <div className="flex items-center gap-2.5">
            <div className="h-7 w-7 rounded-lg bg-primary/10 text-primary flex items-center justify-center font-mono">
              <Terminal className="h-4 w-4 stroke-[2.2]" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-sm font-bold tracking-tight text-foreground">
                  Compiled Prompt
                </h3>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-primary/10 text-primary font-bold uppercase tracking-wider">
                  {targetAgent}
                </span>
                {taskType && (
                  <span className="hidden sm:inline-block text-[10px] font-mono px-2 py-0.5 rounded-full bg-muted text-muted-foreground uppercase">
                    {taskType}
                  </span>
                )}
              </div>
            </div>
          </div>

          {/* Action buttons */}
          <div className="flex items-center gap-1.5 sm:gap-2">
            {refinementAttempts > 0 && (
              <span className="hidden md:inline-flex items-center gap-1 text-[11px] font-mono text-muted-foreground px-2 py-1 rounded bg-muted/50 border border-border/30">
                <Sparkles className="h-3 w-3 text-amber-500" />
                <span>{refinementAttempts} Refined</span>
              </span>
            )}

            {/* Copy Button */}
            <button
              type="button"
              onClick={handleCopy}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all cursor-pointer ${
                copied
                  ? 'bg-emerald-500 text-white shadow-sm'
                  : 'bg-primary text-primary-foreground hover:opacity-90 shadow-sm'
              }`}
              title="Copy prompt to clipboard"
            >
              {copied ? (
                <>
                  <Check className="h-3.5 w-3.5" />
                  <span>Copied!</span>
                </>
              ) : (
                <>
                  <Copy className="h-3.5 w-3.5" />
                  <span>Copy Prompt</span>
                </>
              )}
            </button>

            {/* Download Button */}
            <button
              type="button"
              onClick={handleDownload}
              className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium text-muted-foreground hover:text-foreground hover:bg-muted/60 border border-border/40 transition-colors cursor-pointer"
              title="Download as Markdown (.md)"
            >
              <Download className="h-3.5 w-3.5" />
              <span className="hidden sm:inline">Export</span>
            </button>

            {/* Fullscreen Expand/Collapse */}
            <button
              type="button"
              onClick={() => setIsExpanded((prev) => !prev)}
              className="p-1.5 rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted/60 border border-border/40 transition-colors cursor-pointer"
              title={isExpanded ? 'Collapse' : 'Expand full screen'}
            >
              {isExpanded ? (
                <Minimize2 className="h-3.5 w-3.5" />
              ) : (
                <Maximize2 className="h-3.5 w-3.5" />
              )}
            </button>
          </div>
        </div>

        {/* Output Body */}
        <div
          className={`p-4 sm:p-6 overflow-y-auto ${
            isExpanded ? 'flex-1 max-h-none' : 'max-h-[560px]'
          } selection:bg-neutral-800 selection:text-white dark:selection:bg-white dark:selection:text-black`}
        >
          <MarkdownRenderer content={prompt} />
        </div>
      </div>

      {/* Dim backdrop when expanded */}
      {isExpanded && (
        <div
          className="fixed inset-0 bg-black/60 backdrop-blur-sm z-40"
          onClick={() => setIsExpanded(false)}
        />
      )}
    </>
  );
};
