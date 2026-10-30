import { useEffect, useState } from "react";
import { ENGINE_BASE_URL } from "./engine";

/**
 * The model each agent actually runs on, as the engine's router resolves it right now
 * (Groq first, Ollama fallback). UI labels read this instead of naming a model in code.
 */
export interface ModelRoute {
  provider: "groq" | "ollama" | "fake" | "none" | string;
  model: string;
  judgeModel?: string;
  downgradeNote?: string | null;
}

export interface ModelRoutes {
  cloudEnabled: boolean;
  localDefaultModel: string;
  roles: Record<string, ModelRoute>;
}

let cached: ModelRoutes | null = null;
let inflight: Promise<ModelRoutes | null> | null = null;
let fetchedAt = 0;
const MAX_AGE_MS = 30_000;

export async function fetchModelRoutes(force = false): Promise<ModelRoutes | null> {
  if (!force && cached && Date.now() - fetchedAt < MAX_AGE_MS) return cached;
  if (inflight) return inflight;
  inflight = fetch(`${ENGINE_BASE_URL}/models`)
    .then((r) => (r.ok ? r.json() : null))
    .then((data) => {
      if (!data) return cached;
      const roles: Record<string, ModelRoute> = {};
      for (const [role, v] of Object.entries<any>(data.judge_validation?.agent_validations || {})) {
        roles[role] = {
          provider: v.generator_provider,
          model: v.generator_model,
          judgeModel: v.judge_model,
          downgradeNote: v.downgrade_note,
        };
      }
      cached = { cloudEnabled: Boolean(data.cloud_enabled), localDefaultModel: data.local_default_model || "", roles };
      fetchedAt = Date.now();
      return cached;
    })
    .catch(() => cached)
    .finally(() => {
      inflight = null;
    });
  return inflight;
}

export function useModelRoutes(): ModelRoutes | null {
  const [routes, setRoutes] = useState<ModelRoutes | null>(cached);
  useEffect(() => {
    let alive = true;
    const load = () => fetchModelRoutes().then((r) => alive && r && setRoutes(r));
    load();
    const t = setInterval(load, MAX_AGE_MS);
    return () => {
      alive = false;
      clearInterval(t);
    };
  }, []);
  return routes;
}

const PROVIDER_LABEL: Record<string, string> = { groq: "Groq", ollama: "Ollama • Local", fake: "Test model" };

/** "gpt-oss-120b • Groq", or "Engine offline" when the route is not known yet. */
export function routeLabel(route: ModelRoute | undefined): string {
  if (!route || !route.model) return route?.provider === "none" ? "No model available" : "Model: checking…";
  const model = route.model.split("/").pop();
  return `${model} • ${PROVIDER_LABEL[route.provider] || route.provider}`;
}
