// The service sends at most 1536 px on the long edge to the AI provider, so larger uploads only
// cost bandwidth and risk the 4 MB request limit.
export const UPLOAD_MAX_EDGE = 1536;

export function uploadSize(width: number, height: number): { width: number; height: number } {
  const longEdge = Math.max(width, height);
  if (longEdge <= UPLOAD_MAX_EDGE) return { width, height };
  const k = UPLOAD_MAX_EDGE / longEdge;
  return { width: Math.max(1, Math.round(width * k)), height: Math.max(1, Math.round(height * k)) };
}

// Output aspect the service picks for an input (mirrors choose_size in apps/style-api/styleapi/images.py).
export function outputAspect(width: number, height: number): number {
  const ratio = width / height;
  if (ratio >= 1.2) return 1536 / 1024;
  if (ratio <= 1 / 1.2) return 1024 / 1536;
  return 1;
}
