export interface GhostTransformState {
  scale: number;
  x: number;
  y: number;
}

export const GHOST_SCALE_MIN = 70;
export const GHOST_SCALE_MAX = 130;
export const GHOST_DEFAULT_SCALE = 100;
export const GHOST_DEFAULT_OPACITY = 40;
export const GHOST_MAX_OFFSET_RATIO = 0.4;

export function createDefaultGhostTransform(): GhostTransformState {
  return {
    scale: GHOST_DEFAULT_SCALE,
    x: 0,
    y: 0,
  };
}

export function clampGhostScale(scale: number): number {
  if (!Number.isFinite(scale)) return GHOST_DEFAULT_SCALE;
  return Math.min(GHOST_SCALE_MAX, Math.max(GHOST_SCALE_MIN, Math.round(scale)));
}

export function clampGhostOffset(value: number, frameDimension: number): number {
  if (!Number.isFinite(value)) return 0;
  if (!Number.isFinite(frameDimension) || frameDimension <= 0) return 0;
  const maxOffset = frameDimension * GHOST_MAX_OFFSET_RATIO;
  return Math.min(maxOffset, Math.max(-maxOffset, Math.round(value)));
}

export function clampGhostPosition(
  x: number,
  y: number,
  frameWidth: number,
  frameHeight: number,
): { x: number; y: number } {
  return {
    x: clampGhostOffset(x, frameWidth),
    y: clampGhostOffset(y, frameHeight),
  };
}

export function isGhostModified(
  scale: number,
  x: number,
  y: number,
  opacity: number,
): boolean {
  return (
    scale !== GHOST_DEFAULT_SCALE ||
    x !== 0 ||
    y !== 0 ||
    opacity !== GHOST_DEFAULT_OPACITY
  );
}
