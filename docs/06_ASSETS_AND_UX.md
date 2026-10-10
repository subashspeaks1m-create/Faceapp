# 6. Asset inventory and UX tokens

`assets/design-tokens.json` is the machine-readable source: dark canvas, elevated surfaces, primary violet, accent mint, high contrast text, Inter/system fonts,8-based space scale with4px steps,44pt iOS/48dp Android targets, restrained120–240ms motion and reduced-motion bypass. Measure contrast for every actual foreground/background pair; numeric token names don't prove WCAG compliance. Always label sliders with numeric value; magic icons have text labels. Compare gesture has accessible Before/After toggle, not just drag.

## Included assets

- Four required original vector SVGs, plus the supplementary icon set: magic-wand.svg, sliders.svg, compare.svg, download.svg. viewBox0 0 24 24, currentColor stroke, round caps/joins. Wrap with react-native-svg or use web directly; don't insert raw SVG markup as React Native views.
- Twelve filters in filters.json with stable IDs, categories, icon references, defaults and explicit model routes. Thirteen primitive capabilities are represented by12 launch tiles because makeup and smoothing share Beauty Retouch controls. All presets currently blocked pending approved weights/quality/latency, regardless of presence of preview assets.
- Inter variable font + SIL OFL license, reused from the prior kit. Prefer native system text if font load fails. Font is actual bundled TTF, not a link-only resource.
- Original synthetic adult portrait PNG1024x1536, provenance note. Development layout/demo fixture only; no real identity or release dataset. No model-generated before/after claim is implied. Prior kit contains additional original illustrations/thumbnail placeholders; The standalone v2 bundle also includes the original supplementary icons, brand vector sources,8 background SVGs and4 local color LUTs.

## States to implement

Onboarding/privacy consent, library/camera, selected-face picker, editor with filter tray/intensity/compare/apply/reset, processing with actual stages/cancel, offline/network/retry/permission/no-face/pose/filter-unavailable states, export/share, quota/purchase/restore, privacy deletion tracker, minimal metadata admin. Background upload, last-writer-wins candidate revision, cancellation and purge override late results. Preserve immutable source plus accepted edit history; a candidate does not mutate the source. Every export operates on selected committed result and retains source dimensions unless a documented export option says otherwise.

## Remaining production assets

Approved inference weights/dense-landmark artifact/model prompt versions, licensed evaluation set with participant consent, independently designed final brand/app icon variants, screenshots from actual devices, translations, real legal policy/support URLs, billing products and signing certificates. The bundle cannot manufacture commercial weight rights, processor agreements or credentials. These are enumerated resource gates, not hidden TODOs.
