import React, { useState } from 'react';
import { Copy, Check } from 'lucide-react';

interface MarkdownRendererProps {
  content: string;
  className?: string;
}

export const MarkdownRenderer: React.FC<MarkdownRendererProps> = ({ content = '', className = '' }) => {
  const [copiedCodeIndex, setCopiedCodeIndex] = useState<number | null>(null);

  const handleCopyCode = async (code: string, index: number) => {
    try {
      await navigator.clipboard.writeText(code);
      setCopiedCodeIndex(index);
      setTimeout(() => setCopiedCodeIndex(null), 2000);
    } catch {
      // clipboard error
    }
  };

  // Split content into blocks (code blocks vs regular markdown text)
  const safeContent = content || '';
  const blocks = parseMarkdownBlocks(safeContent);

  return (
    <div className={`space-y-3 font-sans text-sm leading-relaxed text-foreground ${className}`}>
      {blocks.map((block, idx) => {
        if (block.type === 'code') {
          return (
            <div
              key={idx}
              className="relative my-3 rounded-xl border border-neutral-200 dark:border-neutral-800 bg-neutral-900 dark:bg-black/80 overflow-hidden shadow-sm text-neutral-100 font-mono text-xs"
            >
              <div className="flex items-center justify-between px-3.5 py-1.5 border-b border-neutral-800 bg-neutral-950/80 text-[11px] text-neutral-400">
                <span className="font-mono tracking-wider lowercase">
                  {block.language || 'code'}
                </span>
                <button
                  type="button"
                  onClick={() => handleCopyCode(block.content, idx)}
                  className="flex items-center gap-1 px-2 py-0.5 rounded text-[11px] text-neutral-300 hover:text-white hover:bg-neutral-800 transition-colors cursor-pointer"
                  title="Copy snippet"
                >
                  {copiedCodeIndex === idx ? (
                    <>
                      <Check className="h-3 w-3 text-emerald-400" />
                      <span className="text-emerald-400">Copied</span>
                    </>
                  ) : (
                    <>
                      <Copy className="h-3 w-3" />
                      <span>Copy</span>
                    </>
                  )}
                </button>
              </div>
              <pre className="p-3.5 overflow-x-auto text-xs leading-relaxed text-neutral-200 selection:bg-neutral-700 selection:text-white">
                <code>{block.content}</code>
              </pre>
            </div>
          );
        }

        // Standard text lines
        const lines = block.content.split('\n');
        return (
          <div key={idx} className="space-y-2">
            {lines.map((line, lIdx) => renderLine(line, `${idx}-${lIdx}`))}
          </div>
        );
      })}
    </div>
  );
};

interface Block {
  type: 'text' | 'code';
  content: string;
  language?: string;
}

function parseMarkdownBlocks(text: string): Block[] {
  const blocks: Block[] = [];
  const lines = text.split('\n');
  let inCodeBlock = false;
  let codeBuffer: string[] = [];
  let textBuffer: string[] = [];
  let currentLanguage = '';

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    if (line.trim().startsWith('```')) {
      if (inCodeBlock) {
        // End of code block
        blocks.push({
          type: 'code',
          content: codeBuffer.join('\n'),
          language: currentLanguage,
        });
        codeBuffer = [];
        inCodeBlock = false;
        currentLanguage = '';
      } else {
        // Start of code block
        if (textBuffer.length > 0) {
          blocks.push({
            type: 'text',
            content: textBuffer.join('\n'),
          });
          textBuffer = [];
        }
        inCodeBlock = true;
        currentLanguage = line.trim().slice(3).trim();
      }
    } else if (inCodeBlock) {
      codeBuffer.push(line);
    } else {
      textBuffer.push(line);
    }
  }

  if (inCodeBlock && codeBuffer.length > 0) {
    blocks.push({
      type: 'code',
      content: codeBuffer.join('\n'),
      language: currentLanguage,
    });
  } else if (textBuffer.length > 0) {
    blocks.push({
      type: 'text',
      content: textBuffer.join('\n'),
    });
  }

  return blocks;
}

