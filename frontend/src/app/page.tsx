"use client";

import dynamic from "next/dynamic";

/**
 * The terminal is browser-only: it opens an SSE connection and creates chart
 * canvases on mount, neither of which belongs in the static export prerender.
 */
const Terminal = dynamic(
  () => import("@/components/Terminal").then((module) => module.Terminal),
  {
    ssr: false,
    loading: () => (
      <p className="flex h-full items-center justify-center text-terminal-muted">
        Loading FinAlly...
      </p>
    ),
  },
);

export default function Page() {
  return <Terminal />;
}
