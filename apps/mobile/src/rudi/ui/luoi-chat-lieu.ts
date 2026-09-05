/**
 * Tile grid for a material layer (`ui/Grain.tsx`).
 *
 * One tile is the texture PNG at device pixels, so the grain is never blurred
 * by scaling; on a large surface the tile doubles until the layer needs at
 * most `maxTiles` views. Pure so node can pin the arithmetic: the grid must
 * cover the box, and a screen must not turn into hundreds of image views.
 */
export interface LuoiChatLieu {
  /** Tile side in dp; 0 when the box has no size yet. */
  tile: number;
  cols: number;
  rows: number;
}

export function luoiChatLieu(w: number, h: number, pixelRatio: number, tilePx = 256, maxTiles = 60): LuoiChatLieu {
  if (!(w > 0) || !(h > 0)) return { tile: 0, cols: 0, rows: 0 };
  let tile = tilePx / Math.max(1, pixelRatio);
  let cols = Math.ceil(w / tile);
  let rows = Math.ceil(h / tile);
  while (cols * rows > maxTiles) {
    tile *= 2;
    cols = Math.ceil(w / tile);
    rows = Math.ceil(h / tile);
  }
  return { tile, cols, rows };
}
