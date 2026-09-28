import type { JourneyItem } from "@/components/ui/timeline";

export const workflowTopItems: JourneyItem[] = [
  {
    id: "step-01",
    step: "01",
    title: "Describe",
    year: "Stage 01",
    month: "Describe",
    content: "Start with a rough idea, requirement, feature request, or complex problem statement.",
  },
  {
    id: "step-03",
    step: "03",
    title: "Add Context",
    year: "Stage 03",
    month: "Add Context",
    content: "Inject confirmed project memory, architecture contracts, and local vector knowledge.",
  },
  {
    id: "step-05",
    step: "05",
    title: "Target Agent",
    year: "Stage 05",
    month: "Target Agent",
    content: "Format deterministically for your selected AI agent: Cursor, Claude Code, Cline, or Windsurf.",
  },
];

export const workflowBottomItems: JourneyItem[] = [
  {
    id: "step-02",
    step: "02",
    title: "Understand",
    year: "Stage 02",
    month: "Understand",
    content: "Separate explicit requirements from missing information and safe architectural assumptions.",
  },
  {
    id: "step-04",
    step: "04",
    title: "Compile",
    year: "Stage 04",
    month: "Compile",
    content: "Transform structured requirements into a canonical, implementation-ready prompt.",
  },
  {
    id: "step-06",
    step: "06",
    title: "Refine",
    year: "Stage 06",
    month: "Refine",
    content: "Validate constraints, anti-hallucination bounds, and contracts before returning the prompt.",
  },
];
