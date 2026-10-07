/**
 * Singleton SSE manager (Phase 8).
 *
 * - Exactly one EventSource per page, no matter how many components
 *   subscribe or how often they rerender (refcounted).
 * - Native EventSource auto-reconnect; connection state is broadcast.
 * - Duplicate protection: events are deduped by their id
 *   (event_id / incident_id / workflow_id), bounded LRU-ish set.
 * - Clean teardown: no leaks, no stale listeners.
 */

export type StreamEventType = "zone_event" | "incident" | "connected";
export type ConnectionState = "connecting" | "open" | "closed" | "error";

export interface StreamMessage {
  type: StreamEventType;
  data: Record<string, unknown>;
}

type Handler = (msg: StreamMessage) => void;
type StateHandler = (s: ConnectionState) => void;

const MAX_SEEN = 500;

function eventId(type: string, data: Record<string, unknown>): string | null {
  for (const k of ["event_id", "incident_id", "workflow_id"]) {
    const v = data[k];
    if (typeof v === "string" && v) return `${type}:${v}`;
  }
  return null;
}

class EventStreamManager {
  private es: EventSource | null = null;
  private refs = 0;
  private handlers = new Set<Handler>();
  private stateHandlers = new Set<StateHandler>();
  private seen = new Set<string>();
  private state: ConnectionState = "closed";
  private url = "";

  private setState(s: ConnectionState) {
    this.state = s;
    for (const h of this.stateHandlers) {
      try {
        h(s);
      } catch {
        /* ignore handler errors */
      }
    }
  }

  getState(): ConnectionState {
    return this.state;
  }

  onState(h: StateHandler): () => void {
    this.stateHandlers.add(h);
    h(this.state);
    return () => {
      this.stateHandlers.delete(h);
    };
  }

  subscribe(h: Handler): () => void {
    this.handlers.add(h);
    return () => {
      this.handlers.delete(h);
    };
  }

  /** Idempotent: safe to call from every component mount. */
  connect(url: string): () => void {
    this.refs += 1;
    if (!this.es) {
      this.url = url;
      this.open();
    }
    let released = false;
    return () => {
      if (released) return;
      released = true;
      this.refs = Math.max(0, this.refs - 1);
      if (this.refs === 0) this.close();
    };
  }

  private open() {
    this.setState("connecting");
    const es = new EventSource(this.url);
    this.es = es;

    es.onopen = () => this.setState("open");
    es.onerror = () => {
      // EventSource retries automatically; surface the degraded state.
      if (es.readyState === EventSource.CLOSED) this.setState("closed");
      else this.setState("error");
    };

    const dispatch = (type: StreamEventType) => (ev: MessageEvent) => {
      let data: Record<string, unknown> = {};
      try {
        data = JSON.parse(ev.data);
      } catch {
        return;
      }
      const id = eventId(type, data);
      if (id) {
        if (this.seen.has(id)) return; // duplicate protection
        this.seen.add(id);
        if (this.seen.size > MAX_SEEN) {
          const first = this.seen.values().next().value;
          if (first) this.seen.delete(first);
        }
      }
      const msg = { type, data };
      for (const h of this.handlers) {
        try {
          h(msg);
        } catch {
          /* ignore handler errors */
        }
      }
    };

    es.addEventListener("zone_event", dispatch("zone_event") as EventListener);
    es.addEventListener("incident", dispatch("incident") as EventListener);
    es.addEventListener("connected", dispatch("connected") as EventListener);
  }

  private close() {
    this.es?.close();
    this.es = null;
    this.setState("closed");
  }

  /** Test-only: reset singleton state. */
  _resetForTests() {
    this.close();
    this.handlers.clear();
    this.stateHandlers.clear();
    this.seen.clear();
    this.refs = 0;
  }
}

export const eventStream = new EventStreamManager();
