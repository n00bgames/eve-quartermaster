import {useState, type FormEvent} from "react";
import {api} from "../../lib/api";
import {BrandImage} from "../appearance/AppearanceProvider";

export function PasswordRecovery({token}: {token?: string}) {
  const [busy,setBusy]=useState(false);
  const [message,setMessage]=useState("");
  const [error,setError]=useState("");
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const form=event.currentTarget; const data=new FormData(form);
    setError(""); setMessage("");
    if(token && data.get("password")!==data.get("confirm")){setError("Passwords must match.");return;}
    setBusy(true);
    try {
      const result=await api<{message:string}>(token?"/auth/password-reset":"/auth/password-recovery",{method:"POST",body:JSON.stringify(token?{token,password:data.get("password")}:{email:data.get("email")})});
      if(token) {localStorage.removeItem("eq_access_token");history.replaceState(null,"",location.pathname+location.search+"#reset-password");}
      setMessage(result.message); form.reset();
    } catch(e) {setError(e instanceof Error?e.message:"Unable to reset password");}
    finally {setBusy(false);}
  }
  return <main className="auth-shell"><section className="panel auth-panel password-recovery"><BrandImage className="auth-logo"/>
    <h2>{token?"Choose a new password":"Forgot password"}</h2>
    <p className="muted">{token?"Your recovery link can be used once. Updating your password signs out existing sessions on every device.":"Enter your account email to request a recovery link. If email delivery is unavailable, ask an EQM administrator for a reset link."}</p>
    {error&&<p className="mini-alert" role="alert">{error}</p>}{message&&<p className="notice inline" role="status">{message}</p>}
    {!(token&&message)&&<form className="recovery-form" onSubmit={submit}>{token?<><label>New password<input name="password" type="password" autoComplete="new-password" minLength={8} maxLength={1024} required/></label><label>Confirm new password<input name="confirm" type="password" autoComplete="new-password" minLength={8} maxLength={1024} required/></label></>:<label>Account email<input name="email" type="email" autoComplete="email" maxLength={320} required/></label>}
    <button type="submit" disabled={busy}>{busy?"Please wait…":token?"Update password":"Send recovery link"}</button></form>}
    <a className="auth-link" href="/">Back to sign in</a>
  </section></main>;
}

export function AdminRecovery({userId, ownAccount}: {userId:number;ownAccount:boolean}) {
  const [busy,setBusy]=useState(false),[error,setError]=useState("");
  const [result,setResult]=useState<{url:string;expires_at:string;password_reset_required:boolean}|null>(null);
  const [copied,setCopied]=useState(false);
  async function submit(event:FormEvent<HTMLFormElement>){
    event.preventDefault();const form=event.currentTarget;const data=new FormData(form);setBusy(true);setError("");setResult(null);setCopied(false);
    try{setResult(await api(`/auth/users/${userId}/recovery-link`,{method:"POST",body:JSON.stringify({current_password:data.get("current_password"),require_reset:data.get("require_reset")==="on"})}));form.reset();}
    catch(e){setError(e instanceof Error?e.message:"Unable to create link");}finally{setBusy(false);}
  }
  return <details><summary>Password recovery link</summary><p className="muted">Create a single-use link and share it privately with this user. Generating another link invalidates the previous one. No email setup is required.</p>
    <form className="recovery-form" onSubmit={submit}><label>Your administrator password<input name="current_password" type="password" autoComplete="current-password" maxLength={1024} required/></label>
    {!ownAccount&&<label className="check"><input name="require_reset" type="checkbox"/>Require reset and sign out existing sessions now</label>}
    <button disabled={busy}>{busy?"Creating…":"Generate recovery link"}</button></form>
    {error&&<p className="mini-alert" role="alert">{error}</p>}
    {result&&<div className="stacked"><p role="status">Expires {new Date(result.expires_at).toLocaleString()}.{result.password_reset_required?" Password reset is now required.":" Current login remains available until reset."}</p><label>Private recovery link<input readOnly value={result.url} onFocus={e=>e.target.select()}/></label><button type="button" onClick={()=>{void navigator.clipboard.writeText(result.url).then(()=>setCopied(true)).catch(()=>setError("Select and copy the link manually."));}}>{copied?"Copied":"Copy recovery link"}</button><button type="button" onClick={()=>setResult(null)}>Hide link</button></div>}
  </details>;
}
