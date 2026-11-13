import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactCompiler: true,
  // The Docker image sets this to ship a self-contained server.
  output: process.env.NEXT_OUTPUT === "standalone" ? "standalone" : undefined,
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
