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
}

export interface HealthStatus {
  status: string;
  version: string;
}

export interface ComponentStatus {
  status: "up" | "down";
  detail?: string | null;
}

export interface DetailedHealth {
  status: "ok" | "degraded";
  version: string;
  postgres: ComponentStatus;
  chromadb: ComponentStatus;
  yolo: ComponentStatus;
}
