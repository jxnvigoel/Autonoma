# Design Brief: DocuPulse Reader

Based on Handbook Appendix A.5 (`VirtualOffice_Complete_Guide.md`), `docs/prd.md`, and WCAG 2.2 AA accessibility requirements.

---

## 1. Identity

| Field | Choice | Source |
|---|---|---|
| Style | High-Contrast Clean Desktop Application | `[Q-001]` |
| Personality | Professional, disciplined, high-density, precise | `[Q-001]` |
| Inspiration | Modern local desktop operational workstations | `[ASM-01]` |
| Target Feel | Fast, trustworthy, error-preventing desktop tool built for Biomedical research scientists and lab technicians | `[Q-001]` |

---

## 2. Colours

**Theme Support**: Both Light and Dark themes supported (`--theme-light`, `--theme-dark`).  
**Accessibility Bar**: Every foreground text and interactive token passes WCAG 2.2 AA minimum contrast (>= 4.5:1 for normal text, >= 3:1 for large text/components).

| Token | Light | Dark | Use | Contrast on Background |
|---|---|---|---|---|
| `--color-primary` | `#0369a1` | `#38bdf8` | Primary buttons, active links, key CTAs | 5.7:1 (L) / 8.3:1 (D) |
| `--color-secondary` | `#475569` | `#64748b` | Secondary buttons, subtle borders | 7.2:1 (L) / 3.8:1 (D) |
| `--color-background` | `#f8fafc` | `#0f172a` | App window page background | Baseline Surface |
| `--color-surface` | `#ffffff` | `#1e293b` | Cards, panels, modal dialogs | Baseline Surface |
| `--color-border` | `#cbd5e1` | `#334155` | Card dividers, input borders | Baseline Surface |
| `--color-text` | `#0f172a` | `#f8fafc` | Headings, body paragraphs, form labels | 17.1:1 (L) / 17.1:1 (D) |
| `--color-text-muted` | `#334155` | `#94a3b8` | Captions, table headers, metadata | 9.9:1 (L) / 7.0:1 (D) |
| `--color-error` | `#b91c1c` | `#f87171` | Error notices, warning banners, input validation | 6.2:1 (L) / 6.5:1 (D) |
| `--color-success` | `#15803d` | `#4ade80` | Successful operation alerts, confirmation feedback | 4.8:1 (L) / 10.2:1 (D) |

---

## 3. Typography

| Role | Font Family | Weight | Size / Line Height | Notes |
|---|---|---|---|---|
| `Display` | Inter, system-ui, sans-serif | 700 (Bold) | 28px / 36px | Dashboard hero and welcome title |
| `H1` | Inter, system-ui, sans-serif | 600 (Semi-Bold) | 22px / 28px | Page titles and primary screen headers |
| `H2` | Inter, system-ui, sans-serif | 600 (Semi-Bold) | 18px / 24px | Section cards and panel titles |
| `H3` | Inter, system-ui, sans-serif | 600 (Semi-Bold) | 15px / 20px | Sub-panel headings and modal headers |
| `Body` | Inter, system-ui, sans-serif | 400 (Regular) | 14px / 20px | Table content, form labels, descriptions |
| `Label` | Inter, system-ui, sans-serif | 500 (Medium) | 12px / 16px | Badge text, input field labels, tabs |
| `Code / Monospace` | JetBrains Mono, monospace | 400 (Regular) | 12px / 18px | Record identifiers, payload hashes |

---

## 4. Components

