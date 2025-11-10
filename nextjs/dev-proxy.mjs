import { createProxyMiddleware } from 'http-proxy-middleware';
import http from 'http';
// import { parse } from 'url';
import next from 'next';

const dev = process.env.NODE_ENV !== 'production';
const port = 9205; // 您前端应用的端口
const backendTarget = 'http://localhost:9204'; // 您后端服务的地址
const app = next({ dev });
const handle = app.getRequestHandler();

// 通用的代理配置，包含加长的超时时间
const proxyOptions = {
  target: backendTarget,
  changeOrigin: true,
  proxyTimeout: 300000, // 5 分钟
  timeout: 300000, // 5 分钟
  onProxyReq: (proxyReq, req, res) => {
    proxyReq.setHeader('Origin', backendTarget);
  },
  onError: (err, req, res) => {
    console.error(`Proxy error for ${req.url}:`, err);
    if (res && !res.headersSent) {
      res.writeHead(500, { 'Content-Type': 'text/plain' });
      res.end('Proxy error: ' + err.message);
    }
  },
};

// 根据 next.config.mjs 的规则创建不同的代理实例
// 请注意，数组顺序很重要，将最具体的路径放在前面
const proxyMappings = [
  // 处理 /api/v1/auth* -> /auth* 的路径重写
  { 
    path: '/api/v1/auth', 
    proxy: createProxyMiddleware({ 
      ...proxyOptions, 
      pathRewrite: { '^/api/v1/auth': '/auth' },
    }) 
  },
  // 处理其他 /api 路径，不重写
  { path: '/api/v1/ppt', proxy: createProxyMiddleware(proxyOptions) },
  { path: '/static', proxy: createProxyMiddleware(proxyOptions) },
  { path: '/app_data', proxy: createProxyMiddleware(proxyOptions) }
];

app.prepare().then(() => {
  http.createServer((req, res) => {
    // Use the modern URL API to safely get the pathname.
    // A base URL is required for the constructor, we can create it from request headers.
    const pathname = new URL(req.url, `http://${req.headers.host}`).pathname;

    // Find a matching proxy rule
    for (const mapping of proxyMappings) {
      if (pathname.startsWith(mapping.path)) {
        return mapping.proxy(req, res);
      }
    }

    // If no proxy matches, let Next.js handle it.
    // We call handle() without the parsed URL object. 
    // This lets Next.js handle the parsing internally and avoids the deprecated function.
    return handle(req, res);

  }).listen(port, (err) => {
    if (err) throw err;
    console.log(`> Ready on http://localhost:${port}`);
  });
});