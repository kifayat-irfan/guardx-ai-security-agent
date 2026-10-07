// Shared types — mirror backend/app/schemas/health.py 1:1.
// Phase 8 will extend this with Camera, Zone, Incident, IncidentReport.

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
