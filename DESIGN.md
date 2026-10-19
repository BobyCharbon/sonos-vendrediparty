---
name: "Vendredi Party — L’île qui s’effondre"
description: "Tropical playable 3D island surface; scoped to this game only."
colors:
  action-green: "#235d4b"
  action-hover: "#164534"
  deep-teal: "#16444c"
  ink: "#163d3a"
  body-ink: "#365c53"
  muted-ink: "#496b5d"
  cream-panel: "rgba(255,247,229,.98)"
  cream-text: "#fff9e7"
  title-cream: "#fff8db"
  title-gold: "#ffe095"
  sky: "#b8e5eb"
  grass: "#81a947"
  stone: "#a88c67"
  sand: "#e7c990"
  danger-orange: "#f36a12"
  fracture: "#76250b"
  local-marker: "#ffffff"
typography:
  display:
    fontFamily: "Bricolage Grotesque, sans-serif"
    fontSize: "clamp(28px,4.6vw,58px)"
    lineHeight: 0.96
    letterSpacing: "-0.035em"
  headline:
    fontFamily: "Bricolage Grotesque, sans-serif"
    fontSize: "29px"
    lineHeight: 1.08
    letterSpacing: "-0.025em"
  body:
    fontFamily: "inherit"
    fontSize: "14px"
    lineHeight: 1.5
  label:
    fontFamily: "inherit"
    fontSize: "12px"
    fontWeight: 600
  clock:
    fontFamily: "inherit"
    fontSize: "30px"
    lineHeight: 1
rounded:
  button: "10px"
  panel: "16px"
  hint: "12px"
  status: "30px"
  pill: "20px"
  circle: "50%"
spacing:
  small: "8px"
  medium: "12px"
  standard: "16px"
  mobile-panel: "20px"
  panel: "24px"
components:
  button-primary:
    backgroundColor: "{colors.action-green}"
    textColor: "{colors.cream-text}"
    rounded: "{rounded.button}"
    padding: "14px 16px"
    width: "100%"
  button-primary-hover:
    backgroundColor: "{colors.action-hover}"
  panel:
    backgroundColor: "{colors.cream-panel}"
    textColor: "{colors.ink}"
    rounded: "{rounded.panel}"
    padding: "24px"
  stats:
    backgroundColor: "#16444ce8"
    textColor: "{colors.cream-text}"
    rounded: "{rounded.status}"
    padding: "12px 22px"
  jump:
    backgroundColor: "#16444cb3"
    textColor: "#fffbed"
    rounded: "{rounded.circle}"
    width: "108px"
    height: "108px"
---

# Design System: L’île qui s’effondre

## Overview

**Creative North Star: "The approved tropical island"**

This document applies only to L’île qui s’effondre, implemented in `app/static/island.css`, `island-scene.js`, and `island.js`. It does not establish a redesign of other Vendredi Party games or the shared shell. The approved tropical concept supplies the world: turquoise sea, grassy rocky islands, friendly colorful characters, cream panels, and green actions.

The arena is real, readable, playable 3D. Its current geometry is deliberately simpler than the approved concept illustration; the illustration is visual direction, not a claim of rendering parity. Large controls and clear identity cues support each player on an individual phone, with keyboard controls on desktop.

**Key Characteristics:**
- A turquoise ocean around grassy hexagonal rock platforms.
- Warm cream information surfaces above the scene.
- Colorful rounded characters with a separate white local-player arrow.
- Readable danger through orange terrain and thick geometric fractures.

## Colors

### Primary
Action green belongs to launch, join, and replay buttons. Its darker hover variant preserves the same role.

### Secondary
The turquoise ocean is a procedural shader, interpolating linear RGB vectors `(0.025, 0.48, 0.58)` and `(0.10, 0.73, 0.74)` before tone mapping. These are rendering inputs, not CSS hex equivalents. Sky fog, grassy tops, sandy rims, and warm stone establish the tropical setting. Grass has four observed material variants; the frontmatter records the first representative material.

### Tertiary
Danger orange marks platforms approaching collapse; the dark fracture material provides a second cue. Player colors are identity accents, shared by roster dots and characters, not action states.

