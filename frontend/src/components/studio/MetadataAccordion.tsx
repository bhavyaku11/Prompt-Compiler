import React, { useState } from 'react';
import {
  ChevronDown,
  CheckCircle2,
  AlertTriangle,
  HelpCircle,
  ShieldCheck,
  BookOpen,
  ListCheck,
  Target,
  Layers,
} from 'lucide-react';
import type { RequirementSummary, ValidationSummary, KnowledgeReference } from '@/types/api';

interface MetadataAccordionProps {
  requirements?: RequirementSummary | null;
  validation?: ValidationSummary | null;
  knowledgeReferences?: KnowledgeReference[] | null;
  refinementAttempts?: number;
}

export const MetadataAccordion: React.FC<MetadataAccordionProps> = ({
  requirements,
  validation,
  knowledgeReferences = [],
  refinementAttempts = 0,
}) => {
  const [openSections, setOpenSections] = useState<Record<string, boolean>>({
    requirements: false,
    constraints: false,
    assumptions: false,
    validation: false,
    knowledge: false,
  });

  const toggleSection = (section: string) => {
    setOpenSections((prev) => ({
      ...prev,
      [section]: !prev[section],
    }));
  };

  const safeKnowledgeRefs = Array.isArray(knowledgeReferences) ? knowledgeReferences : [];
  const confirmedReqs = Array.isArray(requirements?.confirmed_requirements) ? requirements.confirmed_requirements : [];
  const missingInfo = Array.isArray(requirements?.missing_information) ? requirements.missing_information : [];
  const constraints = Array.isArray(requirements?.constraints) ? requirements.constraints : [];
  const assumptions = Array.isArray(requirements?.assumptions) ? requirements.assumptions : [];

  const preservedReqs = Array.isArray(validation?.preserved_requirements) ? validation.preserved_requirements : [];
  const missingReqs = Array.isArray(validation?.missing_requirements) ? validation.missing_requirements : [];
  const violatedConstraints = Array.isArray(validation?.violated_constraints) ? validation.violated_constraints : [];
  const inventedReqs = Array.isArray(validation?.invented_requirements) ? validation.invented_requirements : [];
  const issues = Array.isArray(validation?.issues) ? validation.issues : [];

  const hasRequirements = requirements && (confirmedReqs.length > 0 || missingInfo.length > 0);
  const hasConstraints = requirements && constraints.length > 0;
  const hasAssumptions = requirements && assumptions.length > 0;
  const hasValidation = validation !== undefined && validation !== null;
  const hasKnowledge = safeKnowledgeRefs.length > 0;

  if (!hasRequirements && !hasConstraints && !hasAssumptions && !hasValidation && !hasKnowledge) {
    return null;
  }

  return (
    <div className="w-full space-y-2 text-left">
      {/* 1. Understood Requirements */}
      {hasRequirements && (
        <div className="rounded-xl border border-border/60 bg-card/60 backdrop-blur-sm overflow-hidden transition-all">
          <button
            type="button"
            onClick={() => toggleSection('requirements')}
            className="w-full flex items-center justify-between px-4 py-2.5 text-xs font-medium text-foreground hover:bg-muted/40 transition-colors cursor-pointer"
          >
            <div className="flex items-center gap-2">
              <ListCheck className="h-4 w-4 text-primary" />
              <span className="font-semibold">Understood Requirements</span>
              <span className="px-1.5 py-0.2 rounded-full text-[10px] font-mono bg-primary/10 text-primary">
                {confirmedReqs.length} confirmed
              </span>
              {missingInfo.length > 0 && (
                <span className="px-1.5 py-0.2 rounded-full text-[10px] font-mono bg-amber-500/10 text-amber-500">
                  {missingInfo.length} open
                </span>
              )}
            </div>
            <ChevronDown
              className={`h-4 w-4 text-muted-foreground transition-transform duration-200 ${
                openSections.requirements ? 'rotate-180' : ''
              }`}
            />
          </button>

          {openSections.requirements && (
            <div className="px-4 pb-3.5 pt-1 text-xs space-y-3 border-t border-border/30">
              {requirements?.intent && (
                <div>
                  <span className="text-[11px] font-mono uppercase tracking-wider text-muted-foreground block mb-0.5">
                    Classified Intent & Domain
                  </span>
                  <p className="text-foreground font-medium">
                    {requirements.intent}
                    {requirements.domain && (
                      <span className="ml-2 text-[10px] font-mono px-2 py-0.5 rounded bg-muted text-muted-foreground">
                        {requirements.domain}
                      </span>
                    )}
                  </p>
                </div>
              )}

              {confirmedReqs.length > 0 && (
                <div>
                  <span className="text-[11px] font-mono uppercase tracking-wider text-muted-foreground block mb-1">
                    Confirmed Explicit Requirements
                  </span>
                  <ul className="space-y-1">
                    {confirmedReqs.map((req, i) => (
                      <li key={i} className="flex items-start gap-2 text-foreground/90">
                        <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500 mt-0.5 shrink-0" />
                        <span>{req}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {missingInfo.length > 0 && (
                <div className="p-2.5 rounded-lg bg-amber-500/10 border border-amber-500/20">
                  <span className="text-[11px] font-mono font-semibold uppercase tracking-wider text-amber-500 flex items-center gap-1.5 mb-1">
                    <HelpCircle className="h-3.5 w-3.5" />
                    Open Decisions (Preserved As Decisions, Not Fabricated)
                  </span>
                  <ul className="space-y-1">
                    {missingInfo.map((item, i) => (
                      <li key={i} className="text-amber-600 dark:text-amber-400 text-xs">
                        • {item}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* 2. Detected Constraints */}
      {hasConstraints && (
        <div className="rounded-xl border border-border/60 bg-card/60 backdrop-blur-sm overflow-hidden transition-all">
          <button
            type="button"
            onClick={() => toggleSection('constraints')}
            className="w-full flex items-center justify-between px-4 py-2.5 text-xs font-medium text-foreground hover:bg-muted/40 transition-colors cursor-pointer"
          >
            <div className="flex items-center gap-2">
              <Target className="h-4 w-4 text-purple-500" />
              <span className="font-semibold">Detected Constraints</span>
              <span className="px-1.5 py-0.2 rounded-full text-[10px] font-mono bg-purple-500/10 text-purple-500">
                {constraints.length}
              </span>
            </div>
            <ChevronDown
              className={`h-4 w-4 text-muted-foreground transition-transform duration-200 ${
                openSections.constraints ? 'rotate-180' : ''
              }`}
            />
          </button>

          {openSections.constraints && (
            <div className="px-4 pb-3.5 pt-1 text-xs border-t border-border/30">
              <ul className="space-y-1.5">
                {constraints.map((c, i) => (
                  <li key={i} className="flex items-start gap-2 text-foreground/90">
                    <span className="h-1.5 w-1.5 rounded-full bg-purple-500 mt-1.5 shrink-0" />
                    <span>{c}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* 3. Conservative Assumptions */}
      {hasAssumptions && (
        <div className="rounded-xl border border-border/60 bg-card/60 backdrop-blur-sm overflow-hidden transition-all">
          <button
            type="button"
            onClick={() => toggleSection('assumptions')}
            className="w-full flex items-center justify-between px-4 py-2.5 text-xs font-medium text-foreground hover:bg-muted/40 transition-colors cursor-pointer"
          >
            <div className="flex items-center gap-2">
              <Layers className="h-4 w-4 text-blue-500" />
              <span className="font-semibold">Safe Assumptions & Defaults</span>
              <span className="px-1.5 py-0.2 rounded-full text-[10px] font-mono bg-blue-500/10 text-blue-500">
                {assumptions.length}
              </span>
            </div>
            <ChevronDown
              className={`h-4 w-4 text-muted-foreground transition-transform duration-200 ${
                openSections.assumptions ? 'rotate-180' : ''
              }`}
            />
          </button>

          {openSections.assumptions && (
            <div className="px-4 pb-3.5 pt-1 text-xs border-t border-border/30">
              <ul className="space-y-1.5">
                {assumptions.map((a, i) => (
                  <li key={i} className="flex items-start gap-2 text-muted-foreground">
                    <span className="h-1.5 w-1.5 rounded-full bg-blue-500 mt-1.5 shrink-0" />
                    <span className="text-foreground/80">{a}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* 4. Critic & Quality Validation */}
      {hasValidation && (
        <div className="rounded-xl border border-border/60 bg-card/60 backdrop-blur-sm overflow-hidden transition-all">
          <button
            type="button"
            onClick={() => toggleSection('validation')}
            className="w-full flex items-center justify-between px-4 py-2.5 text-xs font-medium text-foreground hover:bg-muted/40 transition-colors cursor-pointer"
          >
            <div className="flex items-center gap-2">
              <ShieldCheck className="h-4 w-4 text-emerald-500" />
              <span className="font-semibold">Compiler Critic & Verification</span>
              <span
                className={`px-1.5 py-0.2 rounded-full text-[10px] font-mono ${
                  validation.overall_valid
                    ? 'bg-emerald-500/10 text-emerald-500'
                    : 'bg-red-500/10 text-red-500'
                }`}
              >
                {validation.overall_valid ? 'Fidelity Valid' : 'Issues Detected'}
              </span>
              {refinementAttempts > 0 && (
                <span className="px-1.5 py-0.2 rounded-full text-[10px] font-mono bg-muted text-muted-foreground">
                  {refinementAttempts} refinement pass{refinementAttempts > 1 ? 'es' : ''}
                </span>
              )}
            </div>
            <ChevronDown
              className={`h-4 w-4 text-muted-foreground transition-transform duration-200 ${
                openSections.validation ? 'rotate-180' : ''
              }`}
            />
          </button>

          {openSections.validation && (
            <div className="px-4 pb-3.5 pt-1 text-xs space-y-2.5 border-t border-border/30">
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-[11px] font-mono">
                <div className="p-2 rounded bg-muted/40">
                  <span className="text-muted-foreground block">Preserved</span>
                  <span className="text-foreground font-bold">
                    {preservedReqs.length} requirements
                  </span>
                </div>
                <div className="p-2 rounded bg-muted/40">
                  <span className="text-muted-foreground block">Missing</span>
                  <span
                    className={`font-bold ${
                      missingReqs.length > 0 ? 'text-amber-500' : 'text-emerald-500'
                    }`}
                  >
                    {missingReqs.length} missing
                  </span>
                </div>
                <div className="p-2 rounded bg-muted/40">
                  <span className="text-muted-foreground block">Violated</span>
                  <span
                    className={`font-bold ${
                      violatedConstraints.length > 0 ? 'text-red-500' : 'text-emerald-500'
                    }`}
                  >
                    {violatedConstraints.length} violated
                  </span>
                </div>
                <div className="p-2 rounded bg-muted/40">
                  <span className="text-muted-foreground block">Invented</span>
                  <span
                    className={`font-bold ${
                      inventedReqs.length > 0 ? 'text-red-500' : 'text-emerald-500'
                    }`}
                  >
                    {inventedReqs.length} invented
                  </span>
                </div>
              </div>

              {issues.length > 0 && (
                <div className="mt-2 space-y-1">
                  <span className="text-[11px] font-mono uppercase tracking-wider text-muted-foreground block">
                    Detailed Critic Issues
                  </span>
                  {issues.map((issue, idx) => (
                    <div
                      key={idx}
                      className={`p-2 rounded-lg text-xs flex items-start gap-2 ${
                        issue.severity === 'error'
                          ? 'bg-red-500/10 border border-red-500/20 text-red-600 dark:text-red-400'
                          : issue.severity === 'warning'
                          ? 'bg-amber-500/10 border border-amber-500/20 text-amber-600 dark:text-amber-400'
                          : 'bg-muted/50 text-foreground'
                      }`}
                    >
                      <AlertTriangle className="h-3.5 w-3.5 mt-0.5 shrink-0" />
                      <div>
                        <span className="font-mono font-semibold uppercase text-[10px] mr-1.5">
                          [{issue.category}]
                        </span>
                        <span>{issue.message}</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* 5. Retrieved Project Knowledge */}
      {hasKnowledge && (
        <div className="rounded-xl border border-border/60 bg-card/60 backdrop-blur-sm overflow-hidden transition-all">
          <button
            type="button"
            onClick={() => toggleSection('knowledge')}
            className="w-full flex items-center justify-between px-4 py-2.5 text-xs font-medium text-foreground hover:bg-muted/40 transition-colors cursor-pointer"
          >
            <div className="flex items-center gap-2">
              <BookOpen className="h-4 w-4 text-emerald-500" />
              <span className="font-semibold">Knowledge Retrieval Sources</span>
              <span className="px-1.5 py-0.2 rounded-full text-[10px] font-mono bg-emerald-500/10 text-emerald-500">
                {safeKnowledgeRefs.length} chunk{safeKnowledgeRefs.length > 1 ? 's' : ''}
              </span>
            </div>
            <ChevronDown
              className={`h-4 w-4 text-muted-foreground transition-transform duration-200 ${
                openSections.knowledge ? 'rotate-180' : ''
              }`}
            />
          </button>

          {openSections.knowledge && (
            <div className="px-4 pb-3.5 pt-1 text-xs space-y-2 border-t border-border/30">
              {safeKnowledgeRefs.map((ref, idx) => (
                <div
                  key={idx}
                  className="flex items-center justify-between p-2 rounded-lg bg-muted/40 border border-border/30"
                >
                  <div className="flex items-center gap-2 min-w-0">
                    <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-card border border-border/40 text-foreground uppercase">
                      {ref.source_type}
                    </span>
                    <span className="font-medium text-foreground truncate">
                      {ref.source_name}
                    </span>
                  </div>
                  <div className="flex items-center gap-2 shrink-0 text-[11px] font-mono text-muted-foreground">
                    <span>Similarity:</span>
                    <span className="font-bold text-emerald-500">
                      {(ref.score * 100).toFixed(1)}%
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
