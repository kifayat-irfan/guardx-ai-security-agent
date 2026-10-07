import type { DetailedHealth, HealthStatus } from "./types";

const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`API ${path} failed: ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export function getHealth(): Promise<HealthStatus> {
  return get<HealthStatus>("/api/v1/health");
}

export function getDetailedHealth(): Promise<DetailedHealth> {
  return get<DetailedHealth>("/api/v1/health/detailed");
}

export { API_URL };
