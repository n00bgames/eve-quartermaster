"""Descriptive position counts, kept separate from offer finances and outcomes."""
from collections import defaultdict


def node_position_summary(offers):
    groups = {}
    tracked = 0
    excluded = defaultdict(int)
    for offer in offers:
        layout = offer.node_map
        if layout is None:
            if offer.status == "completed":
                excluded["missing_map"] += 1
            continue
        tracked += 1
        winner = layout.get("winning_position")
        if offer.status != "completed":
            excluded["not_completed"] += 1
            continue
        if winner is None:
            excluded["missing_winner"] += 1
            continue
        total = offer.total_nodes
        columns = layout["columns"]
        seeded = set(layout["seeded_positions"])
        # Defensive guard for legacy/imported data; API writes validate these.
        if not 1 <= winner <= total or any(not 1 <= pos <= total for pos in seeded):
            excluded["invalid_positions"] += 1
            continue
        key = (total, columns)
        if key not in groups:
            groups[key] = {
                "total_nodes": total, "columns": columns, "draws": 0,
                "complete_seed_maps": 0, "seeded_wins": 0, "expected_seeded_wins": 0.0,
                "incomplete_seed_maps": 0, "outcome_conflicts": 0,
                "positions": [{"position": pos, "wins": 0, "seeded": 0, "seeded_wins": 0} for pos in range(1, total + 1)],
            }
        group = groups[key]
        group["draws"] += 1
        group["positions"][winner - 1]["wins"] += 1
        if len(seeded) != offer.seller_owned_nodes:
            group["incomplete_seed_maps"] += 1
            continue
        seeded_winner = winner in seeded
        if offer.winner not in {"seller", "external"} or seeded_winner != (offer.winner == "seller"):
            group["outcome_conflicts"] += 1
            continue
        group["complete_seed_maps"] += 1
        group["seeded_wins"] += int(seeded_winner)
        group["expected_seeded_wins"] += len(seeded) / total
        for pos in seeded:
            group["positions"][pos - 1]["seeded"] += 1
            group["positions"][pos - 1]["seeded_wins"] += int(pos == winner)
    result = [groups[key] for key in sorted(groups)]
    for group in result:
        group["expected_seeded_wins"] = round(group["expected_seeded_wins"], 4)
    return {"tracked_offers": tracked, "excluded": dict(excluded), "groups": result}
