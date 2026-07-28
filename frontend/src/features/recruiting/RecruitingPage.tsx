import { ClipboardCheck, Settings2, ShieldCheck, UsersRound } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import type { RecruitingContext } from "../../types/recruiting";
import { RecruitingApplicantPage } from "./RecruitingApplicantPage";
import { RecruitingDashboardPage } from "./RecruitingDashboard";
import { RecruitingSetup } from "./RecruitingSetup";
import "./recruiting.css";

type ApiClient = <T>(path: string, options?: RequestInit) => Promise<T>;
type Props = { api: ApiClient };

export function RecruitingPage({ api }: Props) {
  const [context, setContext] = useState<RecruitingContext | null>(null);
  const [tab, setTab] = useState<"application" | "dashboard" | "setup">("dashboard");
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const result = await api<RecruitingContext>("/recruiting/context");
    setContext(result);
    if (result.role === "applicant") setTab("application");
    else if (result.is_recruitment_admin && !result.setup_complete) setTab("setup");
    else setTab((current) => current === "application" ? "dashboard" : current);
  }, [api]);

  useEffect(() => { load().catch((reason) => setError(reason instanceof Error ? reason.message : "Recruiting could not be loaded.")); }, [load]);

  if (!context) return <section className="panel"><p className="muted">Loading recruiting workspace...</p>{error && <div className="alert error">{error}</div>}</section>;
  const identity = context.public.corporation;
  return (
    <div className="recruiting-page">
      <section className="recruiting-workspace-header">
        <div className="recruiting-workspace-identity">
          {identity?.logo_url ? <img src={identity.logo_url} alt="Corporation logo" /> : <UsersRound size={34} />}
          <div><p className="eyebrow">Recruiting</p><h2>{identity?.name || "Initial Setup required"}</h2><span>{context.role === "applicant" ? "Private applicant workspace" : context.is_recruitment_admin ? "Recruitment administration" : "Recruiter workspace"}</span></div>
        </div>
        <div className="recruiting-access-summary"><ShieldCheck size={18} /><span>{context.capabilities.length ? context.capabilities.map((value) => value === "recruitment_admin" ? "Recruitment Administrator" : "Recruiter").join(" · ") : context.role === "applicant" ? "Applicant" : "Host access"}</span></div>
      </section>
      {error && <div className="alert error">{error}</div>}

      {context.role !== "applicant" && (
        <div className="recruiting-tabs">
          {context.is_recruiter && <button type="button" className={tab === "dashboard" ? "active" : ""} onClick={() => setTab("dashboard")}><ClipboardCheck size={17} /> Application review</button>}
          {context.is_recruitment_admin && <button type="button" className={tab === "setup" ? "active" : ""} onClick={() => setTab("setup")}><Settings2 size={17} /> Initial Setup & configuration</button>}
        </div>
      )}

      {tab === "application" && <RecruitingApplicantPage api={api} context={context} onRefresh={load} />}
      {tab === "dashboard" && context.is_recruiter && (context.setup_complete ? <RecruitingDashboardPage api={api} context={context} /> : <section className="panel recruiting-empty"><Settings2 size={28} /><h3>Complete Initial Setup first</h3><p className="muted">Corporation identity, public copy, and privacy settings must be configured before applicants can register.</p></section>)}
      {tab === "setup" && context.is_recruitment_admin && <RecruitingSetup api={api} onRefresh={load} />}
    </div>
  );
}
