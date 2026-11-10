import { Download, Factory } from "lucide-react";
import { useMemo } from "react";
import type { PlanetaryIndustryPayload } from "../../types/planetaryIndustry";
import { buildPlanetaryFacilitiesExport, buildPlanetaryFacilitiesReport, type FacilitiesScope } from "./planetaryFacilitiesExport";
import type { PlanetaryExportFormat } from "./planetaryExport";

const countLabel = (count: number, singular: string, plural = `${singular}s`) => `${count} ${count === 1 ? singular : plural}`;

export function PlanetaryFacilitiesReportPanel({ data, scope }: { data: PlanetaryIndustryPayload | null; scope: FacilitiesScope }) {
  const report = useMemo(() => data ? buildPlanetaryFacilitiesReport(data, scope) : null,
    [data, scope.character, scope.system, scope.planet_type]);
  function download(format: PlanetaryExportFormat) {
    if (!data) return;
    const result = buildPlanetaryFacilitiesExport(data, format, scope);
    const url = URL.createObjectURL(new Blob([result.text], { type: result.mimeType }));
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = result.filename;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  return <section className="planetary-facilities-export" aria-labelledby="pi-facilities-title">
    <div className="section-heading compact">
      <div><h3 id="pi-facilities-title"><Factory size={18} />PI facilities report</h3>
        <p>Installed buildings, schematics, extractor programs and routes. Includes empty and unconfigured facilities.</p></div>
      <div className="button-row compact">
        <button type="button" disabled={!report?.summary.colony_count} onClick={() => download("csv")}><Download size={16} />Facilities CSV</button>
        <button type="button" disabled={!report?.summary.colony_count} onClick={() => download("json")}><Download size={16} />Facilities JSON</button>
      </div>
    </div>
    <p>{report ? `${countLabel(report.summary.facility_count, "facility", "facilities")} · ${countLabel(report.summary.colony_count, "colony", "colonies")} · ${countLabel(report.summary.factory_count, "processor")} · ${countLabel(report.summary.extractor_count, "extractor")} · ${countLabel(report.summary.unconfigured_factory_count, "unconfigured processor")}` : "Loading facilities…"}</p>
    <small>Uses the Character, System and Planet type filters above. CSV has one row per facility; JSON retains full details and routes. Observed and projected values stay separate. This report is for review, not EVE layout import.</small>
  </section>;
}
