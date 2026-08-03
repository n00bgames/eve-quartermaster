import type { SkillDogmaDetails } from "../../types/skills";

type ApiClient = <T>(path: string, options?: RequestInit) => Promise<T>;

const CACHE_PREFIX = "eqm.skill-dogma.v4";
const CACHE_TTL_MS = 7 * 24 * 60 * 60 * 1000;
const memoryCache = new Map<number, Promise<SkillDogmaDetails>>();

type StoredDogma = { expires_at: number; data: SkillDogmaDetails };

function cacheKey(typeId: number) {
  return `${CACHE_PREFIX}.${typeId}`;
}

function readStored(typeId: number): SkillDogmaDetails | null {
  try {
    const raw = window.localStorage.getItem(cacheKey(typeId));
    if (!raw) return null;
    const stored = JSON.parse(raw) as StoredDogma;
    if (stored.expires_at <= Date.now() || stored.data?.type_id !== typeId) {
      window.localStorage.removeItem(cacheKey(typeId));
      return null;
    }
    return stored.data;
  } catch {
    return null;
  }
}

function writeStored(typeId: number, data: SkillDogmaDetails) {
  try {
    window.localStorage.setItem(cacheKey(typeId), JSON.stringify({ expires_at: Date.now() + CACHE_TTL_MS, data }));
  } catch {
    // Storage can be unavailable or full. The in-memory cache still avoids repeat requests.
  }
}

export function loadSkillDogma(api: ApiClient, typeId: number): Promise<SkillDogmaDetails> {
  const existing = memoryCache.get(typeId);
  if (existing) return existing;
  const stored = readStored(typeId);
  const request = stored
    ? Promise.resolve(stored)
    : api<SkillDogmaDetails>(`/esi/skill-dogma/${typeId}?schema=4`).then((data) => {
        writeStored(typeId, data);
        return data;
      });
  memoryCache.set(typeId, request);
  request.catch(() => memoryCache.delete(typeId));
  return request;
}
