"""Original editorial scenarios, not observed fits or prevalence statistics.

Keep facts in SDE and tactics in this independently reviewable catalog. Sources
support the mechanics; counter plans are conditional EQM editorial judgments.
"""
REVIEWED = '2026-11-01'
SOURCES = {
    'sde': {'title': 'CCP Static Data', 'url': 'https://developers.eveonline.com/static-data'},
    'turrets': {'title': 'EVE University: turret mechanics', 'url': 'https://wiki.eveuniversity.org/Turret_mechanics'},
    'missiles': {'title': 'EVE University: missile mechanics', 'url': 'https://wiki.eveuniversity.org/Missile_mechanics'},
    'recognition': {'title': 'EVE University: turret recognition', 'url': 'https://wiki.eveuniversity.org/Turret_Recognition'},
}
for name in ('Deimos','Vagabond','Arazu','Curse','Huginn','Caracal','Orthrus'):
    SOURCES[name.lower()] = {'title': f'EVE University: {name}', 'url': f'https://wiki.eveuniversity.org/{name}'}

# Examples are tools to consider with the stated support, not a winner ranking.
COUNTERS = {
 'range': {'name':'Deny the close approach', 'examples':['Vagabond','Orthrus'], 'condition':'Needs a speed/range advantage, room to move and answers to hostile tackle.',
   'small_gang':'Keep an exit and remove tackle before committing. Do not assume your orbit command keeps you outside a heated scram.',
   'fleet':'Use screens and range control to keep the damage wing outside the brawler envelope.'},
 'web': {'name':'Long-web control', 'examples':['Huginn','Rapier'], 'condition':'Support tool: must survive and have friendly damage/tackle in reach; hull alone does not confirm webs.',
   'small_gang':'Catch the kiter with supported webs rather than feeding individual interceptors.',
   'fleet':'Assign web targets and tackle handoffs; immobilizing a target only helps if your fleet can apply.'},
 'cap': {'name':'Capacitor pressure', 'examples':['Curse','Armageddon'], 'condition':'Needs fitted neutralizers in reach; injections, nosferatu and cap-free weapons can change the outcome.',
   'small_gang':'Pressure cap-dependent repair/propulsion while managing your own cap and drones.',
   'fleet':'Coordinate neutralizers on selected repair/tackle ships; avoid spreading pressure without purpose.'},
 'damp': {'name':'Disrupt enemy projection', 'examples':['Arazu','Celestis'], 'condition':'Requires enough scripted damps to cross the relevant lock-range or lock-time threshold.',
   'small_gang':'Use a range advantage with damp support; a damp does not switch off weapons already able to lock you.',
   'fleet':'Separate hostile support from effective lock range; coordinate scripts and targets.'},
 'projection': {'name':'Apply damage without chasing', 'examples':['Eagle','Cerberus'], 'condition':'Needs a fit that actually reaches and applies at the chosen range, with tackle/support to hold targets.',
   'small_gang':'Force the support ship off with projection instead of burning every pilot into its control envelope.',
   'fleet':'Use coordinated projection and target calls; check logistics and enemy range before committing.'},
 'reload': {'name':'Exploit a confirmed reload', 'examples':['Deimos','Vexor'], 'condition':'Only after confirming rapid-launcher downtime and obtaining range control; neither hull is an automatic counter.',
   'small_gang':'Preserve tackle through the clip, then commit supported damage during the reload window.',
   'fleet':'Call observed reloads; synchronize pressure without assuming the whole enemy wing is reloading.'},
}

def variant(key,name,weapons,range_note,tank,damage,tags,confirm,counters,small_gang,fleet):
    return dict(key=key,name=name,weapons=weapons,range_note=range_note,tank=tank,damage=damage,tags=tags,
                confirm=confirm,counters=counters,small_gang=small_gang,fleet=fleet)

