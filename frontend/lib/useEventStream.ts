"use client";

import { useEffect, useState } from "react";
import {
  eventStream,
  type ConnectionState,
  type StreamMessage,
} from "./eventStream";
import { API_URL } from "./api";

/**
 * Subscribe to the GuardX live event stream.
 * - Single shared EventSource across all mounted users (refcounted).
 * - Returns the live connection state for UI display.
 * - Cleans up on unmount: no leaks, no stale listeners.
 */
export function useEventStream(
  onMessage: (msg: StreamMessage) => void,
): ConnectionState {
  const [state, setState] = useState<ConnectionState>(eventStream.getState());

  useEffect(() => {
    const releaseConn = eventStream.connect(`${API_URL}/api/v1/events/stream`);
    const releaseState = eventStream.onState(setState);
    const releaseSub = eventStream.subscribe(onMessage);
    return () => {
      releaseSub();
      releaseState();
      releaseConn();
    };
    // onMessage must be stable (useCallback) in the caller.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return state;
}
