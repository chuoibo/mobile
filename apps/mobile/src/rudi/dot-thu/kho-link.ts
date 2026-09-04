/**
 * Where a round's guest links live on this phone.
 *
 * The server keeps only a digest of each guest token, so the publish response
 * is the only copy of the links that will ever exist. The organiser who
 * published a round keeps them here, per batch, so a restart does not lose
 * the one thing the round was for. A phone that never published the round
 * finds nothing here, and the screen has to say so rather than invent a link.
 *
 * Kept apart from `dot-thu.ts` so the bridge stays loadable in node tests:
 * AsyncStorage is a native module.
 */
import AsyncStorage from "@react-native-async-storage/async-storage";

import type { Envelope } from "./dot-thu";

function khoa(batchId: string): string {
  return `rudi.dot-thu.link.${batchId}`;
}

export async function luuLinkDot(batchId: string, envelopes: Envelope[]): Promise<void> {
  await AsyncStorage.setItem(khoa(batchId), JSON.stringify(envelopes));
}

/** `null` when this phone never published the round (or the store was cleared). */
export async function docLinkDot(batchId: string): Promise<Envelope[] | null> {
  const raw = await AsyncStorage.getItem(khoa(batchId));
  if (raw === null) return null;
  try {
    const parsed: unknown = JSON.parse(raw);
    return Array.isArray(parsed) ? (parsed as Envelope[]) : null;
  } catch {
    return null;
  }
}
