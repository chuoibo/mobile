/**
 * The journal's two materials, as repeatable tiles (see assets/textures/README.md).
 * Rendered by `ui/Grain.tsx` at low opacity over the token colour, so the colour a
 * test measures is still the token; the tile only adds the surface.
 */
export const chatLieu = {
  /** Indigo cloth of the cover. */
  vaiBia: require("../../assets/textures/vai-bia.png") as number,
  /** Paper of the pages. */
  giayTrang: require("../../assets/textures/giay-trang.png") as number,
};