### Neutral
Cream panel and text surfaces contrast with deep teal HUD backgrounds and dark green ink. Gold accents the second title line. The local-player arrow is white with a dark outline.

**The Warning Rule.** Keep orange terrain and geometric fractures together so the warning survives without motion or color discrimination.

## Typography

Bricolage Grotesque supplies the expressive, tightly tracked game title and panel headings. Body copy and controls inherit the existing shell font; this game does not introduce another body family. Frontmatter captures observed desktop sizes, with compact overrides described below. Timer and result values use tabular numerals. Character names use a canvas-rendered bold sans-serif label and are capped at 16 characters visually.

## Layout

The game fills the viewport below the existing toolbar using a flex column and `100dvh`. The final scoped CSS overrides the earlier minimum-height declarations. The arena remains the background; title sits upper left, timer upper right, lobby/results panel lower left, and controls at opposite lower corners. Safe-area insets protect the toolbar and control edges.

At portrait widths up to 600px, the panel spans the width with 16px side margins and at most 46% height; its padding becomes 20px. The game title becomes 35px and panel title 25px. At landscape heights up to 600px, the panel is 285px wide with 16px padding, the timer becomes horizontal, and secondary hints disappear. Joystick/jump diameters shrink from 116px/108px to 92px/88px. The panel scrolls when necessary; long player names wrap.

## Elevation & Depth

Soft ambient shadows lift cream panels and touch controls above the arena. The panel uses `0 14px 35px #17434730`; the joystick knob uses `0 5px 12px #143e4940`. Near-opaque cream is intentional: it avoids observed WebGL occlusion artifacts on portrait screens. Keep that material instead of adding backdrop blur.

The scene uses an orthographic camera, flat-shaded rough materials, soft shadow maps, warm sunlight, hemisphere illumination, and distance fog. Hexagonal cliffs and sandy lips make platforms physically legible. Decorative ocean glints, warning shake, and foot motion stop under reduced motion; collapse movement still communicates game state.

## Shapes

Rounded rectangular panels and green buttons contrast with circular joystick and jump controls. Platform geometry is six-sided, with tapered irregular rocky walls and flat grassy tops. Characters use rounded capsule/sphere forms and small feet, eyes, and backpacks. Warning fractures are thick dark mesh segments, not unreliable thin WebGL lines.

## Components

- **Primary action:** full width, minimum 48px height, bold text, darker green hover. Disabled controls use 55% opacity. All buttons have a dark 3px focus outline with 4px offset.
- **Invitation action:** underlined text button, minimum 44px height, positioned below the invitation code. Preserve keyboard focus behavior.
- **Lobby/results panel:** near-opaque cream, rounded corners, limited scrolling height, and one clear host action. It disappears during active play. Results align names with tabular survival times.
- **Timer/status pill:** deep translucent teal, cream text, compact preparation/player-count context. Connection failure adds a pale warning surface and explicit reconnection text.
- **Joystick and jump:** opposite bottom corners; direct touch dragging and pressing. Jump has an arrow icon plus the word SAUT, a bright border, and a pressed scale of 0.95. Inactive controls fade and the jump button disables.
- **Character identity:** colored avatars plus name labels. The local white arrow is a separate sprite sized to 18 screen pixels, positioned beside the label, with depth testing disabled. Do not merge it back into the label artwork.
- **Terrain warning:** orange top, dark angular fracture, and optional small shake about three seconds before the fall. Keep the visual warning consistent with the written rules.
- **Failure state:** cream alert panel with a retry button for unavailable or interrupted WebGL. Do not replace the real scene with a background screenshot on failure.

No new input field or navigation component is defined by this game; the existing shell retains those responsibilities.

## Do's and Don'ts

### Do
- Do keep the arena and local character readable in portrait and landscape.
- Do preserve the cream panels, green actions, and tropical materials on this surface.
- Do pair orange danger with visible fractures and keep the white identity arrow separate from the name.
- Do keep touch controls, keyboard focus, and reduced-motion behavior available.

### Don't
- Don't apply this island-specific palette to unrelated games by default.
- Don't use a static concept image as a substitute for playable geometry.
- Don't make terrain warnings depend on color or shaking alone.
- Don't claim real-phone performance or concept-level fidelity from browser screenshots.
