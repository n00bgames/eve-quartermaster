import React from "react";
import { createRoot } from "react-dom/client";
import { PiPlanner } from "../../src/features/industry/PiPlanner";
import "../../src/styles.css";
import "../../src/responsive.css";

async function api<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, {...options, headers: {"Content-Type":"application/json"}});
  if (!response.ok) {const error=await response.json();throw new Error(typeof error.detail === "string" ? error.detail : JSON.stringify(error.detail));}
  return response.status===204 ? undefined as T : response.json();
}
createRoot(document.getElementById("root")!).render(<main style={{padding:24,maxWidth:1450,margin:"0 auto"}}><PiPlanner api={api}/></main>);
