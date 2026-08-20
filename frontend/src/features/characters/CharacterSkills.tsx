import { Copy, Download, GraduationCap, MoreHorizontal, Plus, Search, ScrollText, X } from "lucide-react";
import type { ReactElement, ReactNode } from "react";
import { useEffect, useMemo, useRef, useState } from "react";

import { isCharacterSyncPollingAborted, resumeCharacterSyncJob, trackCharacterSyncJob } from "../../lib/characterSyncPolling";

import { PilotSecurityStatus } from "./PilotSecurityStatus";
import { SkillDogmaPopover } from "./SkillDogmaPopover";
import { SkillPlansPanel } from "./SkillPlansPanel";
import {
  characterSkillReport,
  characterSkillReportFilename,
  groupSkillsByCategory,
  skillCategoryPoints,
} from "./skillReport";
import type { CharacterSkillProfile, SkillRecord, SkillSyncAllJob } from "../../types/skills";
import "./characterSkills.css";

type ApiClient = <T>(path: string, options?: RequestInit) => Promise<T>;
type MetricComponent = (props: { icon: ReactNode; label: string; value: string | number; delta?: string }) => ReactElement;

type CharacterSkillsProps = {
  currentUser: { id: number; role: string };
  api: ApiClient;
  Metric: MetricComponent;
  CharacterHoverName: (props: { characterId?: number | null; name: string; className?: string; href?: string }) => ReactElement;
  selectedPlanId?: number | null;
};

