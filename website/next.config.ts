import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "export",
  basePath: "/argus",
  images: {
    unoptimized: true,
  },
  allowedDevOrigins: ["192.168.1.13"],
};

export default nextConfig;
