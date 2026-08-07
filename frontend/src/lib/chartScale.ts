export type ChartDateTick = { time: number; label: string };

function niceStep(span: number, targetTicks = 5): number {
  const raw = Math.max(Math.abs(span), Number.EPSILON) / Math.max(targetTicks, 1);
  const magnitude = 10 ** Math.floor(Math.log10(raw));
  const fraction = raw / magnitude;
  const factor = fraction <= 1 ? 1 : fraction <= 2 ? 2 : fraction <= 2.5 ? 2.5 : fraction <= 5 ? 5 : 10;
  return factor * magnitude;
}

export function chartDomain(values: number[], includeZero = false): { low: number; high: number; ticks: number[] } {
  const finite = values.filter(Number.isFinite);
  if (finite.length === 0) return { low: 0, high: 1, ticks: [0, 0.25, 0.5, 0.75, 1] };
  const rawMin = Math.min(...finite);
  const rawMax = Math.max(...finite);
  const rawSpan = rawMax - rawMin;
  const baseSpread = rawSpan || Math.max(Math.abs(rawMax) * 0.1, 1);
  let desiredLow = rawMin - baseSpread * 0.04;
  let desiredHigh = rawMax + baseSpread * 0.08;
  if (includeZero) {
    desiredLow = Math.min(0, desiredLow);
    desiredHigh = Math.max(0, desiredHigh);
  }
  const step = niceStep(desiredHigh - desiredLow);
  let low = Math.floor(desiredLow / step) * step;
  let high = Math.ceil(desiredHigh / step) * step;
  if (high - rawMax < baseSpread * 0.05) high += step;
  if (!includeZero && rawMin >= 0 && low < 0) low = 0;
  if (low === high) high = low + step;
  const ticks: number[] = [];
  for (let value = low, guard = 0; value <= high + step / 2 && guard < 12; value += step, guard += 1) {
    ticks.push(Math.abs(value) < step / 1_000_000 ? 0 : value);
  }
  return { low, high, ticks };
}

export function compactChartValue(value: number): string {
  const absolute = Math.abs(value);
  const suffixes: [number, string][] = [[1e12, "T"], [1e9, "B"], [1e6, "M"], [1e3, "K"]];
  const match = suffixes.find(([threshold]) => absolute >= threshold);
  if (!match) return Math.round(value).toLocaleString();
  const scaled = value / match[0];
  const digits = Math.abs(scaled) >= 100 ? 0 : Math.abs(scaled) >= 10 ? 1 : 2;
  return `${scaled.toFixed(digits).replace(/\.0+$|(?<=\.[0-9])0+$/, "")}${match[1]}`;
}

function utcDate(time: number): Date {
  const value = new Date(time);
  return new Date(Date.UTC(value.getUTCFullYear(), value.getUTCMonth(), value.getUTCDate()));
}

function dateLabel(time: number, cadence: "day" | "week" | "month" | "quarter"): string {
  const options: Intl.DateTimeFormatOptions = cadence === "month"
    ? { month: "short", timeZone: "UTC" }
    : cadence === "quarter"
      ? { month: "short", year: "2-digit", timeZone: "UTC" }
      : { month: "short", day: "numeric", timeZone: "UTC" };
  return new Date(time).toLocaleDateString(undefined, options);
}

export function adaptiveDateTicks(minTime: number, maxTime: number, selectedDays?: number): ChartDateTick[] {
  if (minTime === maxTime) return [{ time: minTime, label: dateLabel(minTime, "day") }];
  const actualDays = Math.max(1, Math.ceil((maxTime - minTime) / 86_400_000));
  const spanDays = selectedDays ?? actualDays;
  const cadence: "day" | "week" | "month" | "quarter" = spanDays <= 10 ? "day" : spanDays <= 45 ? "week" : spanDays <= 120 ? "month" : "quarter";
  const ticks = [minTime];
  let cursor = utcDate(minTime);
  while (cursor.getTime() < maxTime) {
    if (cadence === "day") cursor.setUTCDate(cursor.getUTCDate() + 1);
    if (cadence === "week") cursor.setUTCDate(cursor.getUTCDate() + 7);
    if (cadence === "month") cursor = new Date(Date.UTC(cursor.getUTCFullYear(), cursor.getUTCMonth() + 1, 1));
    if (cadence === "quarter") cursor = new Date(Date.UTC(cursor.getUTCFullYear(), cursor.getUTCMonth() + 3, 1));
    if (cursor.getTime() < maxTime) ticks.push(cursor.getTime());
  }
  const minimumGap = (maxTime - minTime) * 0.08;
  if (maxTime - ticks[ticks.length - 1] >= minimumGap) ticks.push(maxTime);
  else ticks[ticks.length - 1] = maxTime;
  return Array.from(new Set(ticks)).map((time) => ({ time, label: dateLabel(time, cadence) }));
}
