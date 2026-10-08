import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import CameraHud from "./CameraHud";
import type { CameraStatus, ZoneEvent } from "@/lib/types";

const baseStatus: CameraStatus = {
  camera_id: "cam-1",
  status: "streaming",
  fps: 12.5,
  person_count: 1,
  frame_index: 42,
  frame_width: 640,
  frame_height: 480,
  inference_ms: 88.3,
  error: null,
  detections: [
    {
      bbox: [64, 48, 192, 288],
      confidence: 0.87,
      class_id: 0,
      class_name: "person",
      track_id: 7,
      frame_index: 42,
      timestamp: 1.5,
    },
  ],
  active_zones: 1,
  active_track_ids: [7],
  zone_events: [],
  track_states: [],
};

const enterEvent: ZoneEvent = {
  event_id: "evt-1",
  camera_id: "cam-1",
  zone_id: "zone-1",
  zone_name: "server-room",
  tracking_id: 7,
  event_type: "zone_enter",
  timestamp: 1.5,
  confidence: 0.87,
  bounding_box: [],
  point: [],
  metadata: {},
};

describe("CameraHud", () => {
  it("shows camera name, REC indicator, and clock", () => {
    render(
      <CameraHud
        cameraName="Gate Cam"
        cameraId="cam-1-abcdef"
        status={baseStatus}
        streaming
        alert={null}
      />,
    );
    expect(screen.getByText(/Gate Cam/)).toBeInTheDocument();
    expect(screen.getByText("REC")).toBeInTheDocument();
    expect(screen.getByLabelText("Camera HUD overlay")).toBeInTheDocument();
  });

  it("shows OFFLINE when not streaming", () => {
    render(
      <CameraHud
        cameraName="Gate Cam"
        cameraId="cam-1"
        status={null}
        streaming={false}
        alert={null}
      />,
    );
    expect(screen.getByText("OFFLINE")).toBeInTheDocument();
    expect(screen.queryByText("REC")).not.toBeInTheDocument();
  });

  it("draws a detection box with track label and confidence", () => {
    const { container } = render(
      <CameraHud
        cameraName="Gate Cam"
        cameraId="cam-1"
        status={baseStatus}
        streaming
        alert={null}
      />,
    );
    expect(screen.getByText("T7 87%")).toBeInTheDocument();
    const box = container.querySelector(
      ".border-emerald-400\\/80",
    ) as HTMLElement | null;
    expect(box).not.toBeNull();
    // bbox [64,48,192,288] on a 640x480 frame -> left 10%, top 10%, w 20%, h 50%
    expect(box?.style.left).toBe("10%");
    expect(box?.style.top).toBe("10%");
    expect(box?.style.width).toBe("20%");
    expect(box?.style.height).toBe("50%");
  });

  it("renders no boxes when frame dimensions are unknown", () => {
    render(
      <CameraHud
        cameraName="Gate Cam"
        cameraId="cam-1"
        status={{ ...baseStatus, frame_width: 0, frame_height: 0 }}
        streaming
        alert={null}
      />,
    );
    expect(screen.queryByText("T7 87%")).not.toBeInTheDocument();
  });

  it("flashes an intrusion banner for a zone_enter alert", () => {
    render(
      <CameraHud
        cameraName="Gate Cam"
        cameraId="cam-1"
        status={baseStatus}
        streaming
        alert={enterEvent}
      />,
    );
    const banner = screen.getByRole("alert");
    expect(banner).toHaveTextContent(/INTRUSION/);
    expect(banner).toHaveTextContent("SERVER-ROOM");
    expect(banner).toHaveTextContent("TRACK 7");
  });

  it("shows telemetry in the bottom strip", () => {
    render(
      <CameraHud
        cameraName="Gate Cam"
        cameraId="cam-1"
        status={baseStatus}
        streaming
        alert={null}
      />,
    );
    expect(screen.getByText("12.5")).toBeInTheDocument();
    expect(screen.getByText("88ms")).toBeInTheDocument();
  });
});
