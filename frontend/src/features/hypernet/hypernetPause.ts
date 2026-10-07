import type { HyperNetMeta, HyperNetPause } from "../../types/hypernet";

export function hypernetPaused(pause: HyperNetPause | undefined, characterId?: number) {
  return Boolean(pause?.account_paused || (characterId != null && pause?.characters.some(row => row.id === characterId && row.effective_paused)));
}

export function recordingCharacters(meta: HyperNetMeta) {
  return meta.seller_characters.filter(row => !hypernetPaused(meta.pause, row.id));
}
