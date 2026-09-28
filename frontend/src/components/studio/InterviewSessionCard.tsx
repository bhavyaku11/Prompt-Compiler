import React, { useState } from 'react';
import {
  HelpCircle,
  ArrowRight,
  Sparkles,
  X,
  Check,
  Loader2,
  MessageSquareQuote,
} from 'lucide-react';
import type {
  InterviewSessionResponse,
  InterviewAnswer,
} from '@/types/api';

interface InterviewSessionCardProps {
  session: InterviewSessionResponse;
  originalInput: string;
  isSubmitting: boolean;
  onSubmitAnswers: (answers: InterviewAnswer[]) => void;
  onSkipAndCompile: () => void;
  onCancel: () => void;
}

export function InterviewSessionCard({
  session,
  originalInput,
  isSubmitting,
  onSubmitAnswers,
  onSkipAndCompile,
  onCancel,
}: InterviewSessionCardProps) {
  // Map question_id -> selected option
  const [selectedOptions, setSelectedOptions] = useState<Record<string, string>>({});
  // Map question_id -> custom input text
  const [customInputs, setCustomInputs] = useState<Record<string, string>>({});

  const handleSelectOption = (questionId: string, option: string) => {
    setSelectedOptions((prev) => ({
      ...prev,
      [questionId]: prev[questionId] === option ? '' : option,
    }));
    // Clear custom input if an option is toggled on
    if (selectedOptions[questionId] !== option) {
      setCustomInputs((prev) => ({ ...prev, [questionId]: '' }));
    }
  };

  const handleCustomInputChange = (questionId: string, value: string) => {
    setCustomInputs((prev) => ({ ...prev, [questionId]: value }));
    if (value.trim()) {
      setSelectedOptions((prev) => ({ ...prev, [questionId]: '' }));
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (isSubmitting) return;

    const answers: InterviewAnswer[] = [];
    for (const q of session.questions) {
      const customVal = customInputs[q.id]?.trim();
      const optionVal = selectedOptions[q.id];
      const answerVal = customVal || optionVal;
      if (answerVal) {
        answers.push({
          question_id: q.id,
          answer: answerVal,
        });
      }
    }

    if (answers.length === 0) {
      // If nothing selected, proceed with defaults
      onSkipAndCompile();
    } else {
      onSubmitAnswers(answers);
    }
  };

  const totalQuestions = session.questions?.length ?? 0;
  const answeredCount = session.questions?.filter(
    (q) => selectedOptions[q.id] || customInputs[q.id]?.trim()
  ).length ?? 0;

  return (
    <div className="w-full max-w-4xl mx-auto p-5 sm:p-7 rounded-3xl border border-border bg-card shadow-2xl shadow-slate-200/50 dark:shadow-2xl dark:shadow-black/70 animate-in fade-in duration-300">
      {/* Header Banner */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-4 border-b border-border/70 gap-3">
        <div className="flex items-center gap-3">
          <div className="h-10 w-10 rounded-2xl bg-amber-500/10 border border-amber-500/20 text-amber-500 flex items-center justify-center shrink-0">
            <HelpCircle className="h-5 w-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-mono font-semibold text-amber-600 dark:text-amber-400 uppercase tracking-wider">
                Interview Clarification
              </span>
              <span className="text-[11px] px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-600 dark:text-amber-400 font-mono">
                Turn {session.turn} of 3
              </span>
            </div>
            <h2 className="text-base sm:text-lg font-bold text-foreground tracking-tight mt-0.5">
              Clarify Implementation Decisions
            </h2>
          </div>
        </div>

        <button
          type="button"
          onClick={onCancel}
          disabled={isSubmitting}
          className="self-end sm:self-center p-2 rounded-xl text-muted-foreground hover:text-foreground hover:bg-secondary transition-colors cursor-pointer disabled:opacity-50"
          title="Cancel interview and return to composer"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      {/* Original Input Reference */}
      <div className="mt-4 p-3.5 rounded-2xl bg-toolbar border border-border/70 flex items-start gap-2.5 text-xs text-muted-foreground font-mono">
        <MessageSquareQuote className="h-4 w-4 mt-0.5 text-primary shrink-0" />
        <div className="flex-1 overflow-hidden text-ellipsis">
          <span className="font-semibold text-foreground/80">Requirement: </span>
          <span className="text-foreground italic">"{originalInput}"</span>
        </div>
      </div>

      {/* Clarification Questions Form */}
      <form onSubmit={handleSubmit} className="mt-6 space-y-6">
        <div className="space-y-6">
          {session.questions.map((q, idx) => {
            const currentSelected = selectedOptions[q.id];
            const currentCustom = customInputs[q.id] || '';

            return (
              <div
                key={q.id}
                className="p-4 sm:p-5 rounded-2xl border border-border/80 bg-toolbar/60 hover:bg-toolbar transition-all duration-200"
              >
                <div className="flex items-center justify-between gap-2 mb-2">
                  <span className="text-[11px] font-mono uppercase tracking-wider px-2 py-0.5 rounded-md bg-primary/10 text-primary font-semibold">
                    Question {idx + 1}: {q.topic.replace(/_/g, ' ')}
                  </span>
                  {(currentSelected || currentCustom.trim()) && (
                    <span className="flex items-center gap-1 text-[11px] font-mono text-emerald-500 font-medium">
                      <Check className="h-3 w-3" /> Answered
                    </span>
                  )}
                </div>

                <p className="text-sm font-semibold text-foreground leading-snug mb-3">
                  {q.question}
                </p>

                {/* Options Chips Grid */}
                {q.options && q.options.length > 0 && (
                  <div className="flex flex-wrap gap-2 mb-3">
                    {q.options.map((opt) => {
                      const isSelected = currentSelected === opt;
                      return (
                        <button
                          key={opt}
                          type="button"
                          disabled={isSubmitting}
                          onClick={() => handleSelectOption(q.id, opt)}
                          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-medium transition-all duration-150 cursor-pointer ${
                            isSelected
                              ? 'bg-primary text-primary-foreground shadow-xs font-semibold'
                              : 'bg-muted/60 text-muted-foreground hover:bg-muted hover:text-foreground border border-border/40'
                          }`}
                        >
                          {isSelected && <Check className="h-3 w-3 shrink-0" />}
                          <span>{opt}</span>
                        </button>
                      );
                    })}
                  </div>
                )}

                {/* Custom Answer Input */}
                <div className="mt-2">
                  <input
                    type="text"
                    disabled={isSubmitting}
                    value={currentCustom}
                    onChange={(e) => handleCustomInputChange(q.id, e.target.value)}
                    placeholder={
                      q.options?.length
                        ? 'Or enter custom specification...'
                        : 'Enter your answer or preference...'
                    }
                    className="w-full px-3 py-2 rounded-xl text-xs bg-muted/30 border border-border/50 text-foreground placeholder:text-muted-foreground/60 focus:outline-hidden focus:ring-1 focus:ring-primary/40 focus:border-primary transition-all font-mono"
                  />
                </div>
              </div>
            );
          })}
        </div>

        {/* Action Buttons Footer */}
        <div className="pt-4 border-t border-border/40 flex flex-col sm:flex-row items-center justify-between gap-3">
          <div className="text-xs text-muted-foreground font-mono">
            <span>
              {answeredCount} of {totalQuestions} answered
            </span>
          </div>

          <div className="flex items-center gap-2.5 w-full sm:w-auto">
            {/* Skip & Compile with Defaults */}
            <button
              type="button"
              onClick={onSkipAndCompile}
              disabled={isSubmitting}
              className="flex-1 sm:flex-none flex items-center justify-center gap-1.5 px-3.5 py-2.5 rounded-xl border border-border bg-background hover:bg-muted/60 text-muted-foreground hover:text-foreground font-semibold text-xs transition-colors cursor-pointer disabled:opacity-50"
            >
              <Sparkles className="h-3.5 w-3.5 text-amber-500" />
              <span>Use Safe Defaults</span>
            </button>

            {/* Submit & Continue */}
            <button
              type="submit"
              disabled={isSubmitting}
              className="flex-1 sm:flex-none flex items-center justify-center gap-2 px-5 py-2.5 rounded-xl bg-primary text-primary-foreground font-semibold text-xs hover:opacity-90 transition-all cursor-pointer shadow-md disabled:opacity-50"
            >
              {isSubmitting ? (
                <>
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  <span>Processing...</span>
                </>
              ) : (
                <>
                  <span>Submit & Compile</span>
                  <ArrowRight className="h-3.5 w-3.5" />
                </>
              )}
            </button>
          </div>
        </div>
      </form>
    </div>
  );
}
