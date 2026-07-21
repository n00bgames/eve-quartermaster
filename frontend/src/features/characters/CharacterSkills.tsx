import { GraduationCap, Plus, ScrollText } from "lucide-react";
import type { ReactElement, ReactNode } from "react";
import { useEffect, useRef, useState } from "react";

import { PilotSecurityStatus } from "./PilotSecurityStatus";
import type { CharacterSkillProfile, SkillRecord, SkillSyncAllJob } from "../../types/skills";

type ApiClient = <T>(path: string, options?: RequestInit) => Promise<T>;
type MetricComponent = (props: { icon: ReactNode; label: string; value: string | number; delta?: string }) => ReactElement;

type CharacterSkillsProps = {
  currentUser: { id: number; role: string };
  api: ApiClient;
  Metric: MetricComponent;
  CharacterHoverName: (props: { characterId?: number | null; name: string; className?: string; href?: string }) => ReactElement;
};

export function CharacterSkills({ currentUser, api, Metric, CharacterHoverName }: CharacterSkillsProps) {
  const [profiles, setProfiles] = useState<CharacterSkillProfile[]>([]);
  const [expandedProfileIds, setExpandedProfileIds] = useState<Set<number>>(new Set());
  const [skillError, setSkillError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [busyTokenId, setBusyTokenId] = useState<number | null>(null);
  const [syncAllJob, setSyncAllJob] = useState<SkillSyncAllJob | null>(null);
  const syncAllPollingRef = useRef(false);
  const baseSkillSp = [0, 250, 1415, 8000, 45255, 256000];
  const syncAllActive = syncAllJob?.status === "queued" || syncAllJob?.status === "running";
  const syncAllPercent = syncAllJob?.total_count ? Math.round((syncAllJob.processed_count / syncAllJob.total_count) * 100) : 0;
  const wait = (ms: number) => new Promise((resolve) => window.setTimeout(resolve, ms));

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
      let job = await api<SkillSyncAllJob>("/esi/sync/character-skills/all", { method: "POST", body: "{}" });
      setSyncAllJob(job);
      const startedAt = Date.now();
      while (job.status === "queued" || job.status === "running") {
        if (Date.now() - startedAt > 10 * 60 * 1000) {
          setMessage(null);
          setSkillError("Skill sync is still running after 10 minutes, so polling was stopped to quiet the logs. Refresh Skills to check the latest status, or restart the backend worker if the count is not moving.");
          setSyncAllJob((current) => current ? { ...current, status: "failed", errors: ["Polling stopped after 10 minutes while the backend job was still running.", ...current.errors] } : current);
          return;
        }
        await wait(2000);
        job = await api<SkillSyncAllJob>(`/esi/sync/character-skills/all/${job.job_id}`);
        setSyncAllJob(job);
      }
      await loadSkills();
      if (job.status === "complete") {
        setMessage(`Synced ${job.success_count.toLocaleString()} of ${job.total_count.toLocaleString()} eligible characters. Skipped ${job.skipped_count.toLocaleString()} opted-out, duplicate, hidden, or missing-scope character${job.skipped_count === 1 ? "" : "s"}.`);
      } else {
        setMessage(null);
        setSkillError(job.errors[0] ?? "One or more character skill syncs failed.");
      }
    } catch (err) {
      setMessage(null);
      setSkillError(err instanceof Error ? err.message : "Sync all skills failed");
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
    const groups = new Map<string, SkillRecord[]>();
    for (const skill of profile.skills) {
      const key = skill.skill_group_name || skill.skill_category_name || "Uncategorized";
      groups.set(key, [...(groups.get(key) ?? []), skill]);
    }
    return [...groups.entries()].sort(([left], [right]) => left.localeCompare(right, undefined, { numeric: true, sensitivity: "base" }));
  }

  function categorySkillPoints(skills: SkillRecord[]) {
    return skills.reduce((total, skill) => total + skill.skillpoints_in_skill, 0);
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

  return <section className="panel stacked"><div className="section-heading"><h3>Character Skills</h3><div className="button-row compact"><button type="button" onClick={() => setExpandedProfileIds(new Set(profiles.map((profile) => profile.token_id)))}>Expand all</button><button type="button" onClick={() => setExpandedProfileIds(new Set())}>Collapse all</button><button type="button" disabled={syncAllActive || busyTokenId !== null || profiles.length === 0} onClick={() => void syncAllSkills()}>{syncAllActive ? "Syncing all" : "Sync all eligible"}</button><button type="button" disabled={syncAllActive} onClick={() => void loadSkills()}>Refresh</button></div></div>{syncAllJob && <div className={`queue-badge queue-${syncAllJob.status}`}><strong>{syncAllJob.processed_count.toLocaleString()} / {syncAllJob.total_count.toLocaleString()}</strong><span>{syncAllJob.status === "complete" ? "Skill sync complete" : syncAllJob.status === "failed" ? "Skill sync needs review" : syncAllJob.current_character_name ? `Syncing ${syncAllJob.current_character_name}` : "Skill sync queued"} · {syncAllJob.success_count.toLocaleString()} synced · {syncAllJob.failed_count.toLocaleString()} failed · {syncAllJob.skipped_count.toLocaleString()} skipped</span><i style={{ width: `${syncAllPercent}%` }} /></div>}{message && <div className="notice inline">{message}</div>}{skillError && <div className="mini-alert">{skillError}</div>}<div className="card-list skill-profiles">{profiles.map((profile) => { const expanded = expandedProfileIds.has(profile.token_id); return <article key={profile.token_id} className="skill-profile-card"><div className="section-heading compact skill-profile-heading"><button type="button" className="skill-profile-toggle" onClick={() => toggleProfile(profile.token_id)} aria-expanded={expanded}>{expanded ? "Collapse" : "Expand"}</button><div><strong><CharacterHoverName characterId={profile.character_id} name={profile.character_name} /><PilotSecurityStatus securityStatus={profile.security_status} compact /></strong><span>Character ID {profile.character_id}</span></div><div className="button-row compact">{profile.can_sync && <button type="button" disabled={syncAllActive || profile.missing_skill_scopes.length > 0 || busyTokenId === profile.token_id} onClick={() => void syncSkills(profile)}>{busyTokenId === profile.token_id ? "Syncing" : profile.sync_opt_out && profile.owner_user_id !== currentUser.id && ["host", "admin"].includes(currentUser.role) ? "Admin override sync" : "Sync skills"}</button>}</div></div>{profile.sync_opt_out && <div className="privacy-placard">This character does not wish to be synced.{profile.admin_override_visible ? " Admin view is active for administrative review." : " This data stays private to the character owner unless an admin opens an override view."}</div>}{profile.can_sync && profile.missing_skill_scopes.length > 0 && <span className="scope-warn">Missing skill scopes: {profile.missing_skill_scopes.join(", ")}. Re-link through ESI Sync.</span>}<div className="status-grid compact"><Metric icon={<GraduationCap size={18} />} label="Total SP" value={profile.total_skill_points ?? 0} /><Metric icon={<Plus size={18} />} label="Unallocated SP" value={profile.unallocated_skill_points ?? 0} /><Metric icon={<ScrollText size={18} />} label="Skills" value={profile.skill_count} /></div><span>Skills synced {profile.skills_synced_at ? new Date(profile.skills_synced_at).toLocaleString() : "never"} · Queue synced {profile.skill_queue_synced_at ? new Date(profile.skill_queue_synced_at).toLocaleString() : "never"}</span>{expanded && <div className="two-column skill-columns"><section><h4>Trained Skills</h4><div className="skill-group-list">{groupedSkills(profile).map(([groupName, skills]) => <details key={groupName} className="skill-group" open><summary>{groupName}<span>{skills.length.toLocaleString()} skills · {categorySkillPoints(skills).toLocaleString()} SP</span></summary><div className="mini-list">{skills.map((skill) => { const progress = skillProgress(skill); return <div key={skill.id} className="skill-row"><strong>{skill.skill_name}</strong><span>Level {skill.trained_skill_level} · Active {skill.active_skill_level}</span><div className="skill-progress-line"><span>{skill.skillpoints_in_skill.toLocaleString()} / {progress.targetSp.toLocaleString()} SP</span><span>{Math.round(progress.percent)}%</span></div><div className="skill-progress-bar" title="Progress target is estimated until SDE dogma skill ranks are imported."><i style={{ width: `${progress.percent}%` }} /></div></div>; })}</div></details>)}{profile.skills.length === 0 && <p className="empty">No trained skills imported yet.</p>}</div></section><section><h4>Current Queue</h4><div className="mini-list">{profile.queue.map((entry) => <div key={entry.id}><strong>{entry.queue_position + 1}. {entry.skill_name}</strong><span>To level {entry.finished_level}{entry.finish_date ? ` · finishes ${new Date(entry.finish_date).toLocaleString()}` : ""}</span></div>)}{profile.queue.length === 0 && <p className="empty">No active queue imported.</p>}</div></section></div>}</article>; })}{profiles.length === 0 && <p className="empty">No linked characters visible. Link a character through ESI Sync first.</p>}</div></section>;
}