// Local edit description. The source image is never modified; every render
// applies one Adjustments value to the immutable source (see docs/adr/0003).

export type LookId = 'soft-warm' | 'cool-clean' | 'muted-film' | 'balanced-mono';
export type CropAspect = 'original' | '1:1' | '4:5' | '9:16';

export interface Adjustments {
  readonly brightness: number;
  readonly contrast: number;
  readonly saturation: number;
  readonly warmth: number;
  readonly look: LookId | null;
  readonly lookIntensity: number;
  readonly crop: CropAspect;
}

export type SliderKey = 'brightness' | 'contrast' | 'saturation' | 'warmth' | 'lookIntensity';

export interface SliderSpec {
  readonly key: SliderKey;
  readonly label: string;
  readonly min: number;
  readonly max: number;
}

export const SLIDERS: readonly SliderSpec[] = [
  { key: 'brightness', label: 'Brightness', min: -1, max: 1 },
  { key: 'contrast', label: 'Contrast', min: -1, max: 1 },
  { key: 'saturation', label: 'Saturation', min: -1, max: 1 },
  { key: 'warmth', label: 'Warmth', min: -1, max: 1 },
];

export const LOOK_INTENSITY: SliderSpec = { key: 'lookIntensity', label: 'Look strength', min: 0, max: 1 };

export const LOOKS: readonly { readonly id: LookId; readonly label: string }[] = [
  { id: 'soft-warm', label: 'Soft Warm' },
  { id: 'cool-clean', label: 'Cool Clean' },
  { id: 'muted-film', label: 'Muted Film' },
  { id: 'balanced-mono', label: 'Mono' },
];

export const CROPS: readonly { readonly id: CropAspect; readonly label: string }[] = [
  { id: 'original', label: 'Original' },
  { id: '1:1', label: 'Square' },
  { id: '4:5', label: '4:5' },
  { id: '9:16', label: '9:16' },
];

export const IDENTITY: Adjustments = Object.freeze({
  brightness: 0,
  contrast: 0,
  saturation: 0,
  warmth: 0,
  look: null,
  lookIntensity: 1,
  crop: 'original',
});

export class InvalidAdjustment extends Error {
  override readonly name = 'InvalidAdjustment';
}

function bounded(value: number, min: number, max: number, field: string): number {
  if (!Number.isFinite(value)) throw new InvalidAdjustment(`${field} must be finite`);
  return Math.min(max, Math.max(min, value));
}

const LOOK_IDS = new Set<string>(LOOKS.map((l) => l.id));
const CROP_IDS = new Set<string>(CROPS.map((c) => c.id));

export function normalizeAdjustments(a: Adjustments): Adjustments {
  if (a.look !== null && !LOOK_IDS.has(a.look)) throw new InvalidAdjustment('unknown look');
  if (!CROP_IDS.has(a.crop)) throw new InvalidAdjustment('unknown crop');
  return Object.freeze({
    brightness: bounded(a.brightness, -1, 1, 'brightness'),
    contrast: bounded(a.contrast, -1, 1, 'contrast'),
    saturation: bounded(a.saturation, -1, 1, 'saturation'),
    warmth: bounded(a.warmth, -1, 1, 'warmth'),
    look: a.look,
    lookIntensity: bounded(a.lookIntensity, 0, 1, 'lookIntensity'),
    crop: a.crop,
  });
}

export function sameAdjustments(a: Adjustments, b: Adjustments): boolean {
  return (
    a.brightness === b.brightness &&
    a.contrast === b.contrast &&
    a.saturation === b.saturation &&
    a.warmth === b.warmth &&
    a.look === b.look &&
    (a.look === null || a.lookIntensity === b.lookIntensity) &&
    a.crop === b.crop
  );
}

export function isIdentity(a: Adjustments): boolean {
  return sameAdjustments(a, IDENTITY);
}
