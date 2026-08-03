import { Info, X } from "lucide-react";
import { useCallback, useEffect, useId, useLayoutEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";

import type { SkillDogmaBonus, SkillDogmaDetails } from "../../types/skills";
import { loadSkillDogma } from "./skillDogmaCache";
import { bonusValueText, groupBonusProfiles } from "./skillDogmaPresentation";
import "./skillDogmaPopover.css";

type ApiClient = <T>(path: string, options?: RequestInit) => Promise<T>;

type SkillDogmaPopoverProps = {
  api: ApiClient;
  skillTypeId: number;
  skillName: string;
  trainedLevel: number;
};

type Position = { left: number; top: number; width: number };
type GroupedProfile = { names: string[]; groupName: string | null; bonuses: SkillDogmaBonus[] };

const PERCENT_UNITS = new Set([105, 109, 111, 121]);

function roman(level: number) {
  return ["0", "I", "II", "III", "IV", "V"][level] ?? String(level);
}

function numberText(value: number) {
  return Number.isInteger(value) ? value.toLocaleString() : value.toLocaleString(undefined, { maximumFractionDigits: 2 });
}

function BonusRows({ bonuses, trainedLevel }: { bonuses: SkillDogmaBonus[]; trainedLevel: number }) {
  return <ul className="skill-dogma-bonuses">{bonuses.map((bonus, index) => <li key={`${bonus.text}-${index}`}>
    <span><strong>{bonusValueText(bonus)}</strong> {bonus.text}</span>
    <small>At level {roman(trainedLevel)}: <strong>{bonusValueText(bonus, trainedLevel)}</strong> {bonus.text}</small>
  </li>)}</ul>;
}

export function SkillDogmaPopover({ api, skillTypeId, skillName, trainedLevel }: SkillDogmaPopoverProps) {
  const generatedId = useId();
  const popoverId = `skill-dogma-${generatedId.replace(/:/g, "")}`;
  const triggerRef = useRef<HTMLButtonElement>(null);
  const cardRef = useRef<HTMLDivElement>(null);
  const openTimerRef = useRef<number | null>(null);
  const closeTimerRef = useRef<number | null>(null);
  const pointerRef = useRef({ x: 0, y: 0, moved: false, type: "" });
  const lastScrollRef = useRef(0);
  const [open, setOpen] = useState(false);
  const [position, setPosition] = useState<Position | null>(null);
  const [data, setData] = useState<SkillDogmaDetails | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const groupedProfiles = useMemo(() => groupBonusProfiles(data?.bonus_profiles ?? []), [data]);

  const clearTimers = useCallback(() => {
    if (openTimerRef.current !== null) window.clearTimeout(openTimerRef.current);
    if (closeTimerRef.current !== null) window.clearTimeout(closeTimerRef.current);
    openTimerRef.current = null;
    closeTimerRef.current = null;
  }, []);

  const requestOpen = useCallback(() => {
    if (Date.now() - lastScrollRef.current < 160) return;
    clearTimers();
    setOpen(true);
  }, [clearTimers]);

  const scheduleOpen = useCallback(() => {
    clearTimers();
    openTimerRef.current = window.setTimeout(requestOpen, 180);
  }, [clearTimers, requestOpen]);

  const scheduleClose = useCallback(() => {
    if (closeTimerRef.current !== null) window.clearTimeout(closeTimerRef.current);
    closeTimerRef.current = window.setTimeout(() => {
      const active = document.activeElement;
      if (active && (triggerRef.current?.contains(active) || cardRef.current?.contains(active))) return;
      setOpen(false);
    }, 220);
  }, []);

  useEffect(() => {
    const onScroll = () => { lastScrollRef.current = Date.now(); };
    window.addEventListener("scroll", onScroll, true);
    return () => window.removeEventListener("scroll", onScroll, true);
  }, []);

  useEffect(() => {
    if (!open || data || loading) return;
    setLoading(true);
    setError(null);
    void loadSkillDogma(api, skillTypeId)
      .then(setData)
      .catch((reason) => setError(reason instanceof Error ? reason.message : "Dogma details could not be loaded."))
      .finally(() => setLoading(false));
  }, [api, data, loading, open, skillTypeId]);

  useLayoutEffect(() => {
    if (!open) {
      setPosition(null);
      return;
    }
    let frame = 0;
    const update = () => {
      const trigger = triggerRef.current;
      const card = cardRef.current;
      if (!trigger || !card) return;
      const padding = 10;
      const gap = 8;
      const width = Math.min(480, window.innerWidth - padding * 2);
      card.style.width = `${width}px`;
      const triggerRect = trigger.getBoundingClientRect();
      const height = card.getBoundingClientRect().height;
      const left = Math.max(padding, Math.min(triggerRect.left, window.innerWidth - width - padding));
      const spaceBelow = window.innerHeight - triggerRect.bottom - gap - padding;
      const top = spaceBelow >= Math.min(height, 280)
        ? triggerRect.bottom + gap
        : Math.max(padding, triggerRect.top - height - gap);
      setPosition({ left, top, width });
    };
    frame = window.requestAnimationFrame(update);
    const observer = new ResizeObserver(update);
    if (cardRef.current) observer.observe(cardRef.current);
    window.addEventListener("resize", update);
    window.addEventListener("scroll", update, true);
    return () => {
      window.cancelAnimationFrame(frame);
      observer.disconnect();
      window.removeEventListener("resize", update);
      window.removeEventListener("scroll", update, true);
    };
  }, [data, error, loading, open]);

  useEffect(() => {
    if (!open) return;
    const onPointerDown = (event: PointerEvent) => {
      if (!triggerRef.current?.contains(event.target as Node) && !cardRef.current?.contains(event.target as Node)) setOpen(false);
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setOpen(false);
        triggerRef.current?.focus();
      }
    };
    document.addEventListener("pointerdown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  useEffect(() => () => clearTimers(), [clearTimers]);

  const card = open ? <div
    ref={cardRef}
    id={popoverId}
    role="dialog"
    aria-label={`${skillName} dogma details`}
    className="skill-dogma-popover"
    style={{ left: position?.left ?? -10000, top: position?.top ?? -10000, width: position?.width ?? 480, visibility: position ? "visible" : "hidden" }}
    onPointerEnter={clearTimers}
    onPointerLeave={(event) => { if (event.pointerType === "mouse") scheduleClose(); }}
  >
    <header><div><span className="eyebrow">Skill dogma</span><h4>{skillName} {roman(trainedLevel)}</h4></div><button type="button" className="skill-dogma-close" aria-label="Close skill details" onClick={() => setOpen(false)}><X size={18} /></button></header>
    {loading && <div className="skill-dogma-loading" role="status"><i /> Loading dogma details…</div>}
    {error && <div className="mini-alert" role="alert">{error}</div>}
    {data && <div className="skill-dogma-content">
      <p>{data.description || "No skill description is available in the imported SDE."}</p>
      <dl className="skill-dogma-meta">
        <div><dt>Trained</dt><dd>Level {roman(trainedLevel)}</dd></div>
        <div><dt>Rank</dt><dd>{data.rank == null ? "Unknown" : `${numberText(data.rank)}×`}</dd></div>
        <div><dt>Attributes</dt><dd>{[data.primary_attribute, data.secondary_attribute].filter(Boolean).join(" / ") || "Unknown"}</dd></div>
        <div><dt>Type ID</dt><dd>{data.type_id}</dd></div>
      </dl>
      <section><h5>Prerequisites</h5>{data.prerequisites.length ? <ul className="skill-dogma-prerequisites">{data.prerequisites.map((prerequisite) => <li key={prerequisite.type_id}>{prerequisite.name} {roman(prerequisite.level)}</li>)}</ul> : <p className="skill-dogma-empty">No prerequisite skills.</p>}</section>
      {data.direct_bonuses.length > 0 && <section><h5>Per-level bonuses</h5><BonusRows bonuses={data.direct_bonuses} trainedLevel={trainedLevel} /></section>}
      {groupedProfiles.length > 0 && <section><h5>Bonuses by affected type</h5><div className="skill-dogma-profiles">{groupedProfiles.map((profile, index) => <details key={`${profile.names[0]}-${index}`} open={groupedProfiles.length <= 4 || index === 0}><summary><span>{profile.names.slice(0, 4).join(", ")}{profile.names.length > 4 ? ` +${profile.names.length - 4} more` : ""}</span><small>{profile.groupName ?? "Affected item"}</small></summary><BonusRows bonuses={profile.bonuses} trainedLevel={trainedLevel} /></details>)}</div></section>}
      {data.affected_categories.length > 0 && <section><h5>Affected categories</h5><div className="skill-dogma-chips">{data.affected_categories.map((category) => <span key={category}>{category}</span>)}</div></section>}
      {data.direct_bonuses.length === 0 && groupedProfiles.length === 0 && <p className="skill-dogma-empty">The imported SDE does not publish a separate numeric bonus for this skill.</p>}
      <footer>EVE type {data.type_id} · Dogma effects {data.dogma_effect_ids.join(", ") || "none"}</footer>
    </div>}
  </div> : null;

  return <>
    <button
      ref={triggerRef}
      type="button"
      className="skill-dogma-trigger"
      aria-haspopup="dialog"
      aria-expanded={open}
      aria-controls={popoverId}
      aria-label={`${skillName}, trained level ${trainedLevel}. Show dogma details.`}
      onPointerEnter={(event) => { pointerRef.current.type = event.pointerType; if (event.pointerType === "mouse") scheduleOpen(); }}
      onPointerLeave={(event) => { if (event.pointerType === "mouse") scheduleClose(); }}
      onPointerDown={(event) => { pointerRef.current = { x: event.clientX, y: event.clientY, moved: false, type: event.pointerType }; }}
      onPointerMove={(event) => { if (Math.hypot(event.clientX - pointerRef.current.x, event.clientY - pointerRef.current.y) > 8) pointerRef.current.moved = true; }}
      onFocus={(event) => { if (event.currentTarget.matches(":focus-visible") || pointerRef.current.type !== "touch") requestOpen(); }}
      onBlur={scheduleClose}
      onClick={(event) => {
        if (pointerRef.current.moved || Date.now() - lastScrollRef.current < 160) { event.preventDefault(); return; }
        if (pointerRef.current.type === "touch") setOpen((current) => !current);
        else requestOpen();
      }}
    ><span>{skillName}</span><Info size={14} aria-hidden="true" /></button>
    {card && createPortal(card, document.body)}
  </>;
}
