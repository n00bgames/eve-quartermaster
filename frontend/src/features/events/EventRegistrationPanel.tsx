import { Check, CircleHelp, Pencil, Plus, Trash2 } from "lucide-react";
import { FormEvent, useEffect, useState } from "react";

import type { EventDetail, EventRegistration, RegistrationCharacter, RegistrationOptions, ShipSearchResult } from "../../types/events";

type ApiClient = <T>(path: string, options?: RequestInit) => Promise<T>;

export function EventRegistrationPanel({
  api,
  event,
  onChanged,
}: {
  api: ApiClient;
  event: EventDetail;
  onChanged: () => Promise<void> | void;
}) {
  const [options, setOptions] = useState<RegistrationOptions | null>(null);
  const [characterId, setCharacterId] = useState("");
  const [fittingId, setFittingId] = useState("");
  const [shipSource, setShipSource] = useState("undecided");
  const [shipQuery, setShipQuery] = useState("");
  const [ships, setShips] = useState<ShipSearchResult[]>([]);
  const [shipTypeId, setShipTypeId] = useState("");
  const [freeformShip, setFreeformShip] = useState("");
  const [roleKey, setRoleKey] = useState("");
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function loadOptions(selectedCharacterId = characterId) {
    const suffix = selectedCharacterId ? `?character_id=${selectedCharacterId}` : "";
    setOptions(await api<RegistrationOptions>(`/events/${event.id}/registration-options${suffix}`));
  }

  useEffect(() => { void loadOptions(""); }, [event.id]);

  useEffect(() => {
    if (shipQuery.trim().length < 2) return setShips([]);
    const timer = window.setTimeout(async () => {
      try { setShips(await api<ShipSearchResult[]>(`/events/search/ships?q=${encodeURIComponent(shipQuery.trim())}&limit=12`)); } catch { setShips([]); }
    }, 220);
    return () => window.clearTimeout(timer);
  }, [shipQuery]);

  async function refreshParticipantData() {
    await onChanged();
    await loadOptions("");
  }

  async function setAccountRsvp(status: string) {
    setBusy(true);
    setError(null);
    try {
      await api(`/events/${event.id}/rsvp`, { method: "PUT", body: JSON.stringify({ status }) });
      await onChanged();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to update account response");
    } finally { setBusy(false); }
  }

  async function setCharacterRsvp(character: RegistrationCharacter, confirmationStatus: "confirmed" | "tentative") {
    setBusy(true);
    setError(null);
    try {
      const existing = event.my_registrations.find((registration) => registration.character_id === character.id);
      if (existing) {
        await api(`/events/${event.id}/registrations/${existing.id}`, {
          method: "PATCH",
          body: JSON.stringify({ confirmation_status: confirmationStatus }),
        });
      } else {
        await api(`/events/${event.id}/registrations`, {
          method: "POST",
          body: JSON.stringify({ character_id: character.id, confirmation_status: confirmationStatus }),
        });
      }
      await refreshParticipantData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to update character RSVP");
    } finally { setBusy(false); }
  }

  function selectCharacter(selectedCharacterId: string) {
    setCharacterId(selectedCharacterId);
    setFittingId("");
    setShipTypeId("");
    setShipQuery("");
    setFreeformShip("");
    setRoleKey("");
    setNotes("");
    if (!selectedCharacterId) {
      setShipSource("undecided");
      void loadOptions("");
      return;
    }
    const existing = event.my_registrations.find((registration) => registration.character_id === Number(selectedCharacterId));
    if (existing) {
      setFittingId(existing.saved_fitting_id ? String(existing.saved_fitting_id) : "");
      setShipSource(existing.planned_ship_source || "undecided");
      setShipTypeId(existing.ship_type_id ? String(existing.ship_type_id) : "");
      setShipQuery(existing.ship_name || "");
      setFreeformShip(existing.freeform_ship_description || "");
      setRoleKey(existing.role_key || "");
      setNotes(existing.notes || "");
    } else {
      setShipSource("undecided");
    }
    void loadOptions(selectedCharacterId);
  }

  async function saveFleetPlan(submitEvent: FormEvent) {
    submitEvent.preventDefault();
    if (!characterId) return;
    setBusy(true);
    setError(null);
    try {
      const existing = event.my_registrations.find((registration) => registration.character_id === Number(characterId));
      const details = {
        planned_ship_source: shipSource,
        saved_fitting_id: shipSource === "saved_fitting" && fittingId ? Number(fittingId) : null,
        ...(shipSource === "saved_fitting" ? {} : { ship_type_id: shipTypeId ? Number(shipTypeId) : null }),
        freeform_ship_description: freeformShip.trim() || null,
        role_key: roleKey || null,
        notes: notes.trim() || null,
      };
      if (existing) {
        await api(`/events/${event.id}/registrations/${existing.id}`, { method: "PATCH", body: JSON.stringify(details) });
      } else {
        await api(`/events/${event.id}/registrations`, {
          method: "POST",
          body: JSON.stringify({ character_id: Number(characterId), confirmation_status: "tentative", ...details }),
        });
      }
      selectCharacter("");
      await refreshParticipantData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to save character fleet plan");
    } finally { setBusy(false); }
  }

  async function removeRegistration(registration: EventRegistration) {
    if (!window.confirm(`Remove ${registration.character_name} from this event?`)) return;
    setBusy(true);
    setError(null);
    try {
      await api(`/events/${event.id}/registrations/${registration.id}`, { method: "DELETE" });
      if (characterId === String(registration.character_id)) selectCharacter("");
      await refreshParticipantData();
    } catch (err) { setError(err instanceof Error ? err.message : "Unable to remove character RSVP"); }
    finally { setBusy(false); }
  }

  const open = ["draft", "scheduled"].includes(event.lifecycle_status) && event.registration_status === "open";
  const selectedRegistration = event.my_registrations.find((registration) => registration.character_id === Number(characterId));

  return (
    <section className="event-registration-panel">
      <div className="event-pane-heading"><div><span className="eyebrow">Your pilots</span><h3>Character RSVPs</h3><p>RSVP as one or more linked characters. Each pilot is tracked separately.</p></div></div>
      {error && <div className="mini-alert">{error}</div>}

      <div className="event-character-rsvp-grid">
        {options?.characters.map((character) => {
          const registration = event.my_registrations.find((row) => row.character_id === character.id);
          const responseLabel = registration?.confirmation_status === "confirmed" ? "Going" : registration ? "Maybe" : "No response";
          return <article key={character.id} className={registration ? "has-rsvp" : ""}>
            <img src={character.portrait_url || `https://images.evetech.net/characters/${character.character_id}/portrait?size=64`} alt="" />
            <span className="event-character-rsvp-name"><strong>{character.name}</strong><small>{responseLabel}{registration?.registration_status === "waitlisted" ? " · Waitlisted" : ""}</small></span>
            <div className="event-character-rsvp-actions">
              <button disabled={busy || !open} type="button" className={registration?.confirmation_status === "confirmed" ? "active going" : ""} onClick={() => void setCharacterRsvp(character, "confirmed")}><Check size={14} /> Going</button>
              <button disabled={busy || !open} type="button" className={registration?.confirmation_status === "tentative" ? "active maybe" : ""} onClick={() => void setCharacterRsvp(character, "tentative")}><CircleHelp size={14} /> Maybe</button>
              {registration && <button disabled={busy || !open} type="button" className="event-character-rsvp-remove" aria-label={`Remove ${character.name} RSVP`} onClick={() => void removeRegistration(registration)}><Trash2 size={15} /></button>}
            </div>
          </article>;
        })}
      </div>
      {options?.characters.length === 0 && <p className="event-placard">Link and authenticate an EVE character before registering for an event.</p>}
      {!open && <p className="event-placard">Registration is {event.registration_status}. Existing character RSVPs remain visible, but participant changes are disabled.</p>}

      {open && <form className="event-registration-form" onSubmit={(submitEvent) => void saveFleetPlan(submitEvent)}>
        <h4><Pencil size={17} /> Fleet details <small>Optional ship, fitting, role, and notes for any of your pilots.</small></h4>
        <div className="event-form-grid">
          <label><span>Character</span><select required value={characterId} onChange={(changeEvent) => selectCharacter(changeEvent.target.value)}><option value="">Choose one of your characters</option>{options?.characters.map((character) => <option key={character.id} value={character.id}>{character.name}{character.already_registered ? " · RSVP saved" : ""}</option>)}</select></label>
          <label><span>Ship source</span><select value={shipSource} onChange={(changeEvent) => setShipSource(changeEvent.target.value)}><option value="undecided">Undecided</option><option value="saved_fitting">Saved fitting</option><option value="sde_hull">Ship hull</option><option value="freeform">Freeform</option><option value="doctrine">Doctrine</option></select></label>
          {shipSource === "saved_fitting" && <label><span>Saved fitting</span><select value={fittingId} onChange={(changeEvent) => { setFittingId(changeEvent.target.value); setShipTypeId(""); }}><option value="">Choose fitting</option>{options?.fittings.map((fitting) => <option key={fitting.id} value={fitting.id}>{fitting.name} · {fitting.ship_name}</option>)}</select></label>}
          {["sde_hull", "doctrine"].includes(shipSource) && <label className="event-ship-search"><span>Ship hull</span><input value={shipQuery} placeholder="Search hulls" onChange={(changeEvent) => { setShipQuery(changeEvent.target.value); setShipTypeId(""); }} />{ships.length > 0 && <div className="event-search-results">{ships.map((ship) => <button type="button" key={ship.type_id} onClick={() => { setShipTypeId(String(ship.type_id)); setShipQuery(ship.name); setShips([]); }}>{ship.name}<small>{ship.group_name}</small></button>)}</div>}</label>}
          {shipSource === "freeform" && <label><span>Ship / plan</span><input value={freeformShip} onChange={(changeEvent) => setFreeformShip(changeEvent.target.value)} /></label>}
          <label><span>Fleet role</span><select value={roleKey} onChange={(changeEvent) => setRoleKey(changeEvent.target.value)}><option value="">Unassigned</option>{options?.roles.map((role) => <option key={role} value={role}>{role.replace(/_/g, " ")}</option>)}</select></label>
          <label className="event-span-2"><span>Notes</span><input maxLength={1000} value={notes} onChange={(changeEvent) => setNotes(changeEvent.target.value)} /></label>
        </div>
        <button type="submit" disabled={busy || !characterId}>{selectedRegistration ? <Pencil size={16} /> : <Plus size={16} />} {busy ? "Saving…" : selectedRegistration ? "Update character plan" : "Add character as maybe"}</button>
      </form>}

      <div className="event-account-rsvp">
        <div><strong>Overall account response</strong><small>Optional summary only; character RSVPs above determine which pilots you are bringing.</small></div>
        <div className="event-rsvp-actions">
          {["going", "maybe", "declined"].map((status) => <button disabled={busy || !open} type="button" key={status} className={event.my_rsvp?.status === status ? "active" : ""} onClick={() => void setAccountRsvp(status)}>{event.my_rsvp?.status === status && <Check size={15} />}{status}</button>)}
        </div>
      </div>
    </section>
  );
}