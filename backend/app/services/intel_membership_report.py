"""Count history and explicit comparison baselines, separate from combat evidence."""
from datetime import timedelta
from sqlalchemy import select
from app.domain.intel import utc
from app.models.intel import IntelObservation
from app.models.intel_membership import IntelMembershipMonitor, IntelMembershipSnapshot
from app.services.intel_membership import monitor_payload, now

LIMIT = 2000


def valid_count(value):
    return type(value) is int and 0 <= value <= 2147483647


def delta(current, baseline):
    change = current["member_count"] - baseline["member_count"]
    return {"change": change, "percent": round(change / baseline["member_count"] * 100, 2) if baseline["member_count"] else None,
            "baseline_count": baseline["member_count"], "baseline_at": baseline["observed_at"],
            "observed_at": current["observed_at"], "elapsed_days": round((utc(current["observed_at"]) - utc(baseline["observed_at"])).total_seconds() / 86400, 2)}


def read(db, subject, from_at, to_at):
    if subject.kind not in {"corporation", "alliance"}:
        return None
    end = utc(to_at)
    # Leave room for 90-day baselines preceding a narrow chart window.
    since = min(utc(from_at), end - timedelta(days=94))
    fields = ("id", "observed_at", "member_count", "corporation_count", "resolved_corporations", "known_member_count")
    snapshots = db.execute(select(*(getattr(IntelMembershipSnapshot, key) for key in fields)).where(
        IntelMembershipSnapshot.subject_id == subject.id,
        IntelMembershipSnapshot.observed_at < end,
        IntelMembershipSnapshot.observed_at >= since)
        .order_by(IntelMembershipSnapshot.observed_at.desc()).limit(LIMIT + 1)).all()
    limited = len(snapshots) > LIMIT
    points = [{key: getattr(row, key) for key in fields if key != "id"}
              | {"source": "public_esi"} for row in snapshots[:LIMIT]]
    if subject.kind == "corporation":
        # Reuse real historic profile observations; never backdate today's count.
        legacy = db.scalars(select(IntelObservation).where(IntelObservation.subject_id == subject.id,
            IntelObservation.source == "esi", IntelObservation.observed_at < end,
            IntelObservation.observed_at >= since).order_by(IntelObservation.observed_at.desc()).limit(LIMIT + 1)).all()
        limited = limited or len(legacy) > LIMIT
        for row in legacy[:LIMIT]:
            count = row.payload.get("member_count")
            if valid_count(count):
                points.append({"observed_at": row.observed_at, "member_count": count, "corporation_count": None,
                    "resolved_corporations": 0, "known_member_count": count, "corporations": [], "source": "retained_public_profile"})
        profile = (subject.public_data.get("esi") or {})
        count = (profile.get("data") or {}).get("member_count")
        if valid_count(count) and profile.get("fetched_at"):
            at = utc(profile["fetched_at"])
            if since <= at < end:
                points.append({"observed_at": at, "member_count": count, "corporation_count": None,
                    "resolved_corporations": 0, "known_member_count": count, "corporations": [], "source": "retained_public_profile"})
    # One last complete observation per UTC day. A partial observation is kept
    # only when that day has no complete count, so it cannot draw a false drop.
    days = {}
    for point in sorted(points, key=lambda p: utc(p["observed_at"])):
        point["observed_at"] = utc(point["observed_at"])
        day = utc(point["observed_at"]).date().isoformat()
        previous = days.get(day)
        if previous is None or point["member_count"] is not None or previous["member_count"] is None:
            days[day] = point
    points = sorted(days.values(), key=lambda p: utc(p["observed_at"]))
    complete = [point for point in points if point["member_count"] is not None]
    latest = complete[-1] if complete else None
    latest_attempt = snapshots[0] if snapshots else None
    windows = []
    for duration in (7, 30, 90):
        cutoff = utc(latest["observed_at"]) - timedelta(days=duration) if latest else None
        candidates = [p for p in complete if cutoff - timedelta(days=2) <= utc(p["observed_at"]) <= cutoff] if cutoff else []
        baseline = candidates[-1] if candidates else None
        windows.append({"days": duration, "state": "available" if baseline else "no_baseline",
                        **(delta(latest, baseline) if baseline else {"change": None, "percent": None, "baseline_at": None})})
    previous = delta(latest, complete[-2]) if len(complete) >= 2 else None
    chart = [{key: value for key, value in point.items() if key != "corporations"}
             for point in points if utc(from_at) <= utc(point["observed_at"]) < end]
    changes = []
    # Only load bounded corporation lists for movement comparisons, not every
    # historical roster-shaped JSON document just to plot scalar pilot counts.
    org_points = list(reversed(db.scalars(select(IntelMembershipSnapshot).where(
        IntelMembershipSnapshot.id.in_([row.id for row in snapshots[:31]]))
        .order_by(IntelMembershipSnapshot.observed_at.desc())).all())) if subject.kind == "alliance" else []
    for before, after in zip(org_points, org_points[1:]):
        if subject.kind != "alliance" or utc(after.observed_at) < utc(from_at):
            continue
        old = {row["eve_id"]: row["name"] for row in before.corporations}
        new = {row["eve_id"]: row["name"] for row in after.corporations}
        if set(old) != set(new):
            changes.append({"observed_at": utc(after.observed_at), "previous_at": utc(before.observed_at),
                "added": [{"eve_id": i, "name": new[i]} for i in sorted(new.keys() - old.keys())],
                "removed": [{"eve_id": i, "name": old[i]} for i in sorted(old.keys() - new.keys())]})
    member_count = latest["member_count"] if latest else None
    direction = ("gaining" if previous["change"] > 0 else "losing" if previous["change"] < 0 else "stable") if previous else "insufficient_history"
    return {"monitor": monitor_payload(db.get(IntelMembershipMonitor, subject.id)), "member_count": member_count,
        "observed_at": utc(latest["observed_at"]) if latest else None,
        "stale": latest is not None and now() - utc(latest["observed_at"]) > timedelta(hours=36),
        "direction": direction, "previous": previous, "windows": windows, "history": chart,
        "latest_attempt": {key: (utc(value) if key == "observed_at" else value) for key in ("observed_at", "member_count", "corporation_count", "resolved_corporations", "known_member_count") for value in [getattr(latest_attempt, key)]} if latest_attempt else None,
        "corporation_count": latest_attempt.corporation_count if latest_attempt else None,
        "corporation_changes": changes[-30:], "changes_limited": subject.kind == "alliance" and len(snapshots) > 31, "history_limited": limited,
        "notice": "Public character counts, not active players or individual joins/leaves. Alliance totals sum all listed corporations only when every count is available and affiliations agree. ESI caches can delay changes. Windows compare against an observation at or up to two days before the target baseline; missing baselines stay unknown."}
