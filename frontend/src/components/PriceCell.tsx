"use client";

import { useEffect, useRef, useState } from "react";
import { formatPrice } from "@/lib/format";

/** How long the flash colour holds before the CSS transition fades it out. */
export const FLASH_MS = 300;

interface PriceCellProps {
  price: number | null;
  className?: string;
  testId?: string;
}

/**
 * A price that flashes green on an uptick and red on a downtick.
 *
 * The direction is derived from the rendered price rather than the stream's
 * `direction` field, so the same cell works for positions and quotes alike.
 */
export function PriceCell({ price, className = "", testId }: PriceCellProps) {
  const [flash, setFlash] = useState<"up" | "down" | null>(null);
  const previous = useRef(price);

  useEffect(() => {
    const before = previous.current;
    previous.current = price;

    if (price === null || before === null || price === before) return;

    setFlash(price > before ? "up" : "down");
    const timer = setTimeout(() => setFlash(null), FLASH_MS);
    return () => clearTimeout(timer);
  }, [price]);

  return (
    <span
      data-testid={testId}
      className={`price-cell tabular px-1 ${flash ? `flash-${flash}` : ""} ${className}`}
    >
      {formatPrice(price)}
    </span>
  );
}
