import {
  ArrowLeft,
  Building2,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Clock3,
  ShieldCheck,
  Target,
  UserPlus,
  X,
} from "lucide-react";
import { FormEvent, useEffect, useRef, useState } from "react";

import type { RecruitingPublic } from "../../types/recruiting";
import {
  initiallyVisibleListIndexes,
  normalizedConfiguredLines,
  parsePublicDescription,
  RECRUITING_PRIVACY_SUMMARY,
} from "./recruitingPublicContent";
import "./recruiting.css";

type ApiClient = <T>(path: string, options?: RequestInit) => Promise<T>;

type Props = {
  api: ApiClient;
  onRegister: (path: string, body: Record<string, unknown>) => Promise<void>;
  onBack: () => void;
};

export function RecruitingPublicPage({ api, onRegister, onBack }: Props) {
  const [content, setContent] = useState<RecruitingPublic | null>(null);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const privacyDialog = useRef<HTMLDialogElement>(null);
  const privacyTrigger = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    api<RecruitingPublic>("/recruiting/public")
      .then(setContent)
      .catch((reason) => setError(reason instanceof Error ? reason.message : "Recruiting information could not be loaded."))
      .finally(() => setBusy(false));
  }, [api]);

  async function register(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setBusy(true);
    setError(null);
    try {
      await onRegister("/recruiting/register", {
        display_name: form.get("display_name"),
        email: form.get("email"),
        password: form.get("password"),
      });
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Applicant account could not be created.");
      setBusy(false);
    }
  }

  if (busy && !content) {
    return <main className="recruiting-public"><section className="panel"><p className="muted">Loading recruiting workspace...</p></section></main>;
  }

  if (!content?.setup_complete) {
    return (
      <main className="recruiting-public">
        <section className="panel recruiting-unavailable">
          <Building2 size={36} />
          <h1>Recruiting is not open yet</h1>
          <p className="muted">The host has not completed Recruiting Initial Setup.</p>
          <button type="button" className="secondary-button" onClick={onBack}><ArrowLeft size={17} /> Back to sign in</button>
        </section>
      </main>
    );
  }

  const corporation = content.corporation;
  const alliance = content.alliance;
  const subheading = content.public_subheading || content.public_summary;
  const showSummaryInBody = Boolean(content.public_subheading && content.public_summary);
  const descriptionSections = parsePublicDescription(content.public_body ?? "");

  function openPrivacyNotice() {
    privacyDialog.current?.showModal();
  }

  function closePrivacyNotice() {
    privacyDialog.current?.close();
  }

  return (
    <main className="recruiting-public">
      <header className="recruiting-public-header">
        <button type="button" className="icon-text-button" onClick={onBack}><ArrowLeft size={17} /> EQM sign in</button>
        <span><ShieldCheck size={17} aria-hidden="true" /> Private application workspace</span>
      </header>

      <section className="recruiting-public-identity" aria-labelledby="recruiting-public-title">
        <div className="recruiting-org-logos">
          {corporation?.logo_url && <img src={corporation.logo_url} alt={(corporation.name || "Corporation") + " logo"} />}
          {alliance?.logo_url && <img src={alliance.logo_url} alt={(alliance.name || "Alliance") + " logo"} />}
        </div>
        <div className="recruiting-public-title-copy">
          <p className="eyebrow">{corporation?.name}{corporation?.ticker ? " [" + corporation.ticker + "]" : ""}</p>
          <h1 id="recruiting-public-title">{content.public_headline || "Recruitment"}</h1>
          {subheading && <p className="recruiting-public-subheading">{subheading}</p>}
          {alliance?.name && <p className="muted recruiting-alliance-name">Alliance: {alliance.name}{alliance.ticker ? " [" + alliance.ticker + "]" : ""}</p>}
        </div>
        {content.ceo?.portrait_url && (
          <div className="recruiting-ceo">
            <img src={content.ceo.portrait_url} alt={(content.ceo.name || "Corporation CEO") + " portrait"} />
            <span>CEO</span><strong>{content.ceo.name}</strong>
          </div>
        )}
      </section>

      <section className="recruiting-public-layout">
        <div className="recruiting-public-copy">
          {(showSummaryInBody || descriptionSections.length > 0) && (
            <article className="panel recruiting-description" aria-label="About this corporation">
              {showSummaryInBody && <p className="recruiting-description-lead">{content.public_summary}</p>}
              {descriptionSections.map((section, sectionIndex) => (
                <section key={(section.heading || "introduction") + "-" + sectionIndex}>
                  {section.heading && <h2>{section.heading}</h2>}
                  {section.paragraphs.map((paragraph, paragraphIndex) => <p key={paragraphIndex}>{paragraph}</p>)}
                </section>
              ))}
            </article>
          )}
          <div className="recruiting-three-columns">
            <PublicList title="What we offer" items={content.offers ?? []} />
            <PublicList title="What we expect" items={content.expectations ?? []} />
            <PublicList title="Current priorities" items={content.priorities ?? []} />
          </div>
          <article className="panel recruiting-time-card">
            <Clock3 size={24} aria-hidden="true" />
            <div>
              <h2>Typical member activity window</h2>
              <span>{content.activity_window_start}-{content.activity_window_end} {content.primary_timezone?.name} ({content.primary_timezone?.utc_offset})</span>
            </div>
          </article>
        </div>

        <form className="panel recruiting-register" onSubmit={register}>
          <div className="recruiting-register-heading"><UserPlus size={26} aria-hidden="true" /><h2>Start an application</h2></div>
          <p className="muted">Create a private applicant account. Recruiter notes are never shown to other applicants.</p>
          {error && <div className="alert error">{error}</div>}
          <label htmlFor="recruiting-display-name">Preferred display name</label>
          <input id="recruiting-display-name" name="display_name" required maxLength={120} autoComplete="nickname" />
          <label htmlFor="recruiting-email">Email</label>
          <input id="recruiting-email" name="email" required type="email" autoComplete="email" />
          <label htmlFor="recruiting-password">Password</label>
          <input id="recruiting-password" name="password" required type="password" minLength={8} autoComplete="new-password" />
          <button type="submit" disabled={busy}><UserPlus size={17} /> {busy ? "Creating account..." : "Create applicant account"}</button>
          <div className="recruiting-privacy-summary">
            <p>{RECRUITING_PRIVACY_SUMMARY}</p>
            <button ref={privacyTrigger} type="button" className="recruiting-text-button" onClick={openPrivacyNotice}>Read full privacy notice</button>
          </div>
          <div className="recruiting-scope-note">
            <ShieldCheck size={18} aria-hidden="true" />
            <span>EVE SSO is requested later and limited to: {(content.required_scopes ?? []).join(", ")}.</span>
          </div>
        </form>
      </section>

      <dialog
        ref={privacyDialog}
        className="recruiting-privacy-dialog"
        aria-labelledby="recruiting-privacy-title"
        onClose={() => privacyTrigger.current?.focus()}
        onClick={(event) => { if (event.currentTarget === event.target) closePrivacyNotice(); }}
      >
        <div className="recruiting-privacy-dialog-content">
          <header>
            <h2 id="recruiting-privacy-title">Privacy notice</h2>
            <button type="button" className="recruiting-dialog-close" aria-label="Close privacy notice" onClick={closePrivacyNotice} autoFocus><X size={18} /></button>
          </header>
          <div className="recruiting-privacy-copy">
            {(content.privacy_notice || "No privacy notice has been configured.").split(/\n\s*\n/).map((paragraph, index) => <p key={index}>{paragraph}</p>)}
          </div>
          <footer><button type="button" className="secondary-button" onClick={closePrivacyNotice}>Close</button></footer>
        </div>
      </dialog>
    </main>
  );
}

