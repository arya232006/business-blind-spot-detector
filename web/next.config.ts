import type { NextConfig } from "next";

// The dashboard is a client-side app: every page fetches from the FastAPI backend in the browser,
// so none of the experimental caching/prefetching modes are needed.
const nextConfig: NextConfig = {
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
