import type {
  Camera,
  CameraStatus,
  DetailedHealth,
  HealthStatus,
} from "./types";

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

async function post<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
    cache: "no-store",
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API ${path} failed: ${res.status} ${text}`);
  }
  return res.json() as Promise<T>;
}

export function listCameras(): Promise<Camera[]> {
  return get<Camera[]>("/api/v1/cameras");
}

export function createCamera(
  name: string,
  source_type: string,
  source_url: string,
): Promise<Camera> {
  return post<Camera>("/api/v1/cameras", { name, source_type, source_url });
}

export function startCamera(id: string): Promise<CameraStatus> {
  return post<CameraStatus>(`/api/v1/cameras/${id}/start`);
}

export function stopCamera(id: string): Promise<CameraStatus> {
  return post<CameraStatus>(`/api/v1/cameras/${id}/stop`);
}

export function getCameraStatus(id: string): Promise<CameraStatus> {
  return get<CameraStatus>(`/api/v1/cameras/${id}/status`);
}

export function streamUrl(id: string): string {
  return `${API_URL}/api/v1/cameras/${id}/stream`;
}

export { API_URL };
