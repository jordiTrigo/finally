import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { appendPoints, usePriceStream } from "./usePriceStream";
import type { PriceUpdate } from "@/lib/types";

function update(ticker: string, price: number, timestamp: string): PriceUpdate {
  return { ticker, price, previous_price: price, timestamp, direction: "up" };
}

/** Minimal stand-in for the browser EventSource, which jsdom does not provide. */
class FakeEventSource {
  static readonly CONNECTING = 0;
  static readonly OPEN = 1;
  static readonly CLOSED = 2;
  static last: FakeEventSource | null = null;

  readyState = FakeEventSource.CONNECTING;
  closed = false;
  onopen: (() => void) | null = null;
  onerror: (() => void) | null = null;
  onmessage: ((event: MessageEvent<string>) => void) | null = null;

  constructor(readonly url: string) {
    FakeEventSource.last = this;
  }

  open() {
    this.readyState = FakeEventSource.OPEN;
    this.onopen?.();
  }

  emit(payload: PriceUpdate) {
    this.onmessage?.({ data: JSON.stringify(payload) } as MessageEvent<string>);
  }

  fail(readyState: number) {
    this.readyState = readyState;
    this.onerror?.();
  }

  close() {
    this.closed = true;
    this.readyState = FakeEventSource.CLOSED;
  }
}

describe("appendPoints", () => {
  it("starts a series for a ticker it has not seen", () => {
    const result = appendPoints({}, [
      update("AAPL", 190, "2026-07-28T12:00:00+00:00"),
    ]);

    expect(result.AAPL).toEqual([{ time: Date.parse("2026-07-28T12:00:00Z") / 1000, value: 190 }]);
  });

  it("keeps one sample per second so times stay unique", () => {
    const result = appendPoints({}, [
      update("AAPL", 190, "2026-07-28T12:00:00.100+00:00"),
      update("AAPL", 191, "2026-07-28T12:00:00.600+00:00"),
    ]);

    expect(result.AAPL).toHaveLength(1);
    expect(result.AAPL[0].value).toBe(191);
  });

  it("appends across second boundaries in ascending order", () => {
    const result = appendPoints({}, [
      update("AAPL", 190, "2026-07-28T12:00:00+00:00"),
      update("AAPL", 191, "2026-07-28T12:00:01+00:00"),
    ]);

    expect(result.AAPL.map((point) => point.value)).toEqual([190, 191]);
    expect(result.AAPL[1].time).toBeGreaterThan(result.AAPL[0].time);
  });

  it("keeps series separate per ticker", () => {
    const result = appendPoints({}, [
      update("AAPL", 190, "2026-07-28T12:00:00+00:00"),
      update("MSFT", 400, "2026-07-28T12:00:00+00:00"),
    ]);

    expect(Object.keys(result).sort()).toEqual(["AAPL", "MSFT"]);
  });

  it("does not mutate the previous history object", () => {
    const before = {};
    appendPoints(before, [update("AAPL", 190, "2026-07-28T12:00:00+00:00")]);

    expect(before).toEqual({});
  });
});

describe("usePriceStream", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.stubGlobal("EventSource", FakeEventSource);
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    FakeEventSource.last = null;
  });

  function source() {
    return FakeEventSource.last!;
  }

  it("subscribes to the price stream", () => {
    renderHook(() => usePriceStream());

    expect(source().url).toBe("/api/stream/prices");
  });

  it("reports connected once the stream opens", () => {
    const { result } = renderHook(() => usePriceStream());
    expect(result.current.status).toBe("connecting");

    act(() => source().open());

    expect(result.current.status).toBe("connected");
  });

  it("batches events into prices and history on flush", () => {
    const { result } = renderHook(() => usePriceStream());

    act(() => {
      source().open();
      source().emit(update("AAPL", 190, "2026-07-28T12:00:00+00:00"));
      source().emit(update("MSFT", 400, "2026-07-28T12:00:00+00:00"));
    });
    expect(result.current.prices).toEqual({});

    act(() => vi.advanceTimersByTime(200));

    expect(result.current.prices.AAPL.price).toBe(190);
    expect(result.current.prices.MSFT.price).toBe(400);
    expect(result.current.history.AAPL).toHaveLength(1);
  });

  it("reports reconnecting while EventSource is still retrying", () => {
    const { result } = renderHook(() => usePriceStream());

    act(() => source().fail(FakeEventSource.CONNECTING));

    expect(result.current.status).toBe("reconnecting");
  });

  it("reports disconnected once EventSource gives up", () => {
    const { result } = renderHook(() => usePriceStream());

    act(() => source().fail(FakeEventSource.CLOSED));

    expect(result.current.status).toBe("disconnected");
  });

  it("reopens the stream itself after a fatal close, which EventSource never retries", () => {
    renderHook(() => usePriceStream());
    const first = source();

    act(() => first.fail(FakeEventSource.CLOSED));
    expect(source()).toBe(first);

    act(() => vi.advanceTimersByTime(2500));

    expect(source()).not.toBe(first);
  });

  it("keeps retrying while the server stays down", () => {
    renderHook(() => usePriceStream());
    const seen = new Set([source()]);

    for (let attempt = 0; attempt < 3; attempt += 1) {
      act(() => source().fail(FakeEventSource.CLOSED));
      act(() => vi.advanceTimersByTime(2500));
      seen.add(source());
    }

    expect(seen.size).toBe(4);
  });

  it("reports disconnected when the stream goes quiet", () => {
    const { result } = renderHook(() => usePriceStream());

    act(() => {
      source().open();
      source().emit(update("AAPL", 190, "2026-07-28T12:00:00+00:00"));
    });
    act(() => vi.advanceTimersByTime(200));
    expect(result.current.status).toBe("connected");

    act(() => vi.advanceTimersByTime(4000));

    expect(result.current.status).toBe("disconnected");
  });

  it("opens a fresh stream when a still-open connection goes quiet", () => {
    renderHook(() => usePriceStream());
    const stalled = source();
    act(() => stalled.open());

    act(() => vi.advanceTimersByTime(4000));

    expect(stalled.closed).toBe(true);
    expect(source()).not.toBe(stalled);
    expect(source().closed).toBe(false);
  });

  it("does not keep reconnecting while the stream is down", () => {
    const { result } = renderHook(() => usePriceStream());
    const first = source();
    act(() => first.fail(FakeEventSource.CONNECTING));

    act(() => vi.advanceTimersByTime(10_000));

    expect(source()).toBe(first);
    expect(result.current.status).toBe("reconnecting");
  });

  it("recovers to connected once data flows again", () => {
    const { result } = renderHook(() => usePriceStream());
    act(() => source().open());
    act(() => vi.advanceTimersByTime(4000));
    expect(result.current.status).toBe("disconnected");

    act(() => {
      source().open();
      source().emit(update("AAPL", 190, "2026-07-28T12:00:00+00:00"));
    });
    act(() => vi.advanceTimersByTime(200));

    expect(result.current.status).toBe("connected");
    expect(result.current.prices.AAPL.price).toBe(190);
  });

  it("closes the stream on unmount", () => {
    const { unmount } = renderHook(() => usePriceStream());
    const stream = source();

    unmount();

    expect(stream.closed).toBe(true);
  });
});
