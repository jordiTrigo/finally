"use client";

import { useEffect, useRef } from "react";
import {
  AreaSeries,
  ColorType,
  CrosshairMode,
  LineSeries,
  createChart,
  type IChartApi,
  type ISeriesApi,
  type UTCTimestamp,
} from "lightweight-charts";
import type { PricePoint } from "@/hooks/usePriceStream";

interface TimeSeriesChartProps {
  points: PricePoint[];
  color: string;
  variant?: "area" | "line";
  /** Changing this refits the visible range - used when the ticker changes. */
  resetKey?: string;
  emptyMessage?: string;
  testId?: string;
}

const BASE_OPTIONS = {
  autoSize: true,
  layout: {
    background: { type: ColorType.Solid, color: "#131a23" },
    textColor: "#7d8da0",
    fontSize: 11,
    fontFamily:
      'ui-monospace, "SF Mono", "JetBrains Mono", Menlo, Consolas, monospace',
    attributionLogo: false,
  },
  grid: {
    vertLines: { color: "rgba(38, 49, 64, 0.45)" },
    horzLines: { color: "rgba(38, 49, 64, 0.45)" },
  },
  rightPriceScale: { borderColor: "#263140" },
  timeScale: {
    borderColor: "#263140",
    timeVisible: true,
    secondsVisible: true,
  },
  crosshair: { mode: CrosshairMode.Normal },
} as const;

/**
 * Lightweight Charts wrapper. The canvas is created once and fed through
 * `setData`; React never re-renders it, which is why it survives a stream
 * pushing several updates a second.
 */
export function TimeSeriesChart({
  points,
  color,
  variant = "area",
  resetKey,
  emptyMessage = "Waiting for data",
  testId,
}: TimeSeriesChartProps) {
  const container = useRef<HTMLDivElement>(null);
  const chart = useRef<IChartApi | null>(null);
  const series = useRef<ISeriesApi<"Area" | "Line"> | null>(null);
  const fittedFor = useRef<string | undefined>(undefined);

  useEffect(() => {
    if (!container.current) return;

    const instance = createChart(container.current, BASE_OPTIONS);
    series.current =
      variant === "area"
        ? instance.addSeries(AreaSeries, {
            lineColor: color,
            lineWidth: 2,
            topColor: `${color}55`,
            bottomColor: `${color}05`,
            priceLineVisible: false,
          })
        : instance.addSeries(LineSeries, {
            color,
            lineWidth: 2,
            priceLineVisible: false,
          });
    chart.current = instance;

    return () => {
      instance.remove();
      chart.current = null;
      series.current = null;
    };
  }, [color, variant]);

  useEffect(() => {
    if (!series.current) return;

    series.current.setData(
      points.map((point) => ({ time: point.time as UTCTimestamp, value: point.value })),
    );

    if (points.length > 0 && fittedFor.current !== resetKey) {
      fittedFor.current = resetKey;
      chart.current?.timeScale().fitContent();
    }
  }, [points, resetKey]);

  return (
    <div data-testid={testId} className="relative h-full w-full">
      <div ref={container} className="h-full w-full" />
      {points.length === 0 && (
        <p className="pointer-events-none absolute inset-0 flex items-center justify-center text-terminal-muted">
          {emptyMessage}
        </p>
      )}
    </div>
  );
}
