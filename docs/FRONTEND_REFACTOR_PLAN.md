# Frontend Refactor & AI Workspace Plan

This document outlines the proposed restructuring and migration plan for the Next.js frontend, shifting from a wizard-based flow to a single, comprehensive reserving **AI Workspace** using a feature-based architecture.

---

## 1. Current Directory Structure

Currently, all page files and components are placed in a flat or layout-centric organization:

```text
frontend/src/app/
├── components/
│   ├── ConfigureAssumptions.tsx
│   ├── ModelSelector.tsx (Legacy/Unused)
│   ├── ParamsView.tsx (Legacy/Unused)
│   ├── ResultsView.tsx
│   ├── SettingsModal.tsx
│   ├── SidebarChat.tsx
│   ├── StepProgress.tsx
│   ├── SummaryView.tsx
│   ├── TriangleView.tsx
│   └── UploadZone.tsx
├── favicon.ico
├── globals.css
├── layout.tsx
├── page.tsx
├── types.ts
└── utils.ts
```

---

## 2. Proposed Feature-Based Architecture

We will organize the code under `frontend/src/` by feature. This separates distinct domains (upload, diagnostics, comparison, recommendation, report, and chat) and keeps generic elements shared.

```text
frontend/src/
├── app/                      # Next.js App Router Pages
│   ├── favicon.ico
│   ├── globals.css
│   ├── layout.tsx
│   └── page.tsx              # Main Workspace Coordinator
├── components/               # Shared / Generic UI Components
│   ├── SettingsModal.tsx     # Global Settings
│   └── StepProgress.tsx      # Generic Navigation/Tabs
├── features/                 # Domain-Specific Features
│   ├── upload/
│   │   └── UploadZone.tsx    # File Drag-and-drop & Context Inputs
│   ├── diagnostics/
│   │   ├── SummaryView.tsx   # Columns classification, inspection, mapping
│   │   └── TriangleView.tsx  # Incurred/Paid Triangles & ATA/LDF factors
│   ├── comparison/
│   │   ├── ConfigureAssumptions.tsx # Model/Method config & parameter inputs
│   │   └── ResultsView.tsx   # Dashboard comparative table & charts
│   ├── recommendation/
│   │   └── RecommendationView.tsx # [NEW] Displays AI Recommendation & Decision Trace details
│   ├── report/
│   │   └── ReportView.tsx    # [NEW] Previews full compiled markdown actuarial reports
│   └── chat/
│       └── SidebarChat.tsx   # Chatbot interface & conditions submission
├── hooks/                    # Reusable Custom Hooks
├── lib/                      # Reusable Utilities / API client
│   └── utils.ts              # formatting & dynamic API URL helpers
└── types/                    # Reusable TS definitions
    └── index.ts              # standard TypeScript interfaces
```

---

## 3. Migration Steps (Incremental & Low-Risk)

To keep the application functional during migration, we will proceed step-by-step:

### Step A: Structure Setup & Type Migration
1. Create directories: `components/`, `features/`, `hooks/`, `lib/`, and `types/` under `frontend/src/`.
2. Move `frontend/src/app/types.ts` to `frontend/src/types/index.ts`.
3. Move `frontend/src/app/utils.ts` to `frontend/src/lib/utils.ts`.

### Step B: Restructure Existing Components
1. Move generic components (`SettingsModal.tsx`, `StepProgress.tsx`) to `frontend/src/components/`.
2. Move `UploadZone.tsx` to `frontend/src/features/upload/`.
3. Move `SummaryView.tsx` and `TriangleView.tsx` to `frontend/src/features/diagnostics/`.
4. Move `ConfigureAssumptions.tsx` and `ResultsView.tsx` to `frontend/src/features/comparison/`.
5. Move legacy/unused components (`ModelSelector.tsx`, `ParamsView.tsx`) to `frontend/src/features/comparison/` to keep them as backups for reference.
6. Move `SidebarChat.tsx` to `frontend/src/features/chat/`.

### Step C: Update Import Paths & Verify Compilation
1. Update import declarations in all relocated components (updating relative paths to `../types` and `../utils`).
2. Update import declarations in `frontend/src/app/page.tsx`.
3. Run `npm run build` from `frontend/` to confirm that the project compiles with no errors.

---

## 4. Reused vs. Newly Created Components

### Reused Components
* `UploadZone` -> Reused for dataset upload.
* `SummaryView` & `TriangleView` -> Reused for dataset summary & triangle inspection.
* `ConfigureAssumptions` & `ResultsView` -> Reused for configuring and comparing models.
* `SidebarChat` -> Reused for multi-agent chatbot.
* `SettingsModal` & `StepProgress` -> Reused for workspace global config and navigation tabs.

### Newly Created Components (Drafted for Next Stage)
* `RecommendationView` -> Formats the supervisor recommendation and renders the **Decision Trace** side-by-side.
* `ReportView` -> Provides a beautiful scrolling markdown preview of the full compiled actuarial report.

---

## 5. Next Stage: Reserving AI Workspace UI Design

Once the file reorganization is completed and approved, we will update `frontend/src/app/page.tsx` to coordinate all features in a **single reserving workspace** workspace. 

### Workspace Layout Diagram:
```text
┌────────────────────────────────────────────────────────────────────────┐
│  Actuarial Reserve AI Workspace                      [USD v] [Settings]│
├────────────────────────────────────────────────────────────────────────┤
│  Main workspace view area:                                             │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │ Tabs: [Upload/Summary] [Triangles] [Methods & Runs] [AI Insights] │  │
│  ├──────────────────────────────────────────────────────────────────┤  │
│  │                                                                  │  │
│  │ Renders active view (Summary, Triangles, comparison Dashboard,   │  │
│  │ or AI Recommendation & Decision Trace)                           │  │
│  │                                                                  │  │
│  └──────────────────────────────────────────────────────────────────┘  │
├────────────────────────────────────────────────────────────────────────┤
│  Agent Chat / Processing Log Sidebar (Toggleable, always reachable)    │
└────────────────────────────────────────────────────────────────────────┘
```
This single workspace layout will:
- Avoid the rigid multi-step wizard.
- Allow developers/actuaries to switch instantly between Dataset Summary, Triangles, Comparison Dashboard, and AI Recommendations once a session is active.
