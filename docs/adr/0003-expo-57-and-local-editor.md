# ADR 0003: Current Expo SDK and the on-device editor

Status: accepted (owner decision, 2026-10-10)

## Problem

The specification pinned a legacy track: Expo 53 / React Native 0.79 / Reanimated 3.17.5, with VisionCamera 4. Reanimated 3 is no longer actively maintained and the spec says leaving that track requires an ADR. Expo 57 is the current release (npm `latest`, 2026-10-10).

## Decision

The owner chose to move to the current stable Expo SDK. Versions are the ones Expo 57's `bundledNativeModules.json` names, confirmed with `expo install --check`:

| Package | Version |
|---|---|
| expo | ~57.0.27 |
| react / react-native | 19.2.3 / 0.86.3 (New Architecture, Hermes) |
| react-native-reanimated / react-native-worklets | 4.5.1 / 0.10.1 |
| @shopify/react-native-skia | 2.6.2 |
| expo-router | ~57.0.25 |

Babel: `babel-preset-expo` adds the worklets plugin; the explicit Reanimated 3 plugin was removed.

Capture: VisionCamera was dropped. VisionCamera 5 requires Nitro modules and is not part of the Expo SDK map. Photos come from the system picker and the system camera through `expo-image-picker` (camera permission requested only when the user taps Take photo). An in-app camera can be added later behind its own ADR.

## On-device editor

- Source: picked file is decoded once by `expo-image-manipulator`, orientation applied, downscaled only if above 24 MP (the user is told), and re-encoded as PNG without metadata. That PNG is the immutable source.
- One render path (`apps/mobile/src/editor/render.ts`) for preview and export. Chain: crop (centered, integer source pixels) → 3D LUT look (17³, trilinear SkSL shader, blended by strength) → colour matrix (warmth → brightness → contrast → saturation) → scale (preview only).
- Candidate/committed: sliders change a candidate; Apply commits it to history, Discard drops it. Undo/Redo walk committed history. Reset is a candidate. Export renders the committed edit at the crop rect's source resolution as JPEG (quality 95) and opens the share sheet.
- Compare: an accessible Before/After toggle plus press-and-hold on the photo.

## Verification

`npm test --workspace=@portraitlab/mobile` runs `render.ts` unchanged on CanvasKit (Skia's WASM build, via React Native Skia's web API) and compares exported pixels with a CPU reference: identity export is bit-exact at source size, colour adjustments within 1/255, every LUT within 2/255, and the preview picture is bit-identical to export at scale 1. Metro bundles for iOS and Android (`expo export`) and `expo prebuild` generates both native projects. No device or simulator run has happened.

## Consequences

- Security: moving to Expo 57 did not clear `npm audit`. 44 advisories remain in the build toolchain (Expo CLI, Metro, Jest, prebuild). For node-forge, braces and sprintf-js no patched release exists at all. The one in app runtime code is decode-uri-component (via expo-router's query-string), a denial of service on malformed links. npm's suggested "fixes" are downgrades to years-old majors and were not applied.
- Specification text still names Reanimated 3 and VisionCamera; this ADR supersedes those lines.
