/** @type {import('next').NextConfig} */
const nextConfig = {
  eslint: {
    ignoreDuringBuilds: true,
  },
  typescript: {
    ignoreBuildErrors: true,
  },
  async redirects() {
    return [
      {
        // obrigatório: sem trailing slash os links relativos do consulta
        // (style.css, app.js) resolvem contra a raiz do domínio -> 404 sem CSS
        source: "/consulta",
        destination: "/consulta/",
        permanent: true,
      },
    ];
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