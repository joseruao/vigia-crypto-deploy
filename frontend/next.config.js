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
        // Azure App Service (EU, italynorth) — o Railway ficou sem créditos a 2026-09-10
        destination: "https://vigia-consulta.azurewebsites.net/:path*",
      },
    ];
  },
}

module.exports = nextConfig