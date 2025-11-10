const nextConfig = {
  reactStrictMode: false,
  distDir: ".next-build",
  

  // Rewrites for development - proxy API and font requests to FastAPI backend
  async rewrites() {
    return [
      {
        source: '/api/v1/auth',
        destination: 'http://localhost:9204/auth/',
      },
      {
        source: '/api/v1/ppt/:path*',
        destination: 'http://localhost:9204/api/v1/ppt/:path*',
      },
      {
        source: '/api/v1/auth/:path*',
        destination: 'http://localhost:9204/auth/:path*',
      },
      {
        source: '/static/:path*',
        destination: 'http://localhost:9204/static/:path*',
      },
      {
        source: '/app_data/:path*',
        destination: 'http://localhost:9204/app_data/:path*',
      }
    ];
  },

  images: {
    remotePatterns: [
      {
        protocol: "https",
        hostname: "pub-7c765f3726084c52bcd5d180d51f1255.r2.dev",
      },
      {
        protocol: "https",
        hostname: "pptgen-public.ap-south-1.amazonaws.com",
      },
      {
        protocol: "https",
        hostname: "pptgen-public.s3.ap-south-1.amazonaws.com",
      },
      {
        protocol: "https",
        hostname: "img.icons8.com",
      },
      {
        protocol: "https",
        hostname: "present-for-me.s3.amazonaws.com",
      },
      {
        protocol: "https",
        hostname: "yefhrkuqbjcblofdcpnr.supabase.co",
      },
      {
        protocol: "https",
        hostname: "images.unsplash.com",
      },
      {
        protocol: "https",
        hostname: "picsum.photos",
      },
      {
        protocol: "https",
        hostname: "unsplash.com",
      },
    ],
  },
  
};

export default nextConfig