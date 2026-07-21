import { useEffect, useRef, useState, type ReactElement, type ReactNode } from "react";

import { UsersAdmin } from "./UsersAdmin";

import { formatDateTime, preferredTimeZone, timezoneChoices } from "../../lib/time";
import type {
  EveMailCharacter,
  EveMailHeader,
  EveMailMessage,
  EveMailRecipient,
  NotificationInbox,
  PrivateMessage,
  ProfileEsiAuthInfo,
  ProfileFocus,
  ProfileUserAccount,
} from "../../types/profile";

type ApiClient = <T>(path: string, options?: RequestInit) => Promise<T>;
type ManagedFormComponent = (props: { children: ReactNode; onSubmit: (form: FormData) => Promise<void>; submitLabel?: string }) => ReactElement;

type ProfilePageProps = {
  currentUser: ProfileUserAccount;
  onUserUpdated: (user: ProfileUserAccount) => void;
  focus: ProfileFocus | null;
  api: ApiClient;
  ManagedForm: ManagedFormComponent;
  accountLabel: (user: ProfileUserAccount) => string;
};

function plainEveMailBody(value?: string | null): string {
  if (!value) return "";

  return value
    .replace(/<br\s*\/?>/gi, "\n")
    .replace(/<\/p>/gi, "\n\n")
    .replace(/<[^>]+>/g, "")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&amp;/g, "&")
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'");
}

function eveMailRecipientLabel(recipient?: EveMailRecipient | null): string {
  if (!recipient) return "Unknown";
  const name = recipient.name ?? String(recipient.recipient_id);
  return `${name} (${recipient.recipient_type.replace("_", " ")})`;
}

