import { useEffect, useMemo, useState } from "react";
import "./headerClocks.css";

export function HeaderClocks({ localTimeZone }: { localTimeZone: string }) {
  const [now, setNow] = useState(() => new Date());
  const clocks = useMemo(() => [
    { label: "EVE", zone: "UTC" },
    { label: "Local", zone: localTimeZone },
  ].map((clock) => ({
    ...clock,
    time: new Intl.DateTimeFormat(undefined, {
      timeZone: clock.zone, hour: "2-digit", minute: "2-digit", second: "2-digit", hourCycle: "h23",
    }),
    date: new Intl.DateTimeFormat(undefined, { timeZone: clock.zone, dateStyle: "full" }),
  })), [localTimeZone]);

  useEffect(() => {
    const update = () => setNow(new Date());
    const timer = window.setInterval(update, 1000);
    document.addEventListener("visibilitychange", update);
    return () => {
      window.clearInterval(timer);
      document.removeEventListener("visibilitychange", update);
    };
  }, []);

  return <div className="header-clocks" role="group" aria-label="EVE and local clocks">
    {clocks.map(({ label, zone, time, date }) => <div className="header-clock" key={label} title={`${date.format(now)} · ${zone}`}>
      <span className="header-clock-label">{label}<small>{zone === "UTC" ? "UTC" : zone.split("/").pop()?.replace(/_/g, " ")}</small></span>
      <time dateTime={now.toISOString()} aria-label={`${label} time, ${time.format(now)}, ${zone}`}>{time.format(now)}</time>
    </div>)}
  </div>;
}