HULLS = {
 'deimos': [
  variant('blaster','Blaster / active armor',['blasters'],
    'Close brawl; no fixed km estimate without guns, ammo, skills and fit. Null can extend its reach.',
    'Active armor is one plausible fit.', 'Kinetic / thermal from hybrid ammo; drones can add other damage.',
    ['brawl','active tank'], ['Short hybrid mounts','Approach into tackle','Armor repair cycles'], ['range','cap'],
    'Avoid trading inside its preferred brawl if you cannot break repairs or control range.',
    'Screen its approach; focus damage or capacitor pressure instead of feeding tackle piecemeal.'),
  variant('rail','Rail / projection',['rails'],
    'Longer reach than the blaster variant; ammo and application determine the useful envelope.',
    'Armor arrangements vary.', 'Hybrid damage remains kinetic / thermal, plus possible drones.',
    ['projection'], ['Long hybrid mounts','Damage maintained at distance'], ['damp','web'],
    'Identify the guns before treating it as a short-range brawler.',
    'Test its projection and supporting tackle before choosing the fleet range.')],
 'vagabond': [variant('autocannon','Autocannon / mobile shield',['autocannons'],
    'Reference: roughly 20–30 km falloff fighting with Barrage, per the linked guide. This is not optimal, a hard cutoff or a guaranteed safe distance.',
    'Shield fits; buffer/active choices vary.', 'Projectile ammunition changes damage mix; drones may differ.',
    ['kite','active tank'], ['Autocannon mounts','Range control','Shield boosting if active'], ['web','damp'],
    'Make it respect supported tackle; do not assume catching it means surviving its close-range ammo.',
    'Use long webs and projection rather than chasing its fastest pilot.')],
 'arazu': [variant('tackle','Covert tackle / sensor damps',[],
    'Extended point/scram envelope. Normal frigate tackle distances are unsafe assumptions; heat, faction modules and links change reach.',
    'Tank is uncertain; support role is the important warning.', 'Do not infer main fleet damage from its small weapon contribution.',
    ['long tackle','damps','covert'], ['Long-range tackle','Damp effect','Covert arrival'], ['projection','damp'],
    'Treat initial tackle as a possible fleet setup. Preserve escape options and call for support.',
    'Keep useful lock range, watch follow-up arrivals and assign damage to the tackle screen.')],
 'curse': [variant('neut','Neutralizer / drone support',[],
    'Reference: medium T2 neuts at Recon V have 30 km optimal in the linked guide; faction/deadspace options can reach farther. Neut falloff and fit still matter.',
    'Shield and armor variants exist.', 'Drone choice changes damage; capacitor warfare is the main threat.',
    ['neuts','drones','weapon disruption','dscan immune'], ['Capacitor loss','Drones','Weapon disruption if fitted'], ['projection','damp'],
    'A capacitor-dependent brawler needs an injection/escape plan. Do not count on d-scan to rule it out.',
    'Identify which support ships are losing cap and pressure the Curse without collapsing your formation.')],
 'huginn': [variant('web','Long-web support',[],
    'Reference: T2 webs at Recon V reach 40 km before heat/other modifiers; faction examples reach 60 km in the guide. These are conditional examples, not maximum reach.',
    'Support fit and tank need observation.', 'Weapons are secondary to its range-control role.',
    ['long webs','dscan immune'], ['Web effect far beyond ordinary range','Friendly ships applying after the web'], ['projection','damp'],
    'Do not send unsupported fast tackle straight through the web envelope.',
    'Protect your screen; coordinate projection or EWAR against the web platform.')],
 'caracal': [
  variant('rapid','Rapid light / anti-tackle',['rapid light missiles'],
    'Light-missile projection with a burst/reload rhythm; actual missile reach depends on skills, ammo and fit.',
    'Shield fits are expected candidates, not confirmed.', 'Missile selection can change all four damage types.',
    ['anti-tackle','reload'], ['Light missiles','Burst then verified long reload'], ['projection','reload'],
    'Do not assume small signature alone saves your tackle. Watch a full clip before exploiting a reload.',
    'Protect tackle and call actual reloads; avoid treating every Caracal as rapid-light fitted.'),
  variant('heavy','HAM / heavy missile alternative',['heavy missiles'],
    'HAM brawl/projection and heavy-missile range fits are alternatives; there is no single Caracal engagement range.',
    'Shield fits vary.', 'Selectable missile damage; application changes with missile family.',
    ['missiles'], ['Launcher family','Application to small targets'], ['web','damp'],
    'Identify launcher behavior before choosing a frigate or cruiser engagement.',
    'Keep range and application assumptions separate from the hull count.')],
 'orthrus': [variant('rapid','Kiting / extended tackle',['rapid light missiles'],
    'Longer tackle than an ordinary cruiser; rapid-light and heavier-missile variants alter damage reach. No universal safe km boundary.',
    'Shield fits vary.', 'Missile selection changes damage mix.',
    ['kite','long tackle','anti-tackle','reload'], ['Extended tackle','Launcher behavior','Observed reload'], ['web','projection'],
    'Respect its tackle advantage and anti-tackle clip; use supported range control.',
    'Coordinate webs, projection and tackle; do not spend interceptors testing its scram range.')],
}

WEAPONS = [
 {'key':'blasters','name':'Hybrid blasters','cue':'Usually compact, chunky hybrid mounts. Compare the exact size against a mounted reference; silhouette alone is not proof.', 'behavior':'Close damage with falloff; kinetic/thermal. Ammo changes reach and tracking.', 'pair':'rails'},
 {'key':'rails','name':'Hybrid railguns','cue':'Elongated hybrid barrels/rails compared with blasters of the same size. Viewing angle and size can mislead.', 'behavior':'Longer hybrid reach; kinetic/thermal. Close angular motion can limit application.', 'pair':'blasters'},
 {'key':'autocannons','name':'Projectile autocannons','cue':'Compact gun assemblies, sometimes multiple barrels. Compare same-size examples rather than counting barrels.', 'behavior':'Fast cycling, falloff-heavy fighting; ammunition changes damage.', 'pair':'artillery'},
 {'key':'artillery','name':'Projectile artillery','cue':'Longer projectile barrels and larger breeches in many size families. Confirm with the reference and firing rhythm.', 'behavior':'Slower cycling, high volleys; reach and tracking depend on fit/ammo.', 'pair':'autocannons'},
 {'key':'pulse','name':'Pulse lasers','cue':'Compare emitter housings with beam mounts of the same size; beam color alone cannot establish pulse versus beam.', 'behavior':'Shorter laser family, with long-range ammo options; EM/thermal.', 'pair':'beam'},
 {'key':'beam','name':'Beam lasers','cue':'Use the exact mounted emitter reference; distance and camera angle can hide the distinguishing shape.', 'behavior':'Longer laser family; EM/thermal, capacitor and angular motion matter.', 'pair':'pulse'},
 {'key':'rapid light missiles','name':'Rapid light launchers','cue':'Launcher racks need a size-specific reference. A generic inventory icon is not the fitted 3D mount.', 'behavior':'Light missiles, burst damage and a long reload. Confirm behavior before exploiting downtime.', 'pair':'heavy missiles'},
 {'key':'heavy missiles','name':'HAM / heavy missile launchers','cue':'Use separate launcher-family references; small visual differences do not reveal ammunition.', 'behavior':'HAMs and heavy missiles have different reach/application. Missiles do not use turret tracking.', 'pair':'rapid light missiles'},
]