export function ProfilePage({ currentUser, onUserUpdated, focus, api, ManagedForm, accountLabel }: ProfilePageProps) {
  const [inbox, setInbox] = useState<NotificationInbox | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [profileError, setProfileError] = useState<string | null>(null);
  const [replyTo, setReplyTo] = useState<PrivateMessage | undefined>(undefined);
  const [mailCharacters, setMailCharacters] = useState<EveMailCharacter[]>([]);
  const [selectedMailTokenId, setSelectedMailTokenId] = useState<number | "">("");
  const [mailHeaders, setMailHeaders] = useState<EveMailHeader[]>([]);
  const [mailHasMore, setMailHasMore] = useState(false);
  const [selectedMail, setSelectedMail] = useState<EveMailMessage | null>(null);
  const [mailBusy, setMailBusy] = useState(false);
  const [mailAuthInfo, setMailAuthInfo] = useState<ProfileEsiAuthInfo | null>(null);
  const [mailNotice, setMailNotice] = useState<string | null>(null);
  const [mailError, setMailError] = useState<string | null>(null);
  const [eveMailReplyTo, setEveMailReplyTo] = useState("");
  const [eveMailSubject, setEveMailSubject] = useState("");
  const [eveMailBody, setEveMailBody] = useState("");
  const messagesRef = useRef<HTMLDivElement | null>(null);
  const recipients = (inbox?.users ?? []).filter((user) => user.id !== currentUser.id);
  const timeZone = preferredTimeZone(currentUser);
  const profileTimezones = timezoneChoices(timeZone);
  const selectedMailCharacter = mailCharacters.find((character) => character.token_id === selectedMailTokenId);

  async function loadInbox() {
    setInbox(await api<NotificationInbox>("/notifications"));
  }

  async function loadMailCharacters() {
    const rows = await api<EveMailCharacter[]>("/mail/characters");
    setMailCharacters(rows);
    setSelectedMailTokenId((current) => current || rows.find((row) => row.can_read)?.token_id || rows[0]?.token_id || "");
  }

  async function loadEveMail(tokenId: number | "" = selectedMailTokenId, append = false) {
    if (!tokenId) return;

    setMailBusy(true);
    setMailError(null);
    try {
      const lastMailId = append && mailHeaders.length > 0 ? mailHeaders[mailHeaders.length - 1].mail_id : null;
      const cursor = lastMailId ? `&last_mail_id=${lastMailId}` : "";
      const rows = await api<EveMailHeader[]>(`/mail/${tokenId}/headers?limit=50${cursor}`);

      setMailHeaders((current) => {
        if (!append) return rows;
        const seen = new Set(current.map((item) => item.mail_id));
        return [...current, ...rows.filter((row) => !seen.has(row.mail_id))];
      });
      setMailHasMore(rows.length >= 50);
      setMailNotice(append ? `Loaded ${rows.length} older EVE mail headers.` : `Loaded ${rows.length} EVE mail headers.`);
    } catch (err) {
      setMailError(err instanceof Error ? err.message : "Unable to load EVE mail");
    } finally {
      setMailBusy(false);
    }
  }

  async function openEveMail(header: EveMailHeader) {
    if (!selectedMailTokenId) return;

    setMailBusy(true);
    setMailError(null);
    try {
      const row = await api<EveMailMessage>(`/mail/${selectedMailTokenId}/messages/${header.mail_id}`);
      setSelectedMail(row);
      if (!header.is_read && selectedMailCharacter?.can_organize) {
        await api<{ status: string }>(`/mail/${selectedMailTokenId}/messages/${header.mail_id}/read`, { method: "PUT" });
        setMailHeaders((rows) => rows.map((item) => item.mail_id === header.mail_id ? { ...item, is_read: true } : item));
      }
    } catch (err) {
      setMailError(err instanceof Error ? err.message : "Unable to open EVE mail");
    } finally {
      setMailBusy(false);
    }
  }

  async function sendEveMail(form: FormData) {
    if (!selectedMailTokenId) return;

    setMailBusy(true);
    setMailError(null);
    try {
      await api<{ status: string }>(`/mail/${selectedMailTokenId}/send`, {
        method: "POST",
        body: JSON.stringify({
          recipient_names: String(form.get("recipient_names") ?? "").trim(),
          subject: String(form.get("subject") ?? "").trim(),
          body: String(form.get("body") ?? ""),
        }),
      });
      setEveMailReplyTo("");
      setEveMailSubject("");
      setEveMailBody("");
      setMailNotice("EVE mail sent.");
      await loadEveMail(selectedMailTokenId);
    } catch (err) {
      setMailError(err instanceof Error ? err.message : "Unable to send EVE mail");
    } finally {
      setMailBusy(false);
    }
  }

  async function updateAccount(form: FormData) {
    setProfileError(null);
    try {
      const payload: Record<string, unknown> = {};
      const displayName = String(form.get("display_name") ?? "").trim();
      const email = String(form.get("email") ?? "").trim();
      const password = String(form.get("password") ?? "");
      const currentPassword = String(form.get("current_password") ?? "");
      const timezone = String(form.get("timezone") ?? "").trim();

      if (displayName) payload.display_name = displayName;
      if (email && email !== currentUser.email) payload.email = email;
      if (timezone && timezone !== preferredTimeZone(currentUser)) payload.timezone = timezone;
      if (password) payload.password = password;
      if (currentPassword) payload.current_password = currentPassword;

      const updated = await api<ProfileUserAccount>("/auth/me", { method: "PATCH", body: JSON.stringify(payload) });
      onUserUpdated(updated);
      setMessage("Profile updated.");
    } catch (err) {
      setProfileError(err instanceof Error ? err.message : "Profile update failed");
    }
  }

  async function sendMessage(form: FormData) {
    setProfileError(null);
    try {
      await api<PrivateMessage>("/notifications/messages", {
        method: "POST",
        body: JSON.stringify({ recipient_user_id: form.get("recipient_user_id"), subject: form.get("subject"), body: form.get("body") }),
      });
      setReplyTo(undefined);
      setMessage("Message sent.");
      await loadInbox();
    } catch (err) {
      setProfileError(err instanceof Error ? err.message : "Message failed");
    }
  }

  async function markMessageRead(messageId: number) {
    await api<{ status: string }>("/notifications/read", { method: "POST", body: JSON.stringify({ event_ids: [], message_ids: [messageId] }) });
    await loadInbox();
  }

  async function deleteMessage(messageId: number) {
    if (!window.confirm("Delete this private message from your mailbox?")) return;

    await api<{ status: string }>(`/notifications/messages/${messageId}`, { method: "DELETE" });
    if (replyTo?.id === messageId) setReplyTo(undefined);
    setMessage("Message deleted.");
    await loadInbox();
  }

  useEffect(() => {
    void loadInbox().catch((err) => setProfileError(err instanceof Error ? err.message : "Unable to load messages"));
    void loadMailCharacters().catch((err) => setMailError(err instanceof Error ? err.message : "Unable to load EVE mail characters"));
    void api<ProfileEsiAuthInfo>("/esi/auth-url?scope_group=mail").then(setMailAuthInfo).catch(() => undefined);
  }, []);

  useEffect(() => {
    if (!selectedMailTokenId) return;
    setSelectedMail(null);
    setMailHasMore(false);
    void loadEveMail(selectedMailTokenId);
  }, [selectedMailTokenId]);

  useEffect(() => {
    if (!focus || focus.section !== "messages") return;
    setReplyTo(focus.replyTo);
    window.setTimeout(() => messagesRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }), 80);
    if (focus.replyTo && !focus.replyTo.is_read) void markMessageRead(focus.replyTo.id).catch(() => undefined);
  }, [focus?.nonce]);

  const replySubject = replyTo?.subject?.toLowerCase().startsWith("re:") ? replyTo.subject : replyTo ? `Re: ${replyTo.subject}` : "";

  return (
    <div className="profile-page">
      <section className="panel stacked">
        <h3>Profile</h3>
        {message && <div className="notice inline">{message}</div>}
        {profileError && <div className="mini-alert">{profileError}</div>}
        <ManagedForm submitLabel="Update profile" onSubmit={updateAccount}>
          <label>Display name<input name="display_name" defaultValue={currentUser.display_name} required /></label>
          <label>Email<input name="email" type="email" defaultValue={currentUser.email} required /></label>
          <label>Local timezone<select name="timezone" defaultValue={timeZone}>{profileTimezones.map((zone) => <option key={zone} value={zone}>{zone}</option>)}</select></label>
          <label>Current password<input name="current_password" type="password" placeholder="Required for email or password changes" /></label>
          <label>New password<input name="password" type="password" minLength={8} placeholder="Leave blank to keep current password" /></label>
        </ManagedForm>
      </section>
      <section className="panel stacked eve-mail-panel">
        <div className="section-heading">
          <div>
            <h3>EVE Mail</h3>
            <p>Select one of your linked characters to read or send in-game mail.</p>
          </div>
          <button type="button" disabled={!selectedMailTokenId || mailBusy} onClick={() => void loadEveMail()}>Refresh mail</button>
        </div>
        {mailNotice && <div className="notice inline">{mailNotice}</div>}
        {mailError && <div className="mini-alert">{mailError}</div>}
        <label>
          Character
          <select value={selectedMailTokenId} onChange={(event) => { setSelectedMailTokenId(event.target.value ? Number(event.target.value) : ""); setSelectedMail(null); setMailHasMore(false); }}>
            <option value="">No linked mail character</option>
            {mailCharacters.map((character) => <option key={character.token_id} value={character.token_id}>{character.character_name}{character.can_read ? "" : " (missing mail read)"}</option>)}
          </select>
        </label>
        {selectedMailCharacter?.missing_mail_scopes?.length ? <div className="mini-alert">Missing mail scopes: {selectedMailCharacter.missing_mail_scopes.join(", ")}{mailAuthInfo?.ready ? <> <a className="mini-link" href={mailAuthInfo.url}>Authorize mail scopes</a></> : null}</div> : null}
        <div className="eve-mail-grid">
          <div className="eve-mail-list">
            <h4>Mailbox</h4>
            {mailHeaders.map((header) => <button type="button" key={header.mail_id} className={header.is_read ? "eve-mail-row" : "eve-mail-row unread-card"} onClick={() => void openEveMail(header)}><strong>{header.subject || "(No subject)"}</strong><span>From {header.from_name ?? (header.from ? `Character ${header.from}` : "Unknown")}</span><span>{header.timestamp ? formatDateTime(header.timestamp, timeZone) : "recently"}</span></button>)}
            {mailHeaders.length === 0 && <p className="empty">No EVE mail loaded.</p>}
            {mailHeaders.length > 0 && mailHasMore && <button type="button" className="secondary" disabled={mailBusy} onClick={() => void loadEveMail(selectedMailTokenId, true)}>{mailBusy ? "Loading..." : "Load older mail"}</button>}
          </div>
          <div className="eve-mail-message">
            <h4>Message</h4>
            {selectedMail ? (
              <>
                <strong>{selectedMail.subject || "(No subject)"}</strong>
                <span>From {selectedMail.from_name ?? (selectedMail.from ? `Character ${selectedMail.from}` : "Unknown")}</span>
                <span>To {(selectedMail.recipients ?? []).map(eveMailRecipientLabel).join(", ") || "Unknown"}</span>
                {selectedMail.timestamp && <span>{formatDateTime(selectedMail.timestamp, timeZone)}</span>}
                <div className="eve-mail-message-body">{plainEveMailBody(selectedMail.body)}</div>
                <div className="card-actions">
                  <button type="button" disabled={!selectedMailCharacter?.can_send} onClick={() => { const sender = selectedMail.from_name || (selectedMail.from ? String(selectedMail.from) : ""); const subject = selectedMail.subject ?? ""; setEveMailReplyTo(sender); setEveMailSubject(subject.toLowerCase().startsWith("re:") ? subject : `Re: ${subject}`); setEveMailBody(""); }}>Reply</button>
                </div>
              </>
            ) : <p className="empty">Select an EVE mail message.</p>}
          </div>
          <div className="eve-mail-compose">
            <h4>Send EVE mail</h4>
            <ManagedForm submitLabel="Send EVE mail" onSubmit={sendEveMail}>
              <label>To<input name="recipient_names" required placeholder="Character, corporation, or alliance name" value={eveMailReplyTo} onChange={(event) => setEveMailReplyTo(event.target.value)} /></label>
              <label>Subject<input name="subject" required value={eveMailSubject} onChange={(event) => setEveMailSubject(event.target.value)} /></label>
              <label>Message<textarea name="body" required value={eveMailBody} onChange={(event) => setEveMailBody(event.target.value)} /></label>
            </ManagedForm>
            {selectedMailCharacter && !selectedMailCharacter.can_send && <p className="empty">This character needs esi-mail.send_mail.v1 before it can send mail.</p>}
          </div>
        </div>
      </section>
      <section className="panel stacked" ref={messagesRef}>
        <div className="section-heading"><h3>Private Messages</h3><button type="button" onClick={() => void loadInbox()}>Refresh</button></div>
        <div className="two-column">
          <div className="stacked">
            <h4>Inbox</h4>
            <div className="card-list message-list">
              {inbox?.messages.map((item) => <article key={item.id} className={item.is_read ? "" : "unread-card"}><strong>{item.subject}</strong><span>From {item.sender_display_name ?? "Unknown"} - {item.created_at ? formatDateTime(item.created_at, timeZone) : "recently"}</span><p>{item.body}</p><div className="card-actions"><button type="button" onClick={() => setReplyTo(item)}>Reply</button>{!item.is_read && <button type="button" onClick={() => void markMessageRead(item.id)}>Mark read</button>}<button className="danger" type="button" onClick={() => void deleteMessage(item.id)}>Delete</button></div></article>)}
              {inbox && inbox.messages.length === 0 && <p className="empty">No private messages.</p>}
            </div>
          </div>
          <div className="stacked">
            <h4>Sent</h4>
            <div className="card-list message-list">
              {inbox?.sent_messages?.map((item) => <article key={item.id}><strong>{item.subject}</strong><span>To {item.recipient_display_name ?? "Unknown"} - {item.created_at ? formatDateTime(item.created_at, timeZone) : "recently"}</span><p>{item.body}</p><div className="card-actions"><button className="danger" type="button" onClick={() => void deleteMessage(item.id)}>Delete</button></div></article>)}
              {inbox && (inbox.sent_messages ?? []).length === 0 && <p className="empty">No sent messages.</p>}
            </div>
          </div>
        </div>
        <h4>{replyTo ? `Reply to ${replyTo.sender_display_name ?? "Unknown"}` : "Compose"}</h4>
        <ManagedForm key={replyTo?.id ?? "compose"} submitLabel={replyTo ? "Send reply" : "Send message"} onSubmit={sendMessage}>
          <label>To<select name="recipient_user_id" required defaultValue={replyTo?.sender_user_id ?? recipients[0]?.id ?? ""}>{recipients.map((user) => <option key={user.id} value={user.id}>{accountLabel(user)} ({user.role})</option>)}</select></label>
          <label>Subject<input name="subject" required defaultValue={replySubject} /></label>
          <label>Message<textarea name="body" required /></label>
        </ManagedForm>
      </section>
      {["host", "admin"].includes(currentUser.role) && <UsersAdmin currentUser={currentUser} api={api} ManagedForm={ManagedForm} accountLabel={accountLabel} />}
    </div>
  );
}
