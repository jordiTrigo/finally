"use client";

import { ResponsiveContainer, Treemap, type TreemapNode } from "recharts";
import { heatmapCells, heatmapColor } from "@/lib/portfolio";
import { formatPercent } from "@/lib/format";
import type { Position } from "@/lib/types";

/** Below this a rectangle has no room for a label. */
const LABEL_MIN_WIDTH = 44;
const LABEL_MIN_HEIGHT = 28;

function Cell(props: TreemapNode) {
  const { x, y, width, height, name, depth } = props;
  const pnlPercent = (props.pnlPercent as number) ?? 0;

  if (depth === 0 || width <= 0 || height <= 0) return <g />;

  return (
    <g data-testid={`heatmap-cell-${name}`}>
      <rect
        x={x}
        y={y}
        width={width}
        height={height}
        fill={heatmapColor(pnlPercent)}
        stroke="#0d1117"
        strokeWidth={2}
      />
      {width >= LABEL_MIN_WIDTH && height >= LABEL_MIN_HEIGHT && (
        <>
          <text
            x={x + 6}
            y={y + 15}
            fill="#e6edf5"
            fontSize={11}
            fontWeight={600}
            fontFamily="ui-monospace, monospace"
          >
            {name}
          </text>
          <text
            x={x + 6}
            y={y + 28}
            fill="#c9d5e1"
            fontSize={10}
            fontFamily="ui-monospace, monospace"
          >
            {formatPercent(pnlPercent)}
          </text>
        </>
      )}
    </g>
  );
}

/**
 * Positions as a treemap: area is portfolio weight, colour is P&L.
 * Recharts is used here only because Lightweight Charts has no treemap.
 */
export function PortfolioHeatmap({ positions }: { positions: Position[] }) {
  const cells = heatmapCells(positions).map((cell) => ({
    ...cell,
    name: cell.ticker,
  }));

  if (cells.length === 0) {
    return (
      <p
        data-testid="heatmap-empty"
        className="flex h-full items-center justify-center text-terminal-muted"
      >
        No positions yet
      </p>
    );
  }

  return (
    <div data-testid="portfolio-heatmap" className="h-full w-full">
      <ResponsiveContainer width="100%" height="100%">
        <Treemap
          data={cells}
          dataKey="size"
          nameKey="name"
          isAnimationActive={false}
          isUpdateAnimationActive={false}
          content={Cell}
        />
      </ResponsiveContainer>
    </div>
  );
}
