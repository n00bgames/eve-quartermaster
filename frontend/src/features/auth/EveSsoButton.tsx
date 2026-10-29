import {useState} from "react";
import {api} from "../../lib/api";

export function EveSsoButton({inviteToken, rememberMe = false}: {inviteToken?: string; rememberMe?: boolean}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  async function begin() {
    setBusy(true); setError(null);
    try {
      const result = await api<{url: string}>("/auth/sso/start", {
        method: "POST", body: JSON.stringify({invite_token: inviteToken, remember_me: rememberMe}),
      });
      const target = new URL(result.url);
      if (target.origin !== "https://login.eveonline.com") throw new Error("EVE sign-in returned an unexpected destination.");
      window.location.assign(target.href);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to start EVE sign-in.");
      setBusy(false);
    }
  }
  return <div className="auth-sso">
    <button className="auth-sso-button" type="button" disabled={busy} onClick={() => void begin()}>
      {busy ? "Opening EVE SSO…" : inviteToken ? "Create account with EVE SSO" : "Log in with EVE SSO"}
    </button>
    <small>{inviteToken ? "Link your character and accept your assigned roles. No EQM password required." : "Use a character already linked to your EQM account."} Identity only; no assets or skills requested.</small>
    {error && <div className="mini-alert" role="alert">{error}</div>}
  </div>;
}
