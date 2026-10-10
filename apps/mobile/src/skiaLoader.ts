// Native platforms link Skia at build time; nothing to load.
export function loadSkia(): Promise<void> {
  return Promise.resolve();
}
