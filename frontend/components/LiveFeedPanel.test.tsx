import { act, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import LiveFeedPanel from "./LiveFeedPanel";
import type { StreamMessage } from "@/lib/eventStream";

const onMessageCapture: {
  fn: ((m: StreamMessage) => void) | null;
} = { fn: null };

vi.mock("@/lib/useEventStream", () => ({
  useEventStream: (fn: (m: StreamMessage) => void) => {
    onMessageCapture.fn = fn;
    return "open";
  },
}));

const analyzeMock = vi.fn();

vi.mock("@/lib/api", () => ({
  analyzeIncident: (...args: unknown[]) => analyzeMock(...args),
  API_URL: "http://test",
}));

function send(msg: StreamMessage) {
  act(() => {
    onMessageCapture.fn?.(msg);
  });
}

const zoneEnter: StreamMessage = {
  type: "zone_event",
  data: {
    event_id: "evt-1",
    event_type: "zone_enter",
    zone_name: "server-room",
    camera_id: "cam-1",
    tracking_id: 2,
    confidence: 0.87,
    timestamp: 12.5,
  },
};

beforeEach(() => {
  vi.clearAllMocks();
  onMessageCapture.fn = null;
  analyzeMock.mockResolvedValue({ status: "completed" });
});

describe("LiveFeedPanel", () => {
  it("renders empty states initially", () => {
    render(<LiveFeedPanel />);
    expect(screen.getByText(/no zone events yet/i)).toBeInTheDocument();
    expect(screen.getByText(/no incidents yet/i)).toBeInTheDocument();
  });

  it("displays zone_enter with an obvious ENTER badge", () => {
    render(<LiveFeedPanel />);
    send(zoneEnter);
    expect(screen.getByText("ENTER")).toBeInTheDocument();
    expect(screen.getByText("server-room")).toBeInTheDocument();
  });

  it("displays incidents from the stream", () => {
    render(<LiveFeedPanel />);
    send({
      type: "incident",
      data: {
        incident_id: "inc-1",
        status: "completed",
        severity: "HIGH",
        zone_name: "server-room",
        summary: "A person entered the server room.",
      },
    });
    expect(screen.getByText("HIGH")).toBeInTheDocument();
    expect(
      screen.getByText("A person entered the server room."),
    ).toBeInTheDocument();
  });

  it("auto-analyzes zone_enter but not zone_exit", async () => {
    render(<LiveFeedPanel />);
    send(zoneEnter);
    expect(analyzeMock).toHaveBeenCalledTimes(1);
    expect(analyzeMock.mock.calls[0][0].event_id).toBe("evt-1");

    send({
      type: "zone_event",
      data: { ...zoneEnter.data, event_id: "evt-2", event_type: "zone_exit" },
    });
    expect(analyzeMock).toHaveBeenCalledTimes(1);
  });

  it("does not analyze the same event twice", () => {
    render(<LiveFeedPanel />);
    send(zoneEnter);
    send(zoneEnter); // duplicate delivery
    expect(analyzeMock).toHaveBeenCalledTimes(1);
  });

  it("shows the live connection badge", () => {
    render(<LiveFeedPanel />);
    expect(screen.getByRole("status", { name: "Stream live" })).toHaveTextContent(
      /live/,
    );
  });
});
