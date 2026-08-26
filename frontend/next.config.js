/** @type {import('next').NextConfig} */
const nextConfig = {
  eslint: {
    ignoreDuringBuilds: true,
  },
  typescript: {
    ignoreBuildErrors: true,
  },
  async rewrites() {
    return [
      {
        source: "/consulta/:path*",
        destination: "https://consulta-production-354e.up.railway.app/:path*",
      },
    ];
  },
}

module.exports = nextConfig