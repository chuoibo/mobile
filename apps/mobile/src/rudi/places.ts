/** Place search and category filter for the RuDi explore screens. */

export type PlaceCategory = "Quán ăn" | "Cafe" | "Vui chơi" | "Đi chơi đêm";

export const PLACE_CATEGORIES: readonly PlaceCategory[] = [
  "Quán ăn",
  "Cafe",
  "Vui chơi",
  "Đi chơi đêm",
];

export type FilterablePlace = {
  id: string;
  name: string;
  subtitle: string;
  tags: readonly string[];
  category: PlaceCategory;
  match: number;
  distance: string;
};

function fold(value: string): string {
  return value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .trim()
    .toLowerCase();
}

export function distanceKm(distance: string): number {
  const numeric = Number(distance.replace(",", ".").replace(/[^0-9.]/g, ""));
  return distance.includes("km") ? numeric : numeric / 1000;
}

export function filterPlaces<T extends FilterablePlace>(
  places: readonly T[],
  input: {
    query?: string;
    category?: PlaceCategory | null;
    matchOnly?: boolean;
    nearOnly?: boolean;
    savedOnly?: boolean;
    savedIds?: readonly string[];
  },
): T[] {
  const needle = fold(input.query ?? "");
  const saved = input.savedIds ?? [];
  return places.filter((place) => {
    const haystack = fold([place.name, place.subtitle, ...place.tags].join(" "));
    return (
      (!needle || haystack.includes(needle)) &&
      (!input.category || place.category === input.category) &&
      (!input.matchOnly || place.match >= 90) &&
      (!input.nearOnly || distanceKm(place.distance) <= 2) &&
      (!input.savedOnly || saved.includes(place.id))
    );
  });
}
