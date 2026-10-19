---
name: Braquage en miniature
description: Scoped museum-night game design within Vendredi Party.
colors:
  action: "#533477"
  action-hover: "#3d245b"
  gold: "#e7b854"
  night: "#15213b"
  ink: "#19243a"
  paper: "rgba(255,247,229,.98)"
  light-text: "#fff9e7"
  exit: "#5ddfb0"
  prison: "#ef8fb2"
  laser: "#ff4568"
  switch: "#62dce0"
typography:
  display:
    fontFamily: '"Bricolage Grotesque", sans-serif'
    fontSize: "clamp(28px,4.6vw,58px)"
    lineHeight: 0.96
    letterSpacing: "-0.035em"
  title:
    fontFamily: '"Bricolage Grotesque", sans-serif'
    fontSize: "27px"
    lineHeight: 1.08
    letterSpacing: "-0.025em"
  body:
    fontFamily: 'system-ui, -apple-system, "Segoe UI", Roboto, sans-serif'
    fontSize: "14px"
    lineHeight: 1.5
rounded:
  button: "10px"
  map-choice: "9px"
  panel: "16px"
  minimap: "12px"
spacing:
  compact: "8px"
  regular: "12px"
  comfortable: "16px"
  panel: "24px"
components:
  button-primary:
    backgroundColor: "{colors.action}"
    textColor: "{colors.light-text}"
    rounded: "{rounded.button}"
    padding: "14px 16px"
  button-primary-hover:
    backgroundColor: "{colors.action-hover}"
  panel:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    rounded: "{rounded.panel}"
    padding: "24px"
---

# Design System: Braquage en miniature

## Overview

**Creative North Star: "Le musée miniature de nuit"**

A readable cartoon cutaway museum, with warm treasure against a blue night. This document records the implemented heist surface only. Its museum palette is the user's chosen extension; root DESIGN.md and .impeccable/design.json continue to describe L'île and are not replaced.

**Key Characteristics:**
- Authored 3D museum rooms with low walls and visible paths.
- Shared Bricolage headings, system text and tactile game controls.
- Compact objectives above the stage, with a persistent navigation plan.

## Colors

Primary violet identifies launch/replay actions and the catalogue tile; gold identifies valuables and architectural details. Night and warm paper separate the playable stage from instructions. Exit green, prison pink, laser red and switch cyan retain distinct semantic roles.

Three map identities come from the renderer: Galerie royale uses blue marble floors (#364f74 / #405c80) and blue walls (#314667); Cabinet des curiosités uses jade floors (#386567 / #487c78) and dark teal walls (#294c54); Aile des antiquités uses sandstone floors (#81634e / #98765a) and brown walls (#644e43). Their layouts and exhibits differ as well as their colors.

## Typography

Bricolage Grotesque carries the title and lobby heading; system UI carries instructions and controls. The display shrinks to 31px in portrait and 23px during portrait play. Panel titles become 23px in portrait and 22px in short landscape. Instructions become 12px on small screens. Timer and results use tabular numerals. Do not shrink contextual action text below the implemented 13px to fit a longer label.

## Layout

The shared toolbar takes its natural height; the stage fills the remaining 100dvh flex viewport. Respect safe-area insets for toolbar and controls. Portrait rules apply at widths up to 600px; short-landscape rules apply at heights up to 600px.

The lobby is a bounded flex panel. Only its content scrolls; its nonshrinking footer retains the launch/replay button outside the scrollable content. Portrait uses 16px panel insets and a maximum height of 52%; short landscape uses a 290px-wide panel. Verify the footer at 320px and 390px portrait and short landscape.

The orthographic camera follows the local player in play/countdown when aspect ratio is below .85 or canvas height below 500px. It deliberately crops the museum while a complete minimap remains visible. Otherwise the camera shows the wider museum. The minimap is 144×128px on desktop, 99×88px in portrait and 90×80px in short landscape.

## Elevation & Depth

Physical cutaway geometry, moonlight and low wall caps establish depth in the scene. The near-opaque paper panel uses a soft ambient shadow; avoid replacing it with backdrop blur because the current opacity prevents WebGL occlusion artifacts. The danger vignette conveys exposure without intercepting input.

## Shapes

Soft rectangular panels and map choices contrast with circular joystick/action controls. Treasure, museum cases and low walls provide the scene's geometry. The local player's white arrow remains visually distinct from colored player bodies and names.

## Components

- **Primary action:** full width, minimum 48px height, violet with a darker hover. Disabled opacity is .55. All buttons use a 3px ink focus outline with 4px offset.
- **Map choice:** stacked name and subtitle, selected violet border and pale violet fill; aria-pressed communicates selection. Only the host can change maps.
- **Invite control:** underlined green text with a 44px minimum target, next to the room code.
- **HUD:** dark rounded timer/count container, separate connection status, and shared objective text.
- **Touch controls:** 116px joystick and 108px contextual action; 92px/88px in short landscape. Active action darkens green and scales to .95. Reduced-motion mode removes CSS transitions.
- **Minimap:** full museum outline, gold loot, green exit, pink prison, white local-player marker and other player colors. It remains independent of follow-camera cropping.

## Do's and Don'ts

- **Do** keep the launch action in the panel footer outside scrolling content.
- **Do** retain readable local-player markers, objectives and navigation while the camera follows.
- **Do** preserve the three museums' distinct materials and layouts.
- **Don't** propagate this museum palette to other games.
- **Don't** treat browser verification as real-phone or deployment validation.