| Component | Default Style | Interaction States | Notes |
|---|---|---|---|
| `Button (Primary)` | Height 38px, radius 6px, bg `--color-primary`, text `#ffffff` | **Hover**: 10% dark overlay. **Focus**: 2px ring. **Disabled**: opacity 0.5. **Loading**: spinner icon. | Primary CTAs (Create, Export) |
| `Button (Secondary)` | Height 38px, radius 6px, border 1px `--color-border`, bg transparent | **Hover**: bg `--color-surface`. **Focus**: 2px ring. **Disabled**: opacity 0.5. | Cancel and secondary actions |
| `Button (Destructive)`| Height 38px, radius 6px, bg `--color-error`, text `#ffffff` | **Hover**: 10% dark overlay. **Focus**: 2px ring. **Disabled**: opacity 0.5. | Removal and deletion actions |
| `Input (Text/Number)` | Height 38px, radius 6px, border 1px `--color-border`, bg `--color-surface` | **Focus**: border `--color-primary`, ring 2px. **Error**: border `--color-error`. **Disabled**: bg muted. | Form and search inputs |
| `Card / Container` | Radius 8px, border 1px `--color-border`, bg `--color-surface`, shadow-sm | **Hover (interactive)**: border `--color-primary`, shadow-md. | Overview cards and unit monitors |
| `Badge / Chip` | Height 22px, radius 4px, font 11px Medium, padding 2px 8px | Specific variant tokens (Active = Success, Error = Error, Pending = Warning). | Status displays |
| `Modal Dialog` | Max width 540px, radius 12px, bg `--color-surface`, shadow-xl | Backdrop blur 2px, backdrop bg `rgba(0,0,0,0.5)`. Accessible focus trap. | Confirmation modals |
| `Data Table` | Row height 44px, border-b 1px `--color-border`, header bg `--color-background` | **Row Hover**: subtle highlight. Keyboard arrow navigable. | Primary record listings |
| `Toast Alert` | Fixed bottom-right, radius 8px, padding 12px 16px, auto-dismiss 4000ms | Progress bar indicator, close button, pause on hover. | Action confirmation alerts |

---

## 5. Layout

- **Base Spacing Unit**: 4px (`--space-1`: 4px, `--space-2`: 8px, `--space-3`: 12px, `--space-4`: 16px, `--space-6`: 24px, `--space-8`: 32px).
- **Application Window Shell**: Fixed top header (height 56px), collapsible navigation sidebar (width 240px expanded, 64px collapsed), scrollable content viewport.
- **Reading Width Limit**: Maximum reading content width constrained to 1280px to preserve scanability.

### Breakpoints & Responsive Behavior
| Breakpoint | Window Width | Layout Adaptation |
|---|---|---|
| `Mobile (< 640 px)` | < 640px | Sidebar collapses into off-canvas mobile drawer; data tables switch to stacked card view; touch targets expand to minimum 44px. |
| `Tablet (640–1024 px)`| 640px–1024px | Sidebar collapses to icon rail (64px width); top bar search collapses to icon trigger; 2-column dashboard grid. |
| `Desktop (> 1024 px)` | > 1024px | Full 240px persistent sidebar; expanded global search; 3-column dashboard metric layout; full multi-column data tables. |

---

## 6. UX Principles (Nielsen's Heuristics Applied)

1. **Visibility of System Status**: Every async user action displays instant feedback: skeleton loaders on initial screen load, inline progress spinners on form submission, and auto-dismissing toast notifications on success.
2. **2-Click Rule**: All primary operational workflows (Local document reader with smart highlight snippet tagging, One-click local bibliography citation export in BibTeX and Markdown formats, Tag-based search functionality) are accessible within 2 clicks from the Dashboard home screen.
3. **Helpful Error Messages**: Error messages use plain human language describing what happened and offering an explicit corrective action button; raw error codes and system stack traces are strictly hidden from users.
4. **Error Prevention**: Destructive or irreversible state changes require explicit confirmation dialogs with double-confirmation CTAs.
5. **Recognition Over Recall**: Statuses, classifications, and parameters are presented via selectable dropdowns and filter chips rather than free-form typing.
6. **Full Keyboard Accessibility (WCAG 2.2 AA)**: All interactive controls are navigable via keyboard with visible focus rings and logical tab order (`[NFR-05]`).
