# Application Flow: DocuPulse Reader

Based on Handbook Appendix A.4 (`VirtualOffice_Complete_Guide.md`), `docs/prd.md`, and `docs/architecture.md`.

---

## 1. Screens

| ID | Screen | Route | Purpose | Auth / Role | Features |
|---|---|---|---|---|---|
| `S-01` | Dashboard & Activity Overview | `/` | Operational dashboard showing recent activities, status summaries, and active alerts | `[P-01], [P-02]` | `[F-001 / FR-01], [F-002 / FR-02]` |
| `S-02` | Core operational workflow management and activity logging for DocuPulse Reader | `/core-operational-wor` | Workspace for core operational workflow management and activity logging for docupulse reader with validation and local persistence | `[P-01]` | `[F-001 / FR-01]` |
| `S-03` | Structured local compliance report compilation and data export in DocuPulse Reader | `/structured-local-com` | Workspace for structured local compliance report compilation and data export in docupulse reader with validation and local persistence | `[P-02]` | `[F-002 / FR-02]` |
| `S-99` | Not Found & Permission Denied | `*` | Fallback route for invalid URLs or unauthorized access attempts | Public / Local | System Fallback |

---

## 2. Journeys

### J-1: Core operational workflow management and activity logging for DocuPulse Reader — covers [F-001 / FR-01], [AC-001], [AC-002]
1. On `S-01` (Dashboard) → Biomedical research scientists (`[P-01]`) views operational overview → clicks primary action button for Core operational workflow management and activity logging for DocuPulse Reader.
2. `S-02` loads → user inputs required parameters and configuration details (`[API-001]`).
3. **Success**: System validates input, persists record into local database (`[TBL-02]`), displays confirmation toast, and updates active view within 1.0 s (`[AC-001]`, `[NFR-01]`).
4. **Error (invalid input)**: Inline validation notices highlight offending fields, preserve user inputs without loss, and enable immediate correction (`[AC-002]`).
5. **Error (system / storage error)**: Non-blocking warning banner notifies user of local database error with an actionable retry button (`[AC-002]`).

### J-2: Structured local compliance report compilation and data export in DocuPulse Reader — covers [F-002 / FR-02], [AC-003], [AC-004]
1. On `S-01` (Dashboard) → lab technicians (`[P-02]`) views operational overview → clicks primary action button for Structured local compliance report compilation and data export in DocuPulse Reader.
2. `S-03` loads → user inputs required parameters and configuration details (`[API-002]`).
3. **Success**: System validates input, persists record into local database (`[TBL-03]`), displays confirmation toast, and updates active view within 1.0 s (`[AC-003]`, `[NFR-01]`).
4. **Error (invalid input)**: Inline validation notices highlight offending fields, preserve user inputs without loss, and enable immediate correction (`[AC-004]`).
5. **Error (system / storage error)**: Non-blocking warning banner notifies user of local database error with an actionable retry button (`[AC-004]`).

---

## 3. Screen states

### S-01 Dashboard & Activity Overview
- **Loading**: Skeleton layout mirroring summary cards and operational activity feed with animated pulse effect.
- **Empty**: Informational banner stating "No operational activity recorded today", accompanied by a primary CTA button.
- **Populated**: Metric cards showing active records, system operational health, and searchable activity table.
- **Error**: High-visibility banner stating "Unable to load dashboard metrics. Check local database connection", with a "Retry" button.
- **No Permission**: Clean access-restricted view stating "Your role does not have authorization to view operational dashboard metrics".

### S-02 Core operational workflow management and activity logging for DocuPulse Reader
- **Loading**: Form and table skeleton displaying field placeholders and action button outlines with shimmer animation.
- **Empty**: Clean workspace ready for data entry with autofocused input and primary "Core operational workflow management and activity logging for DocuPulse Reader" CTA button.
- **Populated**: Structured interactive view displaying validated records, operational status badges, and action controls.
- **Error**: High-contrast error callout detailing field validation failures or local SQLite query errors, with an actionable "Retry" button.
- **No Permission**: Access-restricted notification stating "Access restricted: Only authorized personnel ([P-01]) may perform this action".

### S-03 Structured local compliance report compilation and data export in DocuPulse Reader
- **Loading**: Form and table skeleton displaying field placeholders and action button outlines with shimmer animation.
- **Empty**: Clean workspace ready for data entry with autofocused input and primary "Structured local compliance report compilation and data export in DocuPulse Reader" CTA button.
- **Populated**: Structured interactive view displaying validated records, operational status badges, and action controls.
- **Error**: High-contrast error callout detailing field validation failures or local SQLite query errors, with an actionable "Retry" button.
- **No Permission**: Access-restricted notification stating "Access restricted: Only authorized personnel ([P-02]) may perform this action".

---

## 4. Navigation

- **Top Bar (Desktop Shell)**:
  - Left: Application logo + `DocuPulse Reader` branding link pointing to `S-01`.
  - Center: Global search input (`Cmd/Ctrl+K`) for rapid lookup in under 1.0 s (`[NFR-01]`).
  - Right: System status badge (Offline / Local SQLite mode), active user avatar (`[P-01], [P-02]`), and role badge.
- **Sidebar Navigation**:
  - `Dashboard & Activity Overview` → `S-01` (`/`)
  - `Core operational workflow management and activity logging for DocuPulse Reader` → `S-02` (`/core-operational-wor`)
  - `Structured local compliance report compilation and data export in DocuPulse Reader` → `S-03` (`/structured-local-com`)
- **Footer / Status Bar**:
  - Database status: `Local SQLite (Active WAL Mode)`
  - Storage directory: `Local File System (100% offline, zero cloud)`
  - Version: `v1.0.0 (DocuPulse Reader MVP)`

---

## 5. Keyboard and focus

- **Logical Tab Order**: Every form and interactive data table follows standard DOM order: Top Bar Search → Main Navigation → Primary Content Inputs → Action Buttons.
- **Visible Focus Rings**: All interactive controls display high-contrast 2px focus rings (`--color-primary`, contrast ratio > 4.5:1) meeting WCAG 2.2 AA standards (`[NFR-05]`).
- **Keyboard Shortcuts**:
  - `Cmd/Ctrl + K`: Focus global search input.
  - `Cmd/Ctrl + N`: Trigger primary creation action (`S-02`).
  - `Esc`: Close modal dialogs and slide-over panels.
  - `Enter`: Submit active form or confirm modal dialog.
  - `Arrow Up / Down`: Navigate table rows and dropdown select options.
