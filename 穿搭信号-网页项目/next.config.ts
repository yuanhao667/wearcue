import type { NextConfig } from "next";

const backendUrl = (process.env.BACKEND_URL || "http://127.0.0.1:8000").replace(/\/$/, "");

const nextConfig: NextConfig = {
  poweredByHeader: false,
  output: "standalone",
  allowedDevOrigins: ["127.0.0.1"],
  rewrites() {
    return [{ source: "/icons/garments/:path*", destination: `${backendUrl}/assets/garments/:path*` }];
  },
};

export default nextConfig;