function CharacterSkillProfiles({ currentUser, api, Metric, CharacterHoverName }: CharacterSkillsProps) {
  const [profiles, setProfiles] = useState<CharacterSkillProfile[]>([]);
  const [expandedProfileIds, setExpandedProfileIds] = useState<Set<number>>(new Set());
  const [skillError, setSkillError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [busyTokenId, setBusyTokenId] = useState<number | null>(null);
  const [syncAllJob, setSyncAllJob] = useState<SkillSyncAllJob | null>(null);
  const [skillQuery, setSkillQuery] = useState("");
  const [minimumSkillLevel, setMinimumSkillLevel] = useState(1);
  const [skillMatchMode, setSkillMatchMode] = useState<"all" | "any">("all");
  const syncAllPollingRef = useRef(false);
  const syncPollAbortRef = useRef<AbortController | null>(null);
  const syncResumeScope = `skills-all:${currentUser.id}`;
  const baseSkillSp = [0, 250, 1415, 8000, 45255, 256000];
  const syncAllActive = syncAllJob?.status === "queued" || syncAllJob?.status === "running";
  const syncAllPercent = syncAllJob?.total_count ? Math.round((syncAllJob.processed_count / syncAllJob.total_count) * 100) : 0;
  const skillTerms = useMemo(
    () => skillQuery.split(/[,;\n]+/).map((term) => term.trim().toLocaleLowerCase()).filter(Boolean),
    [skillQuery],
  );
  const skillMatchesByToken = useMemo(() => {
    const matches = new Map<number, SkillRecord[]>();
    if (skillTerms.length === 0) return matches;
    for (const profile of profiles) {
      const eligibleSkills = profile.skills.filter((skill) => skill.trained_skill_level >= minimumSkillLevel);
      const profileMatches = skillMatchMode === "all"
        ? skillTerms.every((term) => eligibleSkills.some((skill) => skill.skill_name.toLocaleLowerCase().includes(term)))
        : skillTerms.some((term) => eligibleSkills.some((skill) => skill.skill_name.toLocaleLowerCase().includes(term)));
      if (!profileMatches) continue;
      matches.set(
        profile.token_id,
        eligibleSkills
          .filter((skill) => skillTerms.some((term) => skill.skill_name.toLocaleLowerCase().includes(term)))
          .sort((left, right) => left.skill_name.localeCompare(right.skill_name)),
      );
    }
    return matches;
  }, [minimumSkillLevel, profiles, skillMatchMode, skillTerms]);
  const filteredProfiles = skillTerms.length === 0
    ? profiles
    : profiles.filter((profile) => skillMatchesByToken.has(profile.token_id));

  async function loadSkills() {
    setProfiles(await api<CharacterSkillProfile[]>("/esi/character-skills"));
  }

  async function syncSkills(profile: CharacterSkillProfile) {
    if (!profile.can_sync || syncAllActive) return;
    if (profile.sync_opt_out && profile.owner_user_id !== currentUser.id && ["host", "admin"].includes(currentUser.role) && !window.confirm(`${profile.character_name} has opted out of normal sync. Temporarily override as admin?`)) return;
    setBusyTokenId(profile.token_id);
    setSkillError(null);
    setMessage(`Syncing skills for ${profile.character_name}...`);
    try {
      const result = await api<{ character_name: string; skill_count: number; queue_count: number; total_skill_points: number }>(`/esi/sync/character-skills/${profile.token_id}`, { method: "POST", body: "{}" });
      setMessage(`Synced ${result.skill_count.toLocaleString()} skills and ${result.queue_count.toLocaleString()} queued skills for ${result.character_name}.`);
      await loadSkills();
    } catch (err) {
      setMessage(null);
      setSkillError(err instanceof Error ? err.message : "Skill sync failed");
    } finally {
      setBusyTokenId(null);
    }
  }

  async function syncAllSkills() {
    if (syncAllPollingRef.current) return;
    syncAllPollingRef.current = true;
    setSkillError(null);
    setMessage("Queued skill sync for every eligible character...");
    try {
      const initialJob = await api<SkillSyncAllJob>("/esi/sync/character-skills/all", { method: "POST", body: "{}" });
      setSyncAllJob(initialJob);
      const job = await trackCharacterSyncJob({
        scope: syncResumeScope,
        initialJob,
        fetchLatest: (current) => api<SkillSyncAllJob>(`/esi/sync/character-skills/all/${current.job_id}`),
        onUpdate: setSyncAllJob,
        signal: syncPollAbortRef.current?.signal,
      });
      await loadSkills();
      if (job.status === "complete") {
        setMessage(`Synced ${job.success_count.toLocaleString()} of ${job.total_count.toLocaleString()} eligible characters. Skipped ${job.skipped_count.toLocaleString()} opted-out, duplicate, hidden, or missing-scope character${job.skipped_count === 1 ? "" : "s"}.`);
      } else {
        setMessage(null);
        setSkillError(job.errors[0] ?? "One or more character skill syncs failed.");
      }
    } catch (err) {
      if (!isCharacterSyncPollingAborted(err)) {
        setMessage(null);
        setSkillError(err instanceof Error ? err.message : "Sync all skills failed");
      }
    } finally {
      syncAllPollingRef.current = false;
    }
  }

  function toggleProfile(tokenId: number) {
    setExpandedProfileIds((current) => {
      const next = new Set(current);
      if (next.has(tokenId)) next.delete(tokenId);
      else next.add(tokenId);
      return next;
    });
  }

  function groupedSkills(profile: CharacterSkillProfile) {
    return groupSkillsByCategory(profile.skills);
  }

  function categorySkillPoints(skills: SkillRecord[]) {
    return skillCategoryPoints(skills);
  }

  async function copySkillReport(profile: CharacterSkillProfile) {
    try {
      await navigator.clipboard.writeText(characterSkillReport(profile));
      setSkillError(null);
      setMessage(`Copied ${profile.character_name}'s categorized skill report.`);
    } catch (err) {
      setMessage(null);
      setSkillError(err instanceof Error ? err.message : "Unable to copy the skill report");
    }
  }

  function downloadSkillReport(profile: CharacterSkillProfile) {
    const url = URL.createObjectURL(new Blob([characterSkillReport(profile)], { type: "text/plain;charset=utf-8" }));
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = characterSkillReportFilename(profile);
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
    setSkillError(null);
    setMessage(`Downloaded ${profile.character_name}'s categorized skill report.`);
  }

  function skillProgress(skill: SkillRecord) {
    const currentSp = skill.skillpoints_in_skill;
    const currentLevel = Math.max(0, Math.min(5, skill.trained_skill_level || skill.active_skill_level || 0));
    const nextLevel = Math.min(5, currentLevel + (currentLevel < 5 ? 1 : 0));
    const baseForCurrent = baseSkillSp[currentLevel] || 250;
    const rankEstimate = currentLevel > 0 ? Math.max(1, Math.min(16, Math.floor(currentSp / baseForCurrent) || 1)) : 1;
    const targetSp = Math.max(baseSkillSp[nextLevel] * rankEstimate, currentSp || baseSkillSp[1]);
    return { targetSp, percent: Math.max(0, Math.min(100, (currentSp / targetSp) * 100)) };
  }

  useEffect(() => { void loadSkills().catch((err) => setSkillError(err instanceof Error ? err.message : "Unable to load character skills")); }, []);

  useEffect(() => {
    const controller = new AbortController();
    syncPollAbortRef.current = controller;
    syncAllPollingRef.current = true;
    void resumeCharacterSyncJob<SkillSyncAllJob>({
      scope: syncResumeScope,
      fetchById: (jobId) => api<SkillSyncAllJob>(`/esi/sync/character-skills/all/${jobId}`),
      onUpdate: (job) => { setSyncAllJob(job); setMessage("Resumed skill sync progress from the server..."); },
      signal: controller.signal,
    }).then(async (job) => {
      if (!job) return;
      await loadSkills();
      if (job.status === "complete") setMessage(`Synced ${job.success_count.toLocaleString()} of ${job.total_count.toLocaleString()} eligible characters.`);
      else setSkillError(job.errors[0] ?? "One or more character skill syncs failed.");
    }).catch((err) => {
      if (!isCharacterSyncPollingAborted(err)) setSkillError(err instanceof Error ? err.message : "Unable to resume skill sync");
    }).finally(() => { syncAllPollingRef.current = false; });
    return () => controller.abort();
  }, [currentUser.id]);

  return <section className="panel stacked skills-page"><div className="section-heading skills-page-heading"><h3>Character Skills</h3><div className="button-row compact skills-page-actions"><button type="button" onClick={() => setExpandedProfileIds(new Set(filteredProfiles.map((profile) => profile.token_id)))}>Expand all</button><button type="button" onClick={() => setExpandedProfileIds(new Set())}>Collapse all</button><button type="button" disabled={syncAllActive || busyTokenId !== null || profiles.length === 0} onClick={() => void syncAllSkills()}>{syncAllActive ? "Syncing all" : "Sync all eligible"}</button><button type="button" disabled={syncAllActive} onClick={() => void loadSkills()}>Refresh</button></div></div><div className="skill-search-panel" role="search" aria-label="Find pilots by trained skill"><label className="skill-search-query"><span>Skill names</span><input type="search" value={skillQuery} onChange={(event) => setSkillQuery(event.target.value)} placeholder="e.g. Logistics Cruisers, Capacitor Emission Systems" /></label><label><span>Minimum trained level</span><select value={minimumSkillLevel} onChange={(event) => setMinimumSkillLevel(Number(event.target.value))}>{[1, 2, 3, 4, 5].map((level) => <option key={level} value={level}>Level {level}+</option>)}</select></label><label><span>Match</span><select value={skillMatchMode} onChange={(event) => setSkillMatchMode(event.target.value as "all" | "any")}><option value="all">All named skills</option><option value="any">Any named skill</option></select></label><button type="button" disabled={skillQuery.trim().length === 0} onClick={() => setSkillQuery("")}><X size={16} /> Clear</button><p className="skill-search-summary"><Search size={17} />{skillTerms.length === 0 ? <span>Enter one skill, or separate several with commas. Only synced skills visible to your account are searched.</span> : <span><strong>{filteredProfiles.length.toLocaleString()}</strong> of {profiles.length.toLocaleString()} visible pilots match at Level {minimumSkillLevel}+.</span>}</p></div>{syncAllJob && <div className={`queue-badge queue-${syncAllJob.status}`}><strong>{syncAllJob.processed_count.toLocaleString()} / {syncAllJob.total_count.toLocaleString()}</strong><span>{syncAllJob.status === "complete" ? "Skill sync complete" : syncAllJob.status === "failed" ? "Skill sync needs review" : syncAllJob.current_character_name ? `Syncing ${syncAllJob.current_character_name}` : "Skill sync queued"} · {syncAllJob.success_count.toLocaleString()} synced · {syncAllJob.failed_count.toLocaleString()} failed · {syncAllJob.skipped_count.toLocaleString()} skipped</span><i style={{ width: `${syncAllPercent}%` }} /></div>}{message && <div className="notice inline">{message}</div>}{skillError && <div className="mini-alert">{skillError}</div>}<div className="card-list skill-profiles">{filteredProfiles.map((profile) => { const expanded = expandedProfileIds.has(profile.token_id); const matches = skillMatchesByToken.get(profile.token_id) ?? []; return <article key={profile.token_id} className="skill-profile-card"><div className="section-heading compact skill-profile-heading"><div className="skill-profile-identity"><strong><CharacterHoverName characterId={profile.character_id} name={profile.character_name} /><PilotSecurityStatus securityStatus={profile.security_status} compact /></strong><span>Character ID {profile.character_id}</span></div><div className="button-row compact skill-profile-actions"><button type="button" className="skill-profile-toggle" onClick={() => toggleProfile(profile.token_id)} aria-expanded={expanded}>{expanded ? "Collapse" : "Expand"}</button><button type="button" className="skill-report-action" disabled={profile.skills.length === 0} onClick={() => void copySkillReport(profile)} title="Copy a categorized skill report for sharing"><Copy size={16} /> Copy report</button><button type="button" className="skill-report-action" disabled={profile.skills.length === 0} onClick={() => downloadSkillReport(profile)} title="Download a categorized plain-text skill report"><Download size={16} /> Download report</button>{profile.can_sync && <button type="button" className="skill-sync-action" disabled={syncAllActive || profile.missing_skill_scopes.length > 0 || busyTokenId === profile.token_id} onClick={() => void syncSkills(profile)}>{busyTokenId === profile.token_id ? "Syncing" : profile.sync_opt_out && profile.owner_user_id !== currentUser.id && ["host", "admin"].includes(currentUser.role) ? "Admin override sync" : "Sync skills"}</button>}<details className="skill-profile-overflow"><summary aria-label={`More report actions for ${profile.character_name}`} title="More report actions"><MoreHorizontal size={18} /><span>Reports</span></summary><div className="skill-profile-overflow-menu"><button type="button" disabled={profile.skills.length === 0} onClick={(event) => { event.currentTarget.closest("details")?.removeAttribute("open"); void copySkillReport(profile); }}><Copy size={16} /> Copy report</button><button type="button" disabled={profile.skills.length === 0} onClick={(event) => { event.currentTarget.closest("details")?.removeAttribute("open"); downloadSkillReport(profile); }}><Download size={16} /> Download report</button></div></details></div></div>{skillTerms.length > 0 && <div className="skill-search-matches"><strong>Matched skills</strong>{matches.slice(0, 8).map((skill) => <span key={skill.id} className="skill-search-match">{skill.skill_name} · Level {skill.trained_skill_level}</span>)}{matches.length > 8 && <span className="skill-search-more">+{(matches.length - 8).toLocaleString()} more</span>}</div>}{profile.sync_opt_out && <div className="privacy-placard">This character does not wish to be synced.{profile.admin_override_visible ? " Admin view is active for administrative review." : " This data stays private to the character owner unless an admin opens an override view."}</div>}{profile.can_sync && profile.missing_skill_scopes.length > 0 && <span className="scope-warn">Missing skill scopes: {profile.missing_skill_scopes.join(", ")}. Re-link through ESI Sync.</span>}<div className="status-grid compact skill-profile-stats"><Metric icon={<GraduationCap size={18} />} label="Total SP" value={profile.total_skill_points ?? 0} /><Metric icon={<Plus size={18} />} label="Unallocated SP" value={profile.unallocated_skill_points ?? 0} /><Metric icon={<ScrollText size={18} />} label="Skills" value={profile.skill_count} /></div><div className="skill-profile-timestamps"><span>Skills synced {profile.skills_synced_at ? new Date(profile.skills_synced_at).toLocaleString() : "never"}</span><span>Queue synced {profile.skill_queue_synced_at ? new Date(profile.skill_queue_synced_at).toLocaleString() : "never"}</span></div>{expanded && <div className="two-column skill-columns"><section><h4>Trained Skills</h4><div className="skill-group-list">{groupedSkills(profile).map(([groupName, skills]) => <details key={groupName} className="skill-group" open><summary>{groupName}<span>{skills.length.toLocaleString()} skills · {categorySkillPoints(skills).toLocaleString()} SP</span></summary><div className="mini-list">{skills.map((skill) => { const progress = skillProgress(skill); return <div key={skill.id} className="skill-row"><SkillDogmaPopover api={api} skillTypeId={skill.skill_type_id} skillName={skill.skill_name} trainedLevel={skill.trained_skill_level} /><span>Level {skill.trained_skill_level} · Active {skill.active_skill_level}</span><div className="skill-progress-line"><span>{skill.skillpoints_in_skill.toLocaleString()} / {progress.targetSp.toLocaleString()} SP</span><span>{Math.round(progress.percent)}%</span></div><div className="skill-progress-bar" title="Progress target is estimated until SDE dogma skill ranks are imported."><i style={{ width: `${progress.percent}%` }} /></div></div>; })}</div></details>)}{profile.skills.length === 0 && <p className="empty">No trained skills imported yet.</p>}</div></section><section><h4>Current Queue</h4><div className="mini-list">{profile.queue.map((entry) => <div key={entry.id}><strong>{entry.queue_position + 1}. {entry.skill_name}</strong><span>To level {entry.finished_level}{entry.finish_date ? ` · finishes ${new Date(entry.finish_date).toLocaleString()}` : ""}</span></div>)}{profile.queue.length === 0 && <p className="empty">No active queue imported.</p>}</div></section></div>}</article>; })}{profiles.length === 0 && <p className="empty">No linked characters visible. Link a character through ESI Sync first.</p>}{profiles.length > 0 && filteredProfiles.length === 0 && <p className="empty">No visible pilots match the selected skill requirements.</p>}</div></section>;
}

export function CharacterSkills(props: CharacterSkillsProps) {
  const [section, setSection] = useState<"characters" | "plans">(props.selectedPlanId ? "plans" : "characters");
  useEffect(()=>{if(props.selectedPlanId)setSection("plans");},[props.selectedPlanId]);
  return <div className="skills-module"><div className="owner-kind-chips skills-module-tabs" role="tablist" aria-label="Skills sections"><button type="button" role="tab" aria-selected={section === "characters"} className={section === "characters" ? "active" : ""} onClick={() => setSection("characters")}>Character Skills</button><button type="button" role="tab" aria-selected={section === "plans"} className={section === "plans" ? "active" : ""} onClick={() => setSection("plans")}>Skill Plans</button></div>{section === "characters" ? <CharacterSkillProfiles {...props} /> : <SkillPlansPanel api={props.api} selectedPlanId={props.selectedPlanId} />}</div>;
}
