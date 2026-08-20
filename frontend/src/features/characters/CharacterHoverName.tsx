import { X } from "lucide-react";
import { useCallback, useEffect, useLayoutEffect, useRef, useState, type ReactElement } from "react";
import { createPortal } from "react-dom";

import { PilotSecurityStatus } from "./PilotSecurityStatus";
import type { CharacterFocus, CharacterSummary } from "../../types/characters";

type ApiClient = <T>(path: string, options?: RequestInit) => Promise<T>;
type EveEntityKind = "character" | "corporation" | "alliance";
type EveIconSize = "tiny" | "sm" | "md" | "lg";
type EveEntityIconComponent = (props: { kind: EveEntityKind; id?: number | null; name?: string | null; size?: EveIconSize }) => ReactElement;

export type CharacterHoverNameProps = {
  characterId?: number | null;
  name: string;
  className?: string;
  href?: string;
};

type CharacterHoverNameComponentProps = CharacterHoverNameProps & {
  api: ApiClient;
  EveEntityIcon: EveEntityIconComponent;
  numberFormatter: Intl.NumberFormat;
};

export function CharacterHoverName({ characterId, name, className = "", href, api, EveEntityIcon, numberFormatter }: CharacterHoverNameComponentProps) {
  const [open, setOpen] = useState(false);
  const [summary, setSummary] = useState<CharacterSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [position, setPosition] = useState({ left: 12, top: 12 });
  const triggerRef = useRef<HTMLButtonElement>(null);
  const cardRef = useRef<HTMLDivElement>(null);

  const positionCard = useCallback(() => {
    if (!triggerRef.current || !cardRef.current) return;

    const anchor = triggerRef.current.getBoundingClientRect();
    const card = cardRef.current.getBoundingClientRect();
    const gutter = 12;
    const offset = 8;
    const left = Math.max(gutter, Math.min(anchor.left, window.innerWidth - card.width - gutter));
    const below = anchor.bottom + offset;
    const above = anchor.top - card.height - offset;
    const top = below + card.height <= window.innerHeight - gutter
      ? below
      : above >= gutter
        ? above
        : Math.max(gutter, Math.min(below, window.innerHeight - card.height - gutter));
    setPosition({ left, top });
  }, []);

  useLayoutEffect(() => {
    if (!open) return;

    positionCard();
    const resizeObserver = new ResizeObserver(positionCard);
    if (triggerRef.current) resizeObserver.observe(triggerRef.current);
    if (cardRef.current) resizeObserver.observe(cardRef.current);
    window.addEventListener("resize", positionCard);
    window.addEventListener("scroll", positionCard, true);
    return () => {
      resizeObserver.disconnect();
      window.removeEventListener("resize", positionCard);
      window.removeEventListener("scroll", positionCard, true);
    };
  }, [open, positionCard]);

  useEffect(() => {
    if (!characterId) return;

    function closeOtherHover(event: Event) {
      const nextCharacterId = (event as CustomEvent<{ characterId: number }>).detail?.characterId;
      if (nextCharacterId !== characterId) setOpen(false);
    }

    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === "Escape") setOpen(false);
    }

    window.addEventListener("eqm:character-hover-open", closeOtherHover as EventListener);
    window.addEventListener("keydown", closeOnEscape);
    return () => {
      window.removeEventListener("eqm:character-hover-open", closeOtherHover as EventListener);
      window.removeEventListener("keydown", closeOnEscape);
    };
  }, [characterId]);

  async function loadSummary() {
    if (!characterId || summary || loading) return;

    setLoading(true);
    setError(null);
    try {
      setSummary(await api<CharacterSummary>(`/characters/summary/${characterId}`));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Summary unavailable");
    } finally {
      setLoading(false);
    }
  }

  function showSummary() {
    if (!characterId) return;

    window.dispatchEvent(new CustomEvent<{ characterId: number }>("eqm:character-hover-open", { detail: { characterId } }));
    setOpen(true);
    void loadSummary();
  }

  if (!characterId) return <span className={className}>{name}</span>;

  function openCharacterPage(event: { preventDefault: () => void; stopPropagation: () => void }) {
    event.preventDefault();
    event.stopPropagation();
    window.dispatchEvent(new CustomEvent<CharacterFocus>("eqm:open-character", { detail: { characterId, name, nonce: Date.now() } }));
  }

  const topCategories = summary?.skill_categories.slice(0, 5) ?? [];
  const nameControl = (
    <button ref={triggerRef} type="button" className={`character-hover-name ${className}`} onMouseEnter={showSummary} onFocus={showSummary} onClick={openCharacterPage} title="Open character dossier" aria-expanded={open}>
      {name}
    </button>
  );

  return (
    <span className="character-hover-wrap">
      {nameControl}
      {open && createPortal(
        <div
          ref={cardRef}
          className="character-hover-card"
          style={{ left: position.left, top: position.top, right: "auto", position: "fixed", zIndex: 10_000, width: "min(380px, calc(100vw - 24px))" }}
          role="dialog"
          aria-label={`${summary?.character.name ?? name} character summary`}
        >
          <button
            type="button"
            className="character-hover-close"
            aria-label="Close character summary"
            title="Close"
            onMouseDown={(event) => event.preventDefault()}
            onClick={(event) => {
              event.preventDefault();
              event.stopPropagation();
              setOpen(false);
            }}
          >
            <X size={16} />
          </button>
          <div className="entity-card-heading">
            <EveEntityIcon kind="character" id={characterId} name={name} size="md" />
            <div>
              <strong>{summary?.character.name ?? name}</strong>
              <PilotSecurityStatus securityStatus={summary?.character.security_status} />
              <span>{summary?.character.corporation_name ?? "Unknown corporation"}{summary?.character.alliance_name ? ` · ${summary.character.alliance_name}` : ""}</span>
            </div>
          </div>
          {loading && <span className="muted">Loading character summary...</span>}
          {error && <span className="muted">Summary hidden by role policy.</span>}
          {summary && (
            <>
              <div className="character-hover-metrics">
                <span><b>{numberFormatter.format(summary.total_skill_points)}</b> SP</span>
                <span><b>{summary.queue_count.toLocaleString()}</b> queued</span>
                <span><b>{summary.ship_units.toLocaleString()}</b> ships</span>
                <span><b>{summary.asset_units.toLocaleString()}</b> assets</span>
                <span><b>{summary.bpos.toLocaleString()}</b> BPO</span>
                <span><b>{summary.bpcs.toLocaleString()}</b> BPC</span>
              </div>
              {topCategories.length > 0 && (
                <div className="character-hover-categories">
                  {topCategories.map((category) => <span key={category.name}>{category.name}<b>{numberFormatter.format(category.skill_points)} SP</b></span>)}
                </div>
              )}
            </>
          )}
          <div className="character-hover-actions">
            <button type="button" onMouseDown={(event) => event.preventDefault()} onClick={openCharacterPage}>Open character</button>
            {href && <a className="character-hover-external" href={href} target="_blank" rel="noreferrer" onMouseDown={(event) => event.preventDefault()} onClick={(event) => event.stopPropagation()}>zKill</a>}
          </div>
        </div>,
        document.body,
      )}
    </span>
  );
}