function renderLine(line: string, key: string): React.ReactNode {
  const trimmed = line.trim();

  if (!trimmed) {
    return <div key={key} className="h-2" />;
  }

  // Horizontal rule
  if (/^(\*\*\*|---|___)$/.test(trimmed)) {
    return <hr key={key} className="my-3 border-border/60" />;
  }

  // Headings
  if (trimmed.startsWith('#### ')) {
    return (
      <h4 key={key} className="text-xs font-bold font-mono tracking-wider uppercase text-foreground mt-4 mb-1">
        {renderInlineFormatted(trimmed.slice(5))}
      </h4>
    );
  }
  if (trimmed.startsWith('### ')) {
    return (
      <h3 key={key} className="text-sm font-semibold tracking-tight text-foreground mt-4 mb-1">
        {renderInlineFormatted(trimmed.slice(4))}
      </h3>
    );
  }
  if (trimmed.startsWith('## ')) {
    return (
      <h2 key={key} className="text-base font-bold tracking-tight text-foreground mt-5 mb-1.5 pb-1 border-b border-border/40">
        {renderInlineFormatted(trimmed.slice(3))}
      </h2>
    );
  }
  if (trimmed.startsWith('# ')) {
    return (
      <h1 key={key} className="text-lg font-extrabold tracking-tight text-foreground mt-6 mb-2">
        {renderInlineFormatted(trimmed.slice(2))}
      </h1>
    );
  }

  // Blockquote
  if (trimmed.startsWith('> ')) {
    return (
      <blockquote key={key} className="pl-3 py-1 my-2 border-l-2 border-primary/50 text-muted-foreground italic text-xs">
        {renderInlineFormatted(trimmed.slice(2))}
      </blockquote>
    );
  }

  // Unordered list
  if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
    return (
      <div key={key} className="flex items-start gap-2 ml-2 my-0.5">
        <span className="text-primary mt-1.5 h-1.5 w-1.5 rounded-full bg-current shrink-0" />
        <span className="flex-1 text-foreground/90">{renderInlineFormatted(trimmed.slice(2))}</span>
      </div>
    );
  }

  // Numbered list
  const orderedMatch = trimmed.match(/^(\d+)\.\s+(.*)$/);
  if (orderedMatch) {
    return (
      <div key={key} className="flex items-start gap-2 ml-2 my-0.5">
        <span className="font-mono text-xs text-muted-foreground font-semibold shrink-0 mt-0.5">
          {orderedMatch[1]}.
        </span>
        <span className="flex-1 text-foreground/90">{renderInlineFormatted(orderedMatch[2])}</span>
      </div>
    );
  }

  // Standard paragraph
  return (
    <p key={key} className="text-foreground/90 leading-relaxed">
      {renderInlineFormatted(line)}
    </p>
  );
}

function renderInlineFormatted(text: string): React.ReactNode {
  // Regex to match inline code (`code`), bold (**bold**), and plain text
  const parts: React.ReactNode[] = [];
  const regex = /(`[^`]+`|\*\*[^*]+\*\*)/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = regex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push(text.substring(lastIndex, match.index));
    }
    const token = match[0];
    if (token.startsWith('`') && token.endsWith('`')) {
      const code = token.slice(1, -1);
      parts.push(
        <code
          key={match.index}
          className="px-1.5 py-0.5 mx-0.5 rounded-md font-mono text-[11px] bg-neutral-200/70 dark:bg-neutral-800 border border-neutral-300 dark:border-neutral-700 text-foreground font-medium"
        >
          {code}
        </code>
      );
    } else if (token.startsWith('**') && token.endsWith('**')) {
      const boldText = token.slice(2, -2);
      parts.push(
        <strong key={match.index} className="font-semibold text-foreground">
          {boldText}
        </strong>
      );
    }
    lastIndex = regex.lastIndex;
  }

  if (lastIndex < text.length) {
    parts.push(text.substring(lastIndex));
  }

  return parts.length > 0 ? parts : text;
}
