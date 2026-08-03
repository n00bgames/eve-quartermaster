import { ArrowLeft, Plus, Save, Trash2 } from "lucide-react";
import { FormEvent, useEffect, useMemo, useState } from "react";

import { SystemSearchField } from "../../components/SystemSearchField";
import { formatEveTime } from "../../lib/time";
import type {
  EventDetail,
  EventDoctrineRequirement,
  EventLocation,
  EventMeta,
  EventRoleRequirement,
  LocationSearchResult,
  SystemSearchResult,
} from "../../types/events";

type ApiClient = <T>(path: string, options?: RequestInit) => Promise<T>;

function toLocalInput(value?: string | null): string {
  if (!value) return "";
  const date = new Date(value);
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60000);
  return local.toISOString().slice(0, 16);
}

function toIso(value: string): string | null {
  if (!value) return null;
  return new Date(value).toISOString();
}

function clean(value: string): string | null {
  const trimmed = value.trim();
  return trimmed || null;
}

function humanize(value: string): string {
  return value.replace(/_/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

type EditableLocation = {
  role: "formup" | "destination";
  system: SystemSearchResult | null;
  locationId: number | null;
  eveLocationId: number | null;
  locationName: string;
  notes: string;
};

function locationFromDetail(role: "formup" | "destination", detail?: EventDetail | null): EditableLocation {
  const row = detail?.locations.find((location) => location.location_role === role);
  return {
    role,
    system: row ? { system_id: row.system_id, name: row.system_name || `System ${row.system_id}`, security_status: row.security_status } : null,
    locationId: row?.location_id ?? null,
    eveLocationId: row?.eve_location_id ?? null,
    locationName: row?.location_name || row?.location_name_snapshot || "",
    notes: row?.notes || "",
  };
}

export function EventEditor({
  api,
  meta,
  detail,
  onSaved,
  onCancel,
}: {
  api: ApiClient;
  meta: EventMeta;
  detail?: EventDetail | null;
  onSaved: (event: EventDetail) => void;
  onCancel: () => void;
}) {
  const editing = Boolean(detail);
  const [title, setTitle] = useState(detail?.title ?? "");
  const [eventType, setEventType] = useState(detail?.event_type ?? "fleet");
  const [initialLifecycle, setInitialLifecycle] = useState<"draft" | "scheduled">(detail?.lifecycle_status === "scheduled" ? "scheduled" : "draft");
  const [formupAt, setFormupAt] = useState(toLocalInput(detail?.formup_at));
  const [startAt, setStartAt] = useState(toLocalInput(detail?.start_at) || toLocalInput(new Date(Date.now() + 3600000).toISOString()));
  const [endAt, setEndAt] = useState(toLocalInput(detail?.end_at));
  const [duration, setDuration] = useState(detail?.estimated_duration_minutes?.toString() ?? "");
  const [operationalArea, setOperationalArea] = useState(detail?.operational_area ?? "");
  const [routeNotes, setRouteNotes] = useState(detail?.route_notes ?? "");
  const [leadCharacterId, setLeadCharacterId] = useState(detail?.lead.character_id?.toString() ?? "");
  const [doctrineMode, setDoctrineMode] = useState(detail?.doctrine_mode ?? "none");
  const [doctrineName, setDoctrineName] = useState(detail?.doctrine.name ?? "");
  const [doctrineUrl, setDoctrineUrl] = useState(detail?.doctrine.external_url ?? "");
  const [doctrineNotes, setDoctrineNotes] = useState(detail?.doctrine_notes ?? "");
  const [voiceLabel, setVoiceLabel] = useState(detail?.discord_voice_label ?? "");
  const [voiceUrl, setVoiceUrl] = useState(detail?.discord_voice_url ?? "");
  const [relatedUrl, setRelatedUrl] = useState(detail?.related_url ?? "");
  const [instructions, setInstructions] = useState(detail?.instructions ?? "");
  const [audienceKind, setAudienceKind] = useState(detail?.audience_kind ?? "all_members");
  const [audienceCorporationId, setAudienceCorporationId] = useState(detail?.audience_corporation_id?.toString() ?? "");
  const [audienceAllianceId, setAudienceAllianceId] = useState(detail?.audience_alliance_id?.toString() ?? "");
  const [compositionVisibility, setCompositionVisibility] = useState(detail?.composition_visibility ?? "participants");
  const [participantLimit, setParticipantLimit] = useState(detail?.participant_limit?.toString() ?? "");
  const [limitBasis, setLimitBasis] = useState(detail?.limit_basis ?? "characters");
  const [formup, setFormup] = useState(() => locationFromDetail("formup", detail));
  const [destination, setDestination] = useState(() => locationFromDetail("destination", detail));
  const [formupOptions, setFormupOptions] = useState<LocationSearchResult[]>([]);
  const [destinationOptions, setDestinationOptions] = useState<LocationSearchResult[]>([]);
  const [roles, setRoles] = useState<EventRoleRequirement[]>(detail?.role_requirements ?? []);
  const [doctrineRequirements, setDoctrineRequirements] = useState<EventDoctrineRequirement[]>(detail?.doctrine_requirements ?? []);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const constants = meta.constants;
  const startEve = useMemo(() => formatEveTime(toIso(startAt)), [startAt]);

  async function loadLocationOptions(system: SystemSearchResult | null, setter: (rows: LocationSearchResult[]) => void) {
    if (!system) return setter([]);
    setter(await api<LocationSearchResult[]>(`/events/search/locations?system_id=${system.system_id}`));
  }

  useEffect(() => { void loadLocationOptions(formup.system, setFormupOptions); }, [formup.system?.system_id]);
  useEffect(() => { void loadLocationOptions(destination.system, setDestinationOptions); }, [destination.system?.system_id]);

  function serializeLocation(location: EditableLocation, sortOrder: number): EventLocation | null {
    if (!location.system) return null;
    return {
      location_role: location.role,
      sort_order: sortOrder,
      system_id: location.system.system_id,
      location_id: location.locationId,
      eve_location_id: location.eveLocationId,
      location_name_snapshot: clean(location.locationName),
      notes: clean(location.notes),
    };
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const locations = [serializeLocation(formup, 0), serializeLocation(destination, 1)].filter(Boolean);
      const body: Record<string, unknown> = {
        title,
        event_type: eventType,
        formup_at: toIso(formupAt),
        start_at: toIso(startAt),
        end_at: toIso(endAt),
        estimated_duration_minutes: duration ? Number(duration) : null,
        operational_area: clean(operationalArea),
        route_notes: clean(routeNotes),
        lead_character_id: leadCharacterId ? Number(leadCharacterId) : null,
        doctrine_mode: doctrineMode,
        doctrine_id: null,
        doctrine_manual_name: clean(doctrineName),
        doctrine_external_url: clean(doctrineUrl),
        doctrine_notes: clean(doctrineNotes),
        discord_voice_label: clean(voiceLabel),
        discord_voice_url: clean(voiceUrl),
        related_url: clean(relatedUrl),
        instructions: clean(instructions),
        audience_kind: audienceKind,
        audience_corporation_id: audienceCorporationId ? Number(audienceCorporationId) : null,
        audience_alliance_id: audienceAllianceId ? Number(audienceAllianceId) : null,
        composition_visibility: compositionVisibility,
        participant_limit: participantLimit ? Number(participantLimit) : null,
        limit_basis: limitBasis,
        locations,
        role_requirements: roles.map((role, index) => ({ ...role, id: undefined, sort_order: index })),
        doctrine_requirements: doctrineRequirements.map((requirement, index) => ({
          role_requirement_id: null,
          label: requirement.label,
          requested_quantity: requirement.requested_quantity,
          notes: requirement.notes || null,
          sort_order: index,
          options: requirement.options.map((option, optionIndex) => ({
            ship_type_id: option.ship_type_id || null,
            fitting_id: option.fitting_id || null,
            manual_name_snapshot: option.manual_name_snapshot || option.ship_name || null,
            is_primary: optionIndex === 0,
            sort_order: optionIndex,
          })),
        })),
      };
      if (editing && detail) {
        body.expected_updated_at = detail.updated_at;
      } else {
        body.lifecycle_status = initialLifecycle;
        body.registration_status = "open";
      }
      const saved = await api<EventDetail>(editing ? `/events/${detail!.id}` : "/events", {
        method: editing ? "PATCH" : "POST",
        body: JSON.stringify(body),
      });
      onSaved(saved);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to save event");
    } finally {
      setBusy(false);
    }
  }

  function updateLocation(role: "formup" | "destination", patch: Partial<EditableLocation>) {
    const setter = role === "formup" ? setFormup : setDestination;
    setter((current) => ({ ...current, ...patch }));
  }

  return (
    <section className="panel event-editor">
      <div className="event-pane-heading">
        <div><span className="eyebrow">{editing ? "Operation control" : "Fleet planning"}</span><h3>{editing ? `Edit ${detail?.title}` : "Create Event"}</h3></div>
        <button type="button" className="event-secondary-button" onClick={onCancel}><ArrowLeft size={17} /> Back</button>
      </div>
      {error && <div className="mini-alert">{error}</div>}
      <form onSubmit={(event) => void submit(event)}>
        <div className="event-form-grid event-form-primary">
          <label className="event-span-2"><span>Event title</span><input required maxLength={255} value={title} onChange={(event) => setTitle(event.target.value)} /></label>
          <label><span>Event type</span><select value={eventType} onChange={(event) => setEventType(event.target.value as EventDetail["event_type"])}>{constants.event_types.map((value) => <option key={value} value={value}>{humanize(value)}</option>)}</select></label>
          {!editing && <label><span>Initial state</span><select value={initialLifecycle} onChange={(event) => setInitialLifecycle(event.target.value as "draft" | "scheduled")}><option value="draft">Save draft</option><option value="scheduled">Publish scheduled</option></select></label>}
          <label><span>Formup time (local)</span><input type="datetime-local" value={formupAt} onChange={(event) => setFormupAt(event.target.value)} /></label>
          <label><span>Start time (local)</span><input required type="datetime-local" value={startAt} onChange={(event) => setStartAt(event.target.value)} /><small>{startEve}</small></label>
          <label><span>End time (local)</span><input type="datetime-local" value={endAt} disabled={Boolean(duration)} onChange={(event) => setEndAt(event.target.value)} /></label>
          <label><span>Estimated minutes</span><input type="number" min={1} max={43200} value={duration} disabled={Boolean(endAt)} onChange={(event) => setDuration(event.target.value)} /></label>
        </div>

        <fieldset><legend>Locations</legend><div className="event-location-grid">
          {[formup, destination].map((location) => {
            const options = location.role === "formup" ? formupOptions : destinationOptions;
            return <div key={location.role} className="event-location-editor">
              <SystemSearchField api={api} label={`${location.role === "formup" ? "Formup" : "Destination"} system`} required={location.role === "formup" && initialLifecycle === "scheduled"} value={location.system} onChange={(system) => updateLocation(location.role, { system, locationId: null, eveLocationId: null, locationName: "" })} />
              <label><span>Station / structure</span><select value={location.locationId ? `location:${location.locationId}` : location.eveLocationId ? `eve:${location.eveLocationId}` : ""} onChange={(event) => {
                const row = options.find((option) => `${option.location_id ? `location:${option.location_id}` : `eve:${option.eve_location_id}`}` === event.target.value);
                updateLocation(location.role, { locationId: row?.location_id ?? null, eveLocationId: row?.eve_location_id ?? null, locationName: row?.name ?? "" });
              }}><option value="">System only</option>{options.map((row) => <option key={`${row.source}:${row.location_id ?? row.eve_location_id}`} value={row.location_id ? `location:${row.location_id}` : `eve:${row.eve_location_id}`}>{row.name}</option>)}</select></label>
              <label><span>Location notes</span><input value={location.notes} onChange={(event) => updateLocation(location.role, { notes: event.target.value })} /></label>
            </div>;
          })}
        </div></fieldset>

        <fieldset><legend>Operation details</legend><div className="event-form-grid">
          <label><span>Operational area</span><input maxLength={500} value={operationalArea} onChange={(event) => setOperationalArea(event.target.value)} /></label>
          <label><span>Fleet lead</span><select value={leadCharacterId} onChange={(event) => setLeadCharacterId(event.target.value)}><option value="">Unassigned</option>{meta.directory.lead_characters.map((character) => <option key={character.id} value={character.id}>{character.name}{character.corporation_name ? ` · ${character.corporation_name}` : ""}</option>)}</select></label>
          <label><span>Doctrine mode</span><select value={doctrineMode} onChange={(event) => setDoctrineMode(event.target.value)}>{constants.doctrine_modes.map((value) => <option key={value} value={value}>{humanize(value)}</option>)}</select></label>
          <label><span>Doctrine name</span><input value={doctrineName} onChange={(event) => setDoctrineName(event.target.value)} /></label>
          <label className="event-span-2"><span>Doctrine URL</span><input type="url" value={doctrineUrl} onChange={(event) => setDoctrineUrl(event.target.value)} /></label>
          <label className="event-span-2"><span>Doctrine notes</span><textarea rows={3} value={doctrineNotes} onChange={(event) => setDoctrineNotes(event.target.value)} /></label>
          <label><span>Discord voice label</span><input value={voiceLabel} onChange={(event) => setVoiceLabel(event.target.value)} /></label>
          <label><span>Discord voice URL</span><input type="url" value={voiceUrl} onChange={(event) => setVoiceUrl(event.target.value)} /></label>
          <label className="event-span-2"><span>Related URL</span><input type="url" value={relatedUrl} onChange={(event) => setRelatedUrl(event.target.value)} /></label>
          <label className="event-span-2"><span>Route notes</span><textarea rows={3} value={routeNotes} onChange={(event) => setRouteNotes(event.target.value)} /></label>
          <label className="event-span-2"><span>Instructions</span><textarea rows={6} value={instructions} onChange={(event) => setInstructions(event.target.value)} /></label>
        </div></fieldset>

        <fieldset><legend>Audience and limits</legend><div className="event-form-grid">
          <label><span>Audience</span><select value={audienceKind} onChange={(event) => setAudienceKind(event.target.value)}>{constants.audience_kinds.map((value) => <option key={value} value={value}>{humanize(value)}</option>)}</select></label>
          <label><span>Composition visibility</span><select value={compositionVisibility} onChange={(event) => setCompositionVisibility(event.target.value)}>{constants.composition_visibilities.map((value) => <option key={value} value={value}>{humanize(value)}</option>)}</select></label>
          {audienceKind === "corporation" && <label><span>Corporation</span><select required value={audienceCorporationId} onChange={(event) => setAudienceCorporationId(event.target.value)}><option value="">Choose a corporation</option>{meta.directory.corporations.map((corporation) => <option key={corporation.id} value={corporation.id}>{corporation.name}{corporation.ticker ? ` [${corporation.ticker}]` : ""}</option>)}</select></label>}
          {audienceKind === "alliance" && <label><span>Alliance</span><select required value={audienceAllianceId} onChange={(event) => setAudienceAllianceId(event.target.value)}><option value="">Choose an alliance</option>{meta.directory.alliances.map((alliance) => <option key={alliance.id} value={alliance.id}>{alliance.name}{alliance.ticker ? ` [${alliance.ticker}]` : ""}</option>)}</select></label>}
          <label><span>Participant limit</span><input type="number" min={1} value={participantLimit} onChange={(event) => setParticipantLimit(event.target.value)} /></label>
          <label><span>Limit counts</span><select value={limitBasis} onChange={(event) => setLimitBasis(event.target.value as "users" | "characters")}><option value="characters">Characters</option><option value="users">Users</option></select></label>
        </div></fieldset>

        <fieldset><legend>Requested roles</legend><div className="event-requirement-editor">
          {roles.map((role, index) => <div key={index}>
            <select value={role.role_key} onChange={(event) => setRoles((rows) => rows.map((row, rowIndex) => rowIndex === index ? { ...row, role_key: event.target.value } : row))}>{constants.fleet_roles.map((value) => <option key={value}>{value.replace(/_/g, " ")}</option>)}</select>
            <input aria-label="Custom role label" placeholder="Custom label" value={role.custom_label ?? ""} onChange={(event) => setRoles((rows) => rows.map((row, rowIndex) => rowIndex === index ? { ...row, custom_label: event.target.value } : row))} />
            <input aria-label="Requested quantity" type="number" min={1} value={role.requested_quantity} onChange={(event) => setRoles((rows) => rows.map((row, rowIndex) => rowIndex === index ? { ...row, requested_quantity: Number(event.target.value) } : row))} />
            <button type="button" aria-label="Remove role" onClick={() => setRoles((rows) => rows.filter((_, rowIndex) => rowIndex !== index))}><Trash2 size={16} /></button>
          </div>)}
          <button type="button" className="event-add-row" onClick={() => setRoles((rows) => [...rows, { role_key: "mainline_dps", requested_quantity: 1, sort_order: rows.length }])}><Plus size={16} /> Add requested role</button>
        </div></fieldset>

        <fieldset><legend>Doctrine composition</legend><div className="event-requirement-editor">
          {doctrineRequirements.map((requirement, index) => <div key={index} className="event-doctrine-editor-row">
            <input required aria-label="Doctrine requirement label" placeholder="Mainline DPS" value={requirement.label} onChange={(event) => setDoctrineRequirements((rows) => rows.map((row, rowIndex) => rowIndex === index ? { ...row, label: event.target.value } : row))} />
            <input aria-label="Requested quantity" type="number" min={1} value={requirement.requested_quantity} onChange={(event) => setDoctrineRequirements((rows) => rows.map((row, rowIndex) => rowIndex === index ? { ...row, requested_quantity: Number(event.target.value) } : row))} />
            <input aria-label="Accepted hulls" placeholder="Accepted hulls, comma separated" value={requirement.options.map((option) => option.manual_name_snapshot || option.ship_name).filter(Boolean).join(", ")} onChange={(event) => setDoctrineRequirements((rows) => rows.map((row, rowIndex) => rowIndex === index ? { ...row, options: event.target.value.split(",").map((name, optionIndex) => ({ manual_name_snapshot: name.trim(), is_primary: optionIndex === 0, sort_order: optionIndex })).filter((option) => option.manual_name_snapshot) } : row))} />
            <button type="button" aria-label="Remove doctrine requirement" onClick={() => setDoctrineRequirements((rows) => rows.filter((_, rowIndex) => rowIndex !== index))}><Trash2 size={16} /></button>
          </div>)}
          <button type="button" className="event-add-row" onClick={() => setDoctrineRequirements((rows) => [...rows, { label: "", requested_quantity: 1, sort_order: rows.length, options: [] }])}><Plus size={16} /> Add doctrine requirement</button>
        </div></fieldset>

        <div className="event-form-actions"><button type="button" className="event-secondary-button" onClick={onCancel}>Cancel</button><button type="submit" disabled={busy}><Save size={17} /> {busy ? "Saving…" : editing ? "Update event" : "Create event"}</button></div>
      </form>
    </section>
  );
}
