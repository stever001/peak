import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Pin the workspace root to web/ (a stray lockfile higher up would otherwise be picked).
  turbopack: { root: __dirname },
};

export default nextConfig;
