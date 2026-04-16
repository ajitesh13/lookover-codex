import type { NextConfig } from "next";
import path from "node:path";

const apiBaseUrl =
  process.env.LOOKOVER_API_BASE_URL?.trim() ||
  process.env.NEXT_PUBLIC_API_BASE_URL?.trim() ||
  process.env.NEXT_PUBLIC_LOOKOVER_API_BASE_URL?.trim() ||
  "http://localhost:8080";

const nextConfig: NextConfig = {
  turbopack: {
    root: path.join(__dirname),
  },
  async rewrites() {
    return [
      {
        source: "/v1/:path*",
        destination: `${apiBaseUrl}/v1/:path*`,
      },
    ];
  },
};

export default nextConfig;
