interface SparklineProps {
  values: number[];
  width?: number;
  height?: number;
  testId?: string;
}

/**
 * A hand-rolled SVG polyline. Charting libraries are heavy for a 20px trace
 * repeated once per watchlist row and redrawn several times a second.
 */
export function Sparkline({
  values,
  width = 96,
  height = 20,
  testId,
}: SparklineProps) {
  if (values.length < 2) {
    return (
      <svg
        data-testid={testId}
        width={width}
        height={height}
        aria-hidden="true"
        className="block"
      />
    );
  }

  const low = Math.min(...values);
  const high = Math.max(...values);
  const span = high - low || 1;
  const step = width / (values.length - 1);

  const points = values
    .map(
      (value, index) =>
        `${(index * step).toFixed(1)},${(height - ((value - low) / span) * height).toFixed(1)}`,
    )
    .join(" ");

  const rising = values[values.length - 1] >= values[0];

  return (
    <svg
      data-testid={testId}
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      aria-hidden="true"
      className="block"
    >
      <polyline
        fill="none"
        stroke={rising ? "#26a65b" : "#e0453e"}
        strokeWidth="1.25"
        points={points}
      />
    </svg>
  );
}
