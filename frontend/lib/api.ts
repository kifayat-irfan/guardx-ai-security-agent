import type {
  Camera,
  CameraStatus,
  DetailedHealth,
  HealthStatus,
  Incident,
  IncidentDecision,
  IncidentDetail,
  IncidentList,
  IncidentReport,
  IndexReport,
  LangChainStatus,
  PolicyMeta,
  PolicySearchResult,
  RagStatus,
  WorkflowState,
  Zone,
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

// -- zones ---------------------------------------------------------------

export interface ZoneInput {
  camera_id: string;
  name: string;
  polygon: number[][] | { x: number; y: number }[];
  dwell_seconds?: number;
  cooldown_seconds?: number;
  active?: boolean;
}

async function patch<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    cache: "no-store",
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API ${path} failed: ${res.status} ${text}`);
  }
  return res.json() as Promise<T>;
}

async function del_(path: string): Promise<void> {
  const res = await fetch(`${API_URL}${path}`, {
    method: "DELETE",
    cache: "no-store",
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API ${path} failed: ${res.status} ${text}`);
  }
}

export function listZones(cameraId: string): Promise<Zone[]> {
  return get<Zone[]>(`/api/v1/zones?camera_id=${cameraId}`);
}

export function createZone(input: ZoneInput): Promise<Zone> {
  return post<Zone>("/api/v1/zones", input);
}

export function updateZone(
  id: string,
  body: Partial<ZoneInput>,
): Promise<Zone> {
  return patch<Zone>(`/api/v1/zones/${id}`, body);
}

export function deleteZone(id: string): Promise<void> {
  return del_(`/api/v1/zones/${id}`);
}

// -- policies / RAG ------------------------------------------------------

export function listPolicies(): Promise<PolicyMeta[]> {
  return get<PolicyMeta[]>("/api/v1/policies");
}

export function getRagStatus(): Promise<RagStatus> {
  return get<RagStatus>("/api/v1/policies/status");
}

export function reindexPolicies(): Promise<IndexReport> {
  return post<IndexReport>("/api/v1/policies/reindex");
}

export function searchPolicies(
  query: string,
  top_k = 3,
): Promise<PolicySearchResult> {
  return post<PolicySearchResult>("/api/v1/policies/search", {
    query,
    top_k,
  });
}

export function getLangChainStatus(): Promise<LangChainStatus> {
  return get<LangChainStatus>("/api/v1/policies/langchain/status");
}

export function analyzeIncident(event: Record<string, unknown>): Promise<IncidentDecision> {
  return post<IncidentDecision>("/api/v1/incidents/analyze", event);
}

export function getWorkflow(workflowId: string): Promise<WorkflowState> {
  return get<WorkflowState>(`/api/v1/incidents/workflows/${workflowId}`);
}

export interface IncidentFilters {
  page?: number;
  page_size?: number;
  status?: string;
  severity?: string;
  camera_id?: string;
  zone_name?: string;
}

export function listIncidents(f: IncidentFilters = {}): Promise<IncidentList> {
  const q = new URLSearchParams();
  for (const [k, v] of Object.entries(f)) {
    if (v !== undefined && v !== "") q.set(k, String(v));
  }
  const s = q.toString();
  return get<IncidentList>(`/api/v1/incidents${s ? `?${s}` : ""}`);
}

export function getIncidentDetail(id: string): Promise<IncidentDetail> {
  return get<IncidentDetail>(`/api/v1/incidents/${id}`);
}

export function getIncidentReport(id: string): Promise<IncidentReport> {
  return get<IncidentReport>(`/api/v1/incidents/${id}/report`);
}

export function reprocessIncident(id: string): Promise<IncidentDecision> {
  return post<IncidentDecision>(`/api/v1/incidents/${id}/reprocess`, {});
}

export { API_URL };
