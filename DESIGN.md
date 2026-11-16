---
version: alpha
name: bobBuilder-drafting-table
description: The bobBuilder workspace reads as engineering software. Light theme is a drafting table (white panels on a light grey desk, hairline rules, square corners, one blue). Dark theme borrows quiet night-shift panels with a lighter blue. Drawings stay white paper in both themes. Mono type marks data.

colors:
  light:
    canvas: "#f4f4f4"
    surface: "#ffffff"
    surface-2: "#e8e8e8"
    surface-3: "#e0e0e0"
    line: "#e0e0e0"
    line-strong: "#8d8d8d"
    ink: "#161616"
    ink-2: "#525252"
    ink-3: "#8d8d8d"
    accent: "#0f62fe"
    accent-soft: "#edf5ff"
    on-accent: "#ffffff"
    bar: "#161616"
    on-bar: "#f4f4f4"
  dark:
    canvas: "#0c0d10"
    surface: "#121318"
    surface-2: "#1c1e25"
    surface-3: "#262932"
    line: "#22252c"
    line-strong: "#3a3e47"
    ink: "#e6e7eb"
    ink-2: "#8b909a"
    ink-3: "#5f6570"
    accent: "#78a9ff"
    accent-soft: "rgba(120,169,255,0.14)"
    on-accent: "#0c0d10"
    bar: "#121318"
    on-bar: "#e6e7eb"
  both:
    paper: "#ffffff"
    paper-mark: "#0f62fe"
  status:
    ok: { light: "#198038", dark: "#4cc38a" }
    warn: { light: "#8e6a00", dark: "#e0b03c" }
    danger: { light: "#da1e28", dark: "#ff8389" }

typography:
  text: IBM Plex Sans, system-ui, Helvetica Neue, Arial, sans-serif
  mono: IBM Plex Mono, ui-monospace, Menlo, Consolas, monospace
  scale:
    display-lg: { size: 32px, weight: 600, lineHeight: 40px }
    heading: { size: 16px, weight: 600, lineHeight: 24px }
    answer: { size: 15px, weight: 400, lineHeight: 22px }
    body: { size: 14px, weight: 400, lineHeight: 20px }
    body-sm: { size: 13px, weight: 400, lineHeight: 18px }
    label-mono: { size: 11px, weight: 500, lineHeight: 16px, letterSpacing: 0.08em, transform: uppercase }

rounded:
  default: 0px
  badge: 2px

spacing: [4px, 8px, 12px, 16px, 24px, 32px, 48px]
---

## Overview

bobBuilder answers questions about construction drawings and points to the exact spot each answer came from. Its users are engineers, architects and property people who already live in CAD and BIM tools, so the interface borrows that world: a dark app bar, white panels, hairline rules, square corners and one blue for whatever is active. Nothing is decorative. The drawing is the hero; the chrome around it stays quiet.

Tokens live in `frontend/src/styles/tokens.css`. Change values here first, then there. Components use tokens only, never literal colours.

## Colors

- **One accent.** Blue marks the active tab, the selected document, primary buttons, focus rings, citation chips and the cited region. Nothing else uses it.
- **Status is not the accent.** Green means verified or ready, amber means not verified, red means failed. Each status shows as a coloured chip or label, never by fill vs outline alone.
- **Paper stays paper.** Scanned and rendered sheets are white in both themes (`paper`). Marks drawn on a sheet use `paper-mark`, which does not change with the theme. Inverting a sheet is reserved for the clean redraw view (#54).
- **Dark theme** keeps the same roles with deeper panels and a lighter blue so the accent keeps contrast on dark surfaces. It follows the OS until the user toggles it in the app bar; the choice is remembered.

## Typography

IBM Plex Sans for everything people read; IBM Plex Mono for things that are data: file names, sheet and page numbers, zoom levels, sizes in mm, status labels, tool steps and section labels. Section labels are mono, 11 px, uppercase with 0.08em tracking. There is one display size, used only on the empty state.

## Layout

- App bar (48 px): wordmark, breadcrumb of the open document, theme toggle, upload.
- Workspace: documents (260 px) · stage (flexible) · ask panel (400 px). Below 1120 px the ask panel moves under the stage; below 768 px everything stacks.
- Panels are white (`surface`) separated by 1 px `line` rules; the stage behind the sheet is the `canvas` desk.

## Shapes and depth

Square corners everywhere; badges get 2 px. No drop shadows on panels or cards. Hierarchy comes from rules, fills and one inset accent edge: the selected document row has a 3 px left accent bar, the latest answer a 2 px top accent rule.

## Components

- **Buttons:** 36 px (28 px small), square. Primary is accent fill; secondary is a 1 px `line-strong` outline; subtle has no chrome until hover. App-bar buttons use the bar colours.
- **Tabs:** text tabs with a 2 px accent underline when active.
- **Document row:** file name, then a mono kind tag and a coloured status. A 2 px progress bar while reading.
- **Answer:** only the latest answer is a card. Older turns are plain text in `ink-2`. Tool steps stream in mono. Badges: verified (ok), not verified (warn), confidence and cached (plain).
- **Citation chip:** accent-soft fill with a square numbered tile. The number matches the mark on the drawing. Unverified citations are outlined and struck through.
- **Drawing overlay:** a cited region gets a `paper-mark` ring and the rest of the sheet dims (D-007's spotlight, now in blue).
- **Redrawn page:** an Original / Redrawn switch above the plan. Before a page is upscaled, Redrawn shows one centred **Upscale** button over the dimmed page. Every page whose `redraw_mode` is `plan` gets it: PDF, SVG and CAD pages, and raster images that look printed (colour fills, dimensions, ruled lines on even paper) (D-054). The redraw is white paper like the original: walls solid `redraw-line`, rooms as faint `redraw-room` outlines with the name in bold and the area underneath in mono, doors and windows as outlined boxes, all text at one size per page, and a scale bar top left. What the upscale pass added is dashed in `redraw-added`. One overlay serves both views (D-027).
- **Redrawn sketch** (raster image pages whose `redraw_mode` is `sketch`: photos of hand drawings, and images ingested before D-054): the button says **Redraw**, and while the model works a status line says it takes a few minutes. The redraw shows only the model's plan: walls filled `redraw-line` with a gap at each opening (outer walls thicker), doors as an open leaf plus a quarter-circle swing, windows as a thin double line across the wall with end ticks, room names bold and centred at one size. No scale bar, no areas, no dimensions unless written on the sketch. While Redrawn is on screen the toolbar offers **Download SVG** (a standalone light file) and **Print** (only the sheet, fitted to the paper) (D-028).
- **3D:** the canvas is transparent over the desk colour; the cited element turns `paper-mark` blue in both themes (three.js materials can't read CSS tokens, so the value is repeated in `ModelViewer.tsx`).

## Accessibility

Focus is a 2 px accent outline on every control, offset outside filled primary buttons. Text on surfaces meets WCAG AA in both themes. Motion is limited to the progress bar and is removed under `prefers-reduced-motion`.
