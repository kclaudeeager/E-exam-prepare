/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  // Prevent Next.js from redirecting trailing-slash URLs (308).
  // FastAPI expects trailing slashes on list endpoints; without this,
  // Next.js strips the slash, FastAPI 307-redirects with the internal
  // Docker hostname (backend:8000), and the browser can't resolve it.
  skipTrailingSlashRedirect: true,
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
