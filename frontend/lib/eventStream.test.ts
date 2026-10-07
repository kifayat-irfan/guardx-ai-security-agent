import { beforeEach, describe, expect, it, vi } from "vitest";
import { eventStream } from "./eventStream";

// --- FakeEventSource -------------------------------------------------------

class FakeEventSource {
  static instances: FakeEventSource[] = [];
  listeners = new Map<string, ((ev: MessageEvent) => void)[]>();
  onopen: (() => void) | null = null;
  onerror: (() => void) | null = null;
  readyState = 0;
  closed = false;
  url: string;

  constructor(url: string) {
    this.url = url;
    FakeEventSource.instances.push(this);
  }

  addEventListener(type: string, fn: (ev: MessageEvent) => void) {
    const arr = this.listeners.get(type) ?? [];
    arr.push(fn);
    this.listeners.set(type, arr);
  }

  emit(type: string, data: unknown) {
    const ev = { data: JSON.stringify(data) } as MessageEvent;
    for (const fn of this.listeners.get(type) ?? []) fn(ev);
  }

  open() {
    this.readyState = 1;
    this.onopen?.();
  }

  fail() {
    this.readyState = 2;
    this.onerror?.();
  }

  close() {
    this.closed = true;
    this.readyState = 2;
  }
}

beforeEach(() => {
  FakeEventSource.instances = [];
  vi.stubGlobal("EventSource", FakeEventSource);
  eventStream._resetForTests();
});

describe("eventStream singleton", () => {
  it("opens exactly one EventSource for multiple connects", () => {
    const r1 = eventStream.connect("http://x/stream");
    const r2 = eventStream.connect("http://x/stream");
    expect(FakeEventSource.instances).toHaveLength(1);
    r1();
    // still referenced once -> stays open
    expect(FakeEventSource.instances[0].closed).toBe(false);
    r2();
    // all released -> closed
    expect(FakeEventSource.instances[0].closed).toBe(true);
  });

  it("fans out messages to all subscribers", () => {
    eventStream.connect("http://x/stream");
    const a: string[] = [];
    const b: string[] = [];
    eventStream.subscribe((m) => a.push(m.type));
    eventStream.subscribe((m) => b.push(m.type));
    const es = FakeEventSource.instances[0];
    es.emit("zone_event", { event_id: "e1" });
    expect(a).toEqual(["zone_event"]);
    expect(b).toEqual(["zone_event"]);
  });

  it("drops duplicate events by id", () => {
    eventStream.connect("http://x/stream");
    const got: string[] = [];
    eventStream.subscribe((m) =>
      got.push(String(m.data.event_id ?? m.data.incident_id)),
    );
    const es = FakeEventSource.instances[0];
    es.emit("zone_event", { event_id: "e1" });
    es.emit("zone_event", { event_id: "e1" }); // duplicate
    es.emit("incident", { incident_id: "e1" }); // different type+id space
    es.emit("incident", { incident_id: "e1" }); // duplicate
    expect(got).toEqual(["e1", "e1"]);
  });

  it("broadcasts connection state", () => {
    const states: string[] = [];
    const release = eventStream.onState((s) => states.push(s));
    eventStream.connect("http://x/stream");
    const es = FakeEventSource.instances[0];
    es.open();
    es.fail();
    release();
    expect(states).toContain("connecting");
    expect(states).toContain("open");
    expect(states).toContain("error");
  });

  it("ignores malformed JSON payloads", () => {
    eventStream.connect("http://x/stream");
    const got: unknown[] = [];
    eventStream.subscribe((m) => got.push(m));
    const es = FakeEventSource.instances[0];
    es.listeners.get("zone_event")?.[0]({ data: "not-json{" } as MessageEvent);
    expect(got).toEqual([]);
  });
});
