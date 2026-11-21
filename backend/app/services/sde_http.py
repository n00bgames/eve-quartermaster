"""Pinned CCP HTTP releases, staged and checked before any database writes.

The adapter exposes the existing importer's keyed rows without materializing
large map tables in memory. Named keys and nested PI rows follow CCP's schemas.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import re
from threading import Lock
from urllib.parse import urljoin, urlsplit

import httpx

LATEST_URL = "https://sde.evetech.net/tranquility/latest/"
ORIGIN = "https://sde.evetech.net"
RELEASE_PATTERN = r"[0-9]{8}T[0-9]{6}Z"
MAX_LINE_BYTES = 8 * 1024**2
MAX_TABLE_BYTES = 1024**3
MAX_MANIFEST_BYTES = 2 * 1024**2


@dataclass(frozen=True)
class Table:
    name: str
    key: str
    required: tuple[str, ...] = ()
    optional: bool = False


# Explicit schema keys, never JSON field order or the ZIP's _key wrapper.
TABLES = {
    "categories": Table("categories", "categoryID", ("name",)),
    "groups": Table("groups", "groupID", ("categoryID", "name")),
    "types": Table("types", "typeID", ("groupID", "name")),
    "blueprints": Table("blueprints", "blueprintTypeID", ("activities",)),
    "dogma_attributes": Table("dogmaAttributes", "attributeID", ("name",)),
    "dogma_effects": Table("dogmaEffects", "effectID", ("name",)),
    "type_dogma": Table("typeDogma", "typeID", ("dogmaAttributes", "dogmaEffects")),
    "planet_schematics": Table("planetSchematics", "schematicID", ("cycleTime", "types")),
    "regions": Table("mapRegions", "regionID", ("name",)),
    "constellations": Table("mapConstellations", "constellationID", ("regionID", "name")),
    "systems": Table("mapSolarSystems", "solarSystemID", ("constellationID", "regionID", "name", "position")),
    "stargates": Table("mapStargates", "stargateID", ("solarSystemID", "destination", "position")),
    "stations": Table("npcStations", "stationID", ("solarSystemID", "typeID", "operationID", "ownerID", "position")),
    "station_operations": Table("stationOperations", "operationID", ("operationName",)),
    "npc_corporations": Table("npcCorporations", "corporationID", ("name",)),
    "npc_characters": Table("npcCharacters", "characterID", ("name", "corporationID"), optional=True),
    "stars": Table("mapStars", "starID", ("solarSystemID", "typeID", "radius"), optional=True),
    "planets": Table("mapPlanets", "planetID", ("solarSystemID", "typeID", "radius", "position"), optional=True),
    "moons": Table("mapMoons", "moonID", ("solarSystemID", "typeID", "position"), optional=True),
    "belts": Table("mapAsteroidBelts", "asteroidBeltID", ("solarSystemID", "typeID", "position"), optional=True),
}


class SdeHttpError(ValueError):
    """Safe operator-facing error; URLs are fixed public CCP resources."""


def _integer(value):
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _json_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise SdeHttpError(f"Duplicate JSON field: {key}")
        result[key] = value
    return result


def parse_json(data):
    return json.loads(data, object_pairs_hook=_json_object,
                      parse_constant=lambda value: (_ for _ in ()).throw(SdeHttpError("Non-finite JSON number")))


def normalize_row(table, row):
    if not isinstance(row, dict) or not _integer(row.get(table.key)):
        raise SdeHttpError(f"{table.name}: missing or invalid {table.key}")
    if any(field not in row for field in table.required):
        raise SdeHttpError(f"{table.name}: missing importer-required fields")
    for field, value in row.items():
        if field.endswith("ID") and value is not None and not _integer(value):
            raise SdeHttpError(f"{table.name}: invalid {field}")
        if field in {"name", "operationName"} and not isinstance(value, (str, dict)):
            raise SdeHttpError(f"{table.name}: invalid {field}")
        if field in {"mass", "volume", "capacity", "radius", "securityStatus", "cycleTime"} and not _number(value):
            raise SdeHttpError(f"{table.name}: invalid {field}")
    if "position" in row:
        pos = row["position"]
        if not isinstance(pos, dict) or any(not _number(pos.get(axis)) for axis in ("x", "y", "z")):
            raise SdeHttpError(f"{table.name}: invalid position")
    if table.name == "mapStargates":
        dest = row["destination"]
        if not isinstance(dest, dict) or any(not _integer(dest.get(k)) for k in ("solarSystemID", "stargateID")):
            raise SdeHttpError("mapStargates: invalid destination")
    if table.name == "typeDogma":
        for field, key in (("dogmaAttributes", "attributeID"), ("dogmaEffects", "effectID")):
            entries = row[field]
            if not isinstance(entries, list) or any(not isinstance(r, dict) or not _integer(r.get(key)) for r in entries):
                raise SdeHttpError(f"typeDogma: invalid {field}")
            if field == "dogmaAttributes" and any(not _number(r.get("value")) for r in entries):
                raise SdeHttpError("typeDogma: invalid attribute value")
    if table.name == "dogmaEffects" and "modifierInfo" in row:
        if not isinstance(row["modifierInfo"], list) or any(not isinstance(r, dict) for r in row["modifierInfo"]):
            raise SdeHttpError("dogmaEffects: invalid modifiers")
    if table.name == "blueprints":
        activities = row["activities"]
        if not isinstance(activities, dict):
            raise SdeHttpError("blueprints: invalid activities")
        for activity in activities.values():
            if not isinstance(activity, dict) or ("time" in activity and not _integer(activity["time"])):
                raise SdeHttpError("blueprints: invalid activity")
            for field in ("materials", "products"):
                entries = activity.get(field, [])
                if not isinstance(entries, list) or any(not isinstance(r, dict) or not _integer(r.get("typeID")) or not _integer(r.get("quantity")) for r in entries):
                    raise SdeHttpError(f"blueprints: invalid {field}")
    if table.name == "npcCharacters" and "agent" in row:
        agent = row["agent"]
        if not isinstance(agent, dict) or ("level" in agent and not _integer(agent["level"])):
            raise SdeHttpError("npcCharacters: invalid agent")
    result = dict(row)
    if table.name == "planetSchematics":
        entries = row["types"]
        if not isinstance(entries, list):
            raise SdeHttpError("planetSchematics: expected named type rows")
        keyed = {}
        for item in entries:
            if not isinstance(item, dict) or not _integer(item.get("typeID")) or not _integer(item.get("quantity")) or not isinstance(item.get("isInput"), bool):
                raise SdeHttpError("planetSchematics: invalid input/output row")
            key = item["typeID"]
            if key in keyed:
                raise SdeHttpError("planetSchematics: duplicate typeID")
            keyed[key] = {k: v for k, v in item.items() if k != "typeID"}
        if not any(not item["isInput"] for item in keyed.values()):
            raise SdeHttpError("planetSchematics: missing output")
        result["types"] = keyed
    # Preserve localized named celestial exceptions in the existing importer.
    if "uniqueName" in row and isinstance(row["uniqueName"], dict):
        result["name"] = row["uniqueName"]
    result.pop(table.key)
    return row[table.key], result


class JsonlRows:
    def __init__(self, path, table):
        self.path, self.table = Path(path), table

    def items(self):
        seen = set()
        with self.path.open("rb") as source:
            while line := source.readline(MAX_LINE_BYTES + 1):
                if len(line) > MAX_LINE_BYTES:
                    raise SdeHttpError(f"{self.table.name}: JSONL record exceeds limit")
                if not line.strip():
                    continue
                try:
                    key, payload = normalize_row(self.table, parse_json(line))
                except (ValueError, TypeError, KeyError) as exc:
                    raise SdeHttpError(f"{self.table.name}: malformed record ({str(exc)[:160]})") from exc
                if key in seen:
                    raise SdeHttpError(f"{self.table.name}: duplicate {self.table.key}")
                seen.add(key)
                yield key, payload

    def values(self):
        return (row for _, row in self.items())


class JsonlSource:
    def __init__(self, path):
        self.path, self.source_path = Path(path), str(path)

    def close(self):
        pass

    def load_yaml(self, logical):
        table = TABLES.get(logical)
        if table is None or not (path := self.path / (table.name + ".jsonl")).is_file():
            raise FileNotFoundError(f"HTTP SDE has no {logical} table")
        rows = JsonlRows(path, table)
        # Agent lookup uses .get(); this small table is safe to materialize.
        return dict(rows.items()) if logical == "npc_corporations" else rows


def _trusted_url(url):
    parsed = urlsplit(str(url))
    if parsed.scheme != "https" or parsed.netloc != "sde.evetech.net" or parsed.query or parsed.fragment:
        raise SdeHttpError("Rejected SDE URL: expected the fixed CCP HTTPS origin")
    return parsed.path


@contextmanager
def _response(client, url, allowed):
    """Check each redirect before issuing it (including CCP's content blobs)."""
    for _ in range(4):
        if not allowed(_trusted_url(url)):
            raise SdeHttpError("Rejected SDE redirect or release path")
        with client.stream("GET", url, follow_redirects=False) as response:
            if response.status_code in {301, 302, 303, 307, 308}:
                url = urljoin(str(response.url), response.headers.get("Location", ""))
                continue
            if response.status_code in {404, 410}:
                raise SdeHttpError("Pinned SDE release is unavailable or expired. Retry as a new job to select a fresh release.")
            response.raise_for_status()
            yield response
            return
    raise SdeHttpError("Too many SDE redirects")


def fetch_release(path, max_bytes, report, receipt, client=None):
    """Fetch one manifest and at most two tables at once; all validation precedes import."""
    if client is None:
        with httpx.Client(timeout=httpx.Timeout(60, connect=15), follow_redirects=False,
                          headers={"User-Agent": "EVE-Quartermaster/2.4.2 SDE Maintenance"},
                          limits=httpx.Limits(max_connections=2)) as owned:
            return fetch_release(path, max_bytes, report, receipt, owned)
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    report("fetching HTTP release manifest", bytes_received=0)
    with _response(client, LATEST_URL, lambda p: p == "/tranquility/latest/" or bool(re.fullmatch(r"/tranquility/" + RELEASE_PATTERN + "/", p))) as response:
        raw = bytearray()
        for chunk in response.iter_bytes(65536):
            raw.extend(chunk)
            if len(raw) > MAX_MANIFEST_BYTES:
                raise SdeHttpError("SDE manifest exceeds size limit")
        manifest = parse_json(raw)
        final_path = _trusted_url(response.url)
    if not isinstance(manifest, dict):
        raise SdeHttpError("Invalid SDE manifest")
    release, build = manifest.get("release"), manifest.get("buildNumber")
    if not isinstance(release, str) or not re.fullmatch(RELEASE_PATTERN, release) or not _integer(build) or build > 999999999999:
        raise SdeHttpError("Invalid SDE release or build number")
    base = f"/tranquility/{release}/"
    if final_path not in {"/tranquility/latest/", base}:
        raise SdeHttpError("SDE manifest release disagrees with its redirect")
    tables = manifest.get("tables")
    if not isinstance(tables, dict):
        raise SdeHttpError("Invalid SDE table manifest")
    selected = []
    missing = []
    for spec in TABLES.values():
        info = tables.get(spec.name)
        if info is None and spec.optional:
            missing.append(spec.name)
            continue
        if not isinstance(info, dict) or not isinstance(info.get("jsonl"), dict):
            raise SdeHttpError(f"Missing required SDE table: {spec.name}")
        url, version = info["jsonl"].get("url", ""), info.get("version", "")
        if _trusted_url(url) != base + spec.name + ".jsonl" or not isinstance(version, str) or not re.fullmatch(r"[a-f0-9]{64}", version):
            raise SdeHttpError(f"Invalid pinned table URL/version: {spec.name}")
        selected.append((spec, url, version))
    details = {"source": "ccp_http", "release": release, "build": str(build),
               "released_at": manifest.get("releaseDate"), "source_url": ORIGIN + base,
               "missing_optional_tables": missing, "tables": {}, "bytes": 0}
    receipt(details)
    report("fetching HTTP tables", bytes_received=0, tables_total=len(selected), tables_completed=0)
    lock, received = Lock(), 0

    def fetch_table(entry):
        nonlocal received
        spec, url, version = entry
        blob = f"/blobs/{version}.jsonl"
        size, digest = 0, hashlib.sha256()
        with _response(client, url, lambda p: p in {base + spec.name + ".jsonl", blob}) as response:
            with (path / (spec.name + ".jsonl")).open("xb") as output:
                # httpx decodes Content-Encoding once. Content-Length is wire size.
                for chunk in response.iter_bytes(65536):
                    size += len(chunk)
                    with lock:
                        received += len(chunk)
                        if received > max_bytes:
                            raise SdeHttpError("HTTP SDE exceeds configured decoded size limit")
                    if size > MAX_TABLE_BYTES:
                        raise SdeHttpError(f"{spec.name}: table exceeds decoded size limit")
                    output.write(chunk)
                    digest.update(chunk)
        rows = sum(1 for _ in JsonlRows(path / (spec.name + ".jsonl"), spec).items())
        if not rows and not spec.optional:
            raise SdeHttpError(f"{spec.name}: required table is empty")
        return spec.name, {"version": version, "bytes": size, "rows": rows, "sha256": digest.hexdigest()}

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = {pool.submit(fetch_table, entry): entry[0].name for entry in selected}
        try:
            for future in as_completed(futures):
                name, data = future.result()
                details["tables"][name] = data
                details["bytes"] += data["bytes"]
                receipt(details)
                report(f"validated {name}", bytes_received=details["bytes"],
                       tables_completed=len(details["tables"]), tables_total=len(selected))
        except Exception as exc:
            failed_table = futures[future]
            report(f"fetching/validating {failed_table} failed")
            for future in futures:
                future.cancel()
            if isinstance(exc, httpx.HTTPError):
                raise SdeHttpError(f"{failed_table}: HTTP transfer failed. Retry a full HTTP import with a fresh release.") from exc
            raise
    report("HTTP tables validated; starting import", bytes_received=details["bytes"])
    return details
