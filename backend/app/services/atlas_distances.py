"""Rust graph traversal, with a deterministic Python fallback for local installs."""
from collections import defaultdict, deque
import json
import logging
import shutil
import subprocess
from app.core.config import get_settings


def python_distances(origin, edges):
    graph = defaultdict(list)
    for start, end in edges:
        graph[start].append(end)
    distances = {origin: 0}
    queue = deque([origin])
    while queue:
        current = queue.popleft()
        for neighbor in graph[current]:
            if neighbor not in distances:
                distances[neighbor] = distances[current] + 1
                queue.append(neighbor)
    return distances


def gate_distances(origin, edges):
    settings = get_settings()
    if shutil.which(settings.eqm_core_binary):
        try:
            result = subprocess.run([settings.eqm_core_binary, "atlas-distances", "--input", "-"],
                input=json.dumps(dict(origin=origin, edges=edges)), capture_output=True, text=True,
                check=True, timeout=settings.eqm_core_timeout_seconds)
            payload = json.loads(result.stdout)
            if payload.get("schema_version") != "eqm.atlas-distances.v1":
                raise ValueError("Unexpected atlas output schema")
            distances = {int(k): int(v) for k, v in payload["distances"].items()}
            if distances.get(origin) != 0 or any(v < 0 for v in distances.values()):
                raise ValueError("Invalid atlas distances")
            return distances
        except (OSError, subprocess.SubprocessError, ValueError, KeyError, TypeError):
            logging.getLogger(__name__).warning("Rust atlas traversal unavailable; using Python fallback")
    return python_distances(origin, edges)
