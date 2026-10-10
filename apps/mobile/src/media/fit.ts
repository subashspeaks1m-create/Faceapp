// Largest size with the same aspect whose pixel count is within maxPixels.
export function fitWithinPixels(width: number, height: number, maxPixels: number): { width: number; height: number } {
  if (width * height <= maxPixels) return { width, height };
  const k = Math.sqrt(maxPixels / (width * height));
  let w = Math.floor(width * k);
  let h = Math.floor(height * k);
  while (w * h > maxPixels) {
    if (w >= h) w--;
    else h--;
  }
  return { width: Math.max(1, w), height: Math.max(1, h) };
}
