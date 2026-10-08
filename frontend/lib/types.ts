// Shared types — mirror backend schemas 1:1.
// Phase 7/8 will extend this with Incident, IncidentReport.

export interface Detection {
  bbox: number[];
  confidence: number;
  class_id: number;
  class_name: string;
  track_id: number | null;
  frame_index: number;
  timestamp: number;
}

export interface Camera {
  id: string;
  name: string;
  source_type: string;
  source_url: string;
  status: string;
  created_at: string;
}

export interface CameraStatus {
  camera_id: string;
  status: string;
  fps: number;
  person_count: number;
  frame_index: number;
  inference_ms: number;
  error: string | null;
  detections: Detection[];
  active_zones: number;
  active_track_ids: number[];
  zone_events: ZoneEvent[];
  track_states: TrackState[];
}

export interface Zone {
  id: string;
  camera_id: string;
  name: string;
  polygon: number[][];
  dwell_seconds: number;
  cooldown_seconds: number;
  active: boolean;
  created_at: string;
  updated_at: string;
}

export interface ZoneEvent {
  event_id: string;
  camera_id: string;
  zone_id: string;
  zone_name: string;
  tracking_id: number;
  event_type: "zone_enter" | "zone_exit";
  timestamp: number;
  confidence: number;
  bounding_box: number[];
  point: number[];
  metadata: Record<string, unknown>;
}

export interface TrackState {
  camera_id: string;
  zone_id: string;
  zone_name: string;
  tracking_id: number;
  state: "outside" | "pending" | "inside";
  inside_since: number | null;
}

export interface PolicyMeta {
  policy_id: string;
  title: string;
  version: string;
  effective_date: string;
  category: string;
  source: string;
}

export interface RetrievedChunk {
  chunk_id: string;
  policy_id: string;
  policy_title: string;
  section: string;
  content: string;
  score: number;
  metadata: Record<string, string>;
}

export interface PolicySearchResult {
  query: string;
  top_k: number;
  chunks: RetrievedChunk[];
  took_ms: number;
}

export interface RagStatus {
  state: "unavailable" | "initializing" | "ready" | "error";
  detail: string | null;
  collection: string | null;
  chunk_count: number;
  embedding_model: string | null;
}

export interface IndexReport {
  indexed_documents: number;
  indexed_chunks: number;
  collection: string;
  embedding_model: string;
  duration_ms: number;
  indexed_at: string;
}

export interface LangChainStatus {
  state: "unavailable" | "configured" | "ready" | "error";
  detail: string | null;
  llm_model: string | null;
  llm_provider: string | null;
  llm_available: boolean;
  retriever_ready: boolean;
  collection: string | null;
}

export interface HealthStatus {
  status: string;
  version: string;
}

export interface ComponentStatus {
  /** up | down | error | unavailable | initializing | configured | degraded */
  status: string;
  detail?: string | null;
}

export interface DetailedHealth {
  status: "ok" | "degraded";
  version: string;
  postgres: ComponentStatus;
  chromadb: ComponentStatus;
  yolo: ComponentStatus;
  langchain?: ComponentStatus; // Phase 5
  langgraph?: ComponentStatus; // Phase 6
  postgres_incidents?: ComponentStatus; // Phase 7
  n8n?: ComponentStatus; // Phase 9
}

export interface IncidentDecision {
  workflow_id: string;
  event_id: string;
  status: string;
  summary: string | null;
  severity: string | null;
  recommended_action: string | null;
  confidence: number | null;
  cited_policy_chunk_ids: string[];
  retrieved_policy_count: number;
  error: { node: string; code: string; message: string } | null;
  started_at: string;
  finished_at: string;
  duration_ms: number;
}

export interface WorkflowState {
  workflow_id: string;
  status: string;
  current_node: string | null;
  started_at: string;
  finished_at: string | null;
  timings_ms: Record<string, number>;
  error: { node: string; code: string; message: string } | null;
  retrieved_chunk_ids: string[];
  decision: IncidentDecision | null;
}

export interface Incident {
  id: string;
  external_event_id: string;
  camera_id: string;
  zone_id: string;
  zone_name: string;
  tracking_id: number;
  event_type: string;
  occurred_at: string;
  detection_confidence: number;
  bounding_box: number[];
  point: number[];
  event_data: Record<string, unknown>;
  status: string;
  severity: string | null;
  summary: string | null;
  recommended_action: string | null;
  analysis_confidence: number | null;
  error: { node: string; code: string; message: string } | null;
  workflow_id: string;
  created_at: string;
  updated_at: string;
}

export interface IncidentReport {
  id: string;
  incident_id: string;
  report_type: string;
  title: string;
  summary: string | null;
  severity: string | null;
  recommended_action: string | null;
  reasoning: string | null;
  cited_policy_chunk_ids: string[];
  retrieved_policy_count: number;
  retrieved_chunk_ids: string[];
  generated_at: string;
  created_at: string;
}

export interface IncidentDetail {
  incident: Incident;
  report: IncidentReport | null;
}

export interface IncidentList {
  items: Incident[];
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
}
