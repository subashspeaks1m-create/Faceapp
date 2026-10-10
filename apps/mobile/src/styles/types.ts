// Public style catalog shapes. Must match public_catalog() in apps/style-api/styleapi/catalog.py.

export type CategoryId = 'retro' | 'illustration' | 'cinematic' | 'editorial' | 'artistic';

export interface StyleCategory {
  readonly id: CategoryId;
  readonly name: string;
  readonly summary: string;
}

export interface IntensityBand {
  readonly min: number;
  readonly max: number;
  readonly label: string;
}

export interface StyleInfo {
  readonly id: string;
  readonly number: number;
  readonly name: string;
  readonly category: CategoryId;
  readonly summary: string;
  readonly tags: readonly string[];
  readonly default_intensity: number;
  readonly swatch: readonly [string, string, string];
}

export interface PublicCatalog {
  readonly version: string;
  readonly categories: readonly StyleCategory[];
  readonly intensity_bands: readonly IntensityBand[];
  readonly styles: readonly StyleInfo[];
}

// Error codes returned by the style API, plus client-side codes for failures before a response.
export type StyleErrorCode =
  | 'INVALID_IMAGE'
  | 'UNSUPPORTED_IMAGE_FORMAT'
  | 'IMAGE_TOO_LARGE'
  | 'INVALID_STYLE'
  | 'INVALID_REQUEST'
  | 'CONSENT_REQUIRED'
  | 'ORIGIN_NOT_ALLOWED'
  | 'PROVIDER_NOT_CONFIGURED'
  | 'RATE_LIMITED'
  | 'PROVIDER_TIMEOUT'
  | 'PROVIDER_REJECTED'
  | 'PROVIDER_ERROR'
  | 'INVALID_PROVIDER_RESPONSE'
  | 'GENERATION_UNAVAILABLE'
  | 'INTERNAL_ERROR'
  | 'NOT_CONNECTED'
  | 'NETWORK_ERROR'
  | 'CANCELED';
