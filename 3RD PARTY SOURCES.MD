# Third-Party Sources and Research Acknowledgments

This file records external software, data sources, documentation, and reference implementations that materially inform EVE Quartermaster (EQM). It distinguishes **research and validation** from code or assets actually incorporated into EQM.

EQM is licensed under the GNU Affero General Public License v3.0 or later. A third party's appearance here does not change EQM's license, imply endorsement, or claim affiliation.

## Research and product references

| Source | Author / steward | License or terms | EQM use |
| --- | --- | --- | --- |
| [EVE Buddy](https://github.com/ErikKalkoken/evebuddy) | Erik Kalkoken and contributors | [MIT License](https://github.com/ErikKalkoken/evebuddy/blob/main/LICENSE), copyright 2024 Erik Kalkoken | Product and architecture research. Its consolidated character/corporation views, cross-character discovery, contextual information windows, background updates, and notification model helped inform EQM planning. EQM's Sync & Freshness Center and related UI are independent implementations using EQM's own models, permissions, privacy controls, API, and visual system. No EVE Buddy source code or assets are presently incorporated. Reviewed against the public repository and v0.68-era feature set in August 2026. |
| [Pyfa](https://github.com/pyfa-org/Pyfa) | Pyfa contributors | [GNU GPL v3](https://github.com/pyfa-org/Pyfa/blob/master/LICENSE) | External validation reference for fitting calculations and character-skill comparisons. Human-produced Pyfa 2.68.0 result captures are stored as test evidence with simulator state and tolerances. EQM does not bundle Pyfa or copy its implementation; fitting logic is independently derived from imported CCP SDE Dogma and verified behavior. |
| [EVE Tools Battle Reports](https://br.evetools.org/recent-brs) | EVE Tools operators | Public web service; no source-code license was identified during the August 2026 review | Product and information-architecture research for readable battle summaries: team cards, involved pilots, chronological kills, damage ranking, and hull composition pivots. EQM independently implements these ideas over its existing ESI-canonical Killboard models, uses its own deterministic grouping/team logic and visual system, and incorporates no EVE Tools source code, assets, branding, or report data. |

## Authoritative platform and game-data sources

### PI planner research (September 2026)

- **Solving PI**, Ryan Allen / Admiral Leyton / Lacking Tallent: [repository](https://github.com/LackingTallent/SolvingPI), [application](https://solvingpi.com/). Supplied source package identified as `solving-pi-v9` 0.1.0; inspected live UI identified itself as `v9.0.0-proto`, commit `61635d5`. No source-reuse license was identified in the supplied archive or inspected repository. Used for feature-direction research and synthetic behavioral probes only. EQM's planner, Rust allocator, market fills, interface and layouts are independently implemented; no SPI code, branding, or bundled community templates are incorporated.
- **CCP/EVE developer PI guide**: [extraction calculation](https://developers.eveonline.com/docs/guides/pi/). The planner reuses EQM's existing implementation of the documented extraction calculation; it does not substitute ESI's raw `qty_per_cycle` for average program yield.
- **EVE Online native template format**: [CCP Bee's announcement and OldGuyMonty's public game-export example, post 7](https://forums.eveonline.com/t/planetary-industry-templates/470630). Used to identify interoperable clipboard field names and one-based link/route indices. EQM generates original coordinates/layouts and does not redistribute the example layout. Live-client import is not yet validation evidence.
- **Bundled CCP game data**: `backend/app/data/pi_planning_pins.json` and `backend/tests/fixtures/pi-planner-catalog.v1.json` are subsets of CCP SDE build 3478781 (2026-08-25T11:07:20Z), inspected 2026-09-09. They contain game types, volumes, Dogma and schematics, under the applicable CCP developer/data terms below. Resource/planet availability reuses EQM's existing shortage-report matrix and its documented EVE University provenance.

The complete PI planner contract and limitations are in [docs/pi-operation-planner.md](docs/pi-operation-planner.md).

| Source | Steward | Terms | EQM use |
| --- | --- | --- | --- |
| [EVE Swagger Interface (ESI)](https://developers.eveonline.com/docs/services/esi/) and EVE SSO | CCP hf. | [CCP Developer License Agreement](https://developers.eveonline.com/license-agreement) and applicable developer policies | Authorized character and corporation data, public universe data, and permitted in-client actions. EQM observes scopes, user consent, ESI cache headers, error limits, and revocation. |
| [EVE Online Static Data Export (SDE)](https://developers.eveonline.com/docs/services/static-data/) | CCP hf. | CCP's applicable developer license and data terms | Universe structure, types, groups, blueprints, attributes, effects, and Dogma inputs. The locally imported SDE is authoritative for the game-data version installed by an EQM operator. |

EVE Online, EVE, CCP, and related marks and imagery are trademarks or registered trademarks of CCP hf. EQM is not affiliated with or endorsed by CCP Games.

## Packaged dependencies

EQM also uses normal open-source runtime and build dependencies declared in its Python requirements, `package.json`, Gradle files, container images, and lockfiles. Those manifests are the authoritative dependency inventory; each dependency remains governed by its own license. This research ledger does not replace license notices that a dependency requires in a distributed binary.

## Contribution rule

When a change is materially based on another project, dataset, article, captured simulator result, or copied asset:

1. Record the source, author/steward, URL, version or commit/date, license or governing terms, and exact EQM use here.
2. State whether the use is research, validation evidence, adapted code, copied code, data, or an asset.
3. Preserve copyright and permission notices required by the source license.
4. Do not copy from a source with unclear or incompatible terms; independently implement the behavior from public specifications instead.
5. Keep externally captured validation evidence reproducible by recording profile, module state, charges, drones, implants, boosters, environmental effects, and rounding assumptions.

This file is an engineering provenance record, not legal advice. Maintainers should obtain qualified advice when a proposed use has uncertain licensing consequences.
