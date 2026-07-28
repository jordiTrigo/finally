import type { NextConfig } from "next";

/**
 * Static export: `next build` writes a self-contained site to `frontend/out`,
 * which FastAPI serves from the same origin as `/api/*` (so no CORS is needed).
 */
const nextConfig: NextConfig = {
  output: "export",
  images: { unoptimized: true },
};

export default nextConfig;
