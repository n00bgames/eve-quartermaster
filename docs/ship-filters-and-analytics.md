# Ship filters, history and Fleet Commander

Source complete for 2.0 development; deployment is separate. No new migration is required beyond the existing report/metric tables and migration 0098 from the preceding account SSO work. Deploy matching frontend and API/worker code. No version bump or production change was performed for this pass.

## Ship Reports

Capsules are always excluded from listings, total hulls and distinct hull types, including when older saved Ship Reports are reopened or exported. This does not modify ordinary Inventory Reports.

Each imported, published ship class has an exclusion checkbox. **Subcaps** selects exclusions for shuttles and all capital/XL/XXL groups, including freighters, jump freighters, Rorquals, carriers, force auxiliaries, dreadnoughts, lancer dreadnoughts, command carriers, supercarriers and titans. Capital classification combines established group IDs/names with imported `rigSize >= 4` Dogma data, covering newly imported XL classes. **Clear exclusions** restores every class except capsules. Adjust individual checkboxes after either preset. Keep SDE current for complete classification.

Selections are saved in each report and appear in its results, CSV and PDF. They apply before totals and itemization. Existing reports do not acquire newly selected class filters; regenerate to change their contents. Capsule removal is the retrospective exception. Packaged quantities count individual hulls, not asset stacks. Reports remain creator-only with no public links.

## Fleet Commander

The assignable built-in role is **Fleet Commander**, above Officer and below Director. It defaults to Ship Reports and Analytics, plus the Navigation/Market and personal profile/appearance access common to utility roles. It can generate ship-only reports across stored character/corporation ownership. It does not require or grant general Assets/Inventory Report permissions. Those modules retain their own permissions. Accounts may combine this role with others; custom roles based on Fleet Commander inherit its rank.

Fleet Commander and higher may see all hull sizes in Ship Analytics. Below Fleet Commander, server-side filtering removes capital types from totals, distinct counts, type selectors, tables, history and metric exports. Direct API requests cannot bypass the restriction. Ship Report visibility remains governed by its separate authorized ownership scope; this capital restriction applies to Analytics.

Fleet-Commander-only accounts remain utility accounts: linking a character does not automatically collect its private assets/skills. Other assigned roles can enable their usual collection. Existing character opt-outs and corporation analytics authorization/exclusions apply to ship observations.

## Ship inventory Analytics

The new widget shows latest observed total hulls and distinct types, daily closing history for both, selectable history for a hull type, and a sortable by-type table. **All accessible ship owners** is the default; alternatively use the selected Analytics pilot scope. The existing reporting period controls the history window. Shuttles count in noncapital Analytics; the Subcaps report preset additionally excludes them.

History begins with future successful asset-sync snapshots or a manual/global Analytics snapshot. It cannot reconstruct inventory before observations existed. Quantities carry forward between observations; disappearing types receive explicit zero observations. Distinct types are deduplicated across owners instead of adding each owner's distinct count. Existing retention/checkpoint policy still applies. Report-generation class filters never change Analytics history. The data describes synchronized stock, not real-time ESI inventory.

CSV/JSON metric exports enforce the same capital and owner restrictions. Below Fleet Commander they expose allowed per-type observations, omitting stored aggregate ship gauges; the widget computes visible totals from the permitted type observations. Unknown/unresolved types fail closed for lower roles. Existing unrelated analytics metrics retain their established access rules.

## Verification

API regressions cover capsules in old/new reports, class validation, Subcaps and imported XL detection, saved CSV/PDF filters, role assignment/custom bases/combined roles, utility collection policy, character/corporation ownership, snapshot hooks, change retention, historical baselines, disappeared types, distinct-count deduplication, selected-capital denial, and filtered CSV/JSON exports. Synthetic browser fixtures show 40 hulls/7 types for Fleet Commander and 35 noncapital hulls/4 types for Officer, with a Subcaps report of 28 hulls/3 types. The synthetic PDF was rendered and visually checked. No live account permissions, inventory or server state were changed.
