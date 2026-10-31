"""Account scan markings; corporation rules override alliance rules."""
from typing import Literal

ScanColor = Literal['red', 'orange', 'blue', 'light_blue', 'green', 'purple', 'gray']
PALETTE = {
    'red': ('EVE Red', '#ff7d86', '#a51d32'),
    'orange': ('EVE Orange', '#ffba66', '#995000'),
    'blue': ('EVE Blue', '#78aaff', '#2452aa'),
    'light_blue': ('EVE Light Blue', '#7cdef5', '#006579'),
    'green': ('EVE Green', '#86df9c', '#226c38'),
    'purple': ('EVE Purple', '#d5a0ff', '#713b9b'),
    'gray': ('EVE Gray', '#bcc8d6', '#4b5969'),
}


def pilot_color(pilot, scope='effective'):
    key = {'alliance': 'alliance_highlight_color', 'corporation': 'corporation_highlight_color'}.get(scope, 'highlight_color')
    value = pilot.get(key)
    if value in PALETTE:
        return value
    # Immutable pre-color snapshots keep their original red markings.
    marked = pilot.get('alliance_highlighted') if scope == 'alliance' else pilot.get('highlighted')
    return 'red' if marked else None


def mark_snapshot(snapshot, rules, automatic=()):
    targets = {(r.kind, r.eve_id): r.color for r in rules}
    standings = {(r["kind"], r["eve_id"]): r["color"] for r in automatic}
    for pilot in snapshot['pilots']:
        manual_alliance = targets.get(('alliance', pilot['alliance_id']))
        corporation = targets.get(('corporation', pilot['corporation_id']))
        alliance = manual_alliance or standings.get(('alliance', pilot['alliance_id']))
        effective = corporation or manual_alliance or standings.get(('corporation', pilot['corporation_id'])) or alliance
        pilot.update(alliance_highlight_color=alliance, corporation_highlight_color=corporation,
                     highlight_color=effective, alliance_highlighted=bool(alliance),
                     highlighted=bool(effective))
    snapshot['highlighted_count'] = sum(p['highlighted'] for p in snapshot['pilots'])


def pdf_color(key):
    return PALETTE.get(key, PALETTE['red'])[2]


def color_label(key):
    return PALETTE.get(key, PALETTE['red'])[0]
