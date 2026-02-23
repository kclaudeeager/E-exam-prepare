/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  // Allow backend API calls in Docker network
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${process.env.BACKEND_INTERNAL_URL || "http://localhost:8000"}/api/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