function PublicList({ title, items }: { title: string; items: string[] }) {
  const [expanded, setExpanded] = useState(false);
  const normalizedItems = normalizedConfiguredLines(items);
  const initialIndexes = initiallyVisibleListIndexes(normalizedItems, title);
  const visibleItems = expanded ? normalizedItems : normalizedItems.filter((_, index) => initialIndexes.has(index));
  const hasHiddenItems = visibleItems.length < normalizedItems.length;
  const listId = "recruiting-" + title.toLowerCase().replace(/\s+/g, "-");
  const Icon = title === "What we expect" ? ShieldCheck : title === "Current priorities" ? Target : CheckCircle2;

  return (
    <article className="panel recruiting-public-list">
      <h2>{title}</h2>
      <div id={listId} className="recruiting-public-list-items">
        {visibleItems.length ? visibleItems.map((item, index) => (
          <p key={item + "-" + index}><Icon size={16} aria-hidden="true" /> <span>{item}</span></p>
        )) : <p className="muted">No items configured.</p>}
      </div>
      {(hasHiddenItems || expanded) && normalizedItems.length > initialIndexes.size && (
        <button
          type="button"
          className="recruiting-text-button recruiting-list-toggle"
          aria-expanded={expanded}
          aria-controls={listId}
          onClick={() => setExpanded((value) => !value)}
        >
          {expanded ? <ChevronUp size={16} aria-hidden="true" /> : <ChevronDown size={16} aria-hidden="true" />}
          {expanded ? "Show less" : "Show all"}
        </button>
      )}
    </article>
  );
}
