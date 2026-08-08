const fs = require('fs');
const path = require('path');
const express = require('express');
const { defineConfig, loadEnv } = require('vite');
const react = require('@vitejs/plugin-react').default;

function visualEditsPlugin(enabled) {
  if (!enabled) return null;
  return {
    name: 'eduflow-visual-edits',
    apply: 'serve',
    configureServer(server) {
      const app = express();
      const setupDevServer = require('@emergentbase/visual-edits/server').default;
      const config = setupDevServer({});
      config.setupMiddlewares([], { app });
      const overlay = require.resolve('@emergentbase/visual-edits/visual-edit-overlay');

      server.middlewares.use((req, res, next) => {
        if (req.url === '/visual-edit-overlay.js') {
          res.setHeader('Content-Type', 'text/javascript; charset=utf-8');
          fs.createReadStream(overlay).pipe(res);
          return;
        }
        if (req.url === '/ping' || req.url === '/edit-file') {
          app(req, res, next);
          return;
        }
        next();
      });
    },
    transformIndexHtml() {
      return [{
        tag: 'script',
        injectTo: 'head',
        children: `if(window.self!==window.top){var s=document.createElement('script');s.src='/visual-edit-overlay.js';document.head.appendChild(s);}`,
      }];
    },
  };
}

function healthPlugin(enabled) {
  if (!enabled) return null;
  const startedAt = Date.now();
  return {
    name: 'eduflow-dev-health',
    apply: 'serve',
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        if (!req.url.startsWith('/health')) return next();
        res.statusCode = 200;
        if (req.url === '/health/simple') {
          res.setHeader('Content-Type', 'text/plain; charset=utf-8');
          res.end('OK');
          return;
        }
        res.setHeader('Content-Type', 'application/json; charset=utf-8');
        res.end(JSON.stringify({
          status: 'healthy',
          ready: true,
          bundler: 'vite',
          timestamp: new Date().toISOString(),
          uptime_seconds: Math.floor((Date.now() - startedAt) / 1000),
        }));
      });
    },
  };
}

module.exports = defineConfig(({ mode, command }) => {
  const env = { ...loadEnv(mode, process.cwd(), ''), ...process.env };
  const isDev = command === 'serve';
  const backendUrl = env.VITE_BACKEND_URL || env.REACT_APP_BACKEND_URL || '';
  const proxyTarget = env.DEV_API_TARGET;
  let visualBabelPlugin = null;
  if (isDev) {
    try {
      visualBabelPlugin = require('@emergentbase/visual-edits/babel-plugin').default;
    } catch (error) {
      console.warn(`[visual-edits] disabled: ${error.message}`);
    }
  }

  const proxy = proxyTarget ? {
    '/api': {
      target: proxyTarget,
      changeOrigin: true,
      secure: true,
      xfwd: false,
      cookieDomainRewrite: 'localhost',
      timeout: 0,
      proxyTimeout: 0,
      configure(proxyServer) {
        proxyServer.on('proxyReq', (proxyReq, req) => {
          for (const header of [
            'referer', 'x-forwarded-host', 'x-forwarded-proto', 'x-forwarded-port',
            'x-forwarded-for', 'sec-fetch-dest', 'sec-fetch-mode', 'sec-fetch-site',
            'sec-fetch-user', 'sec-ch-ua', 'sec-ch-ua-mobile', 'sec-ch-ua-platform',
            'baggage', 'sentry-trace',
          ]) proxyReq.removeHeader(header);
          const rawCookie = req.headers.cookie;
          if (rawCookie) {
            const kept = rawCookie.split(';').map((item) => item.trim())
              .filter((item) => item.startsWith('eduflow_refresh_token='));
            if (kept.length) proxyReq.setHeader('cookie', kept.join('; '));
            else proxyReq.removeHeader('cookie');
          }
          proxyReq.setHeader('origin', proxyTarget);
          proxyReq.setHeader('referer', `${proxyTarget}/`);
        });
      },
    },
  } : undefined;

  return {
    plugins: [
      react({ babel: { plugins: visualBabelPlugin ? [visualBabelPlugin] : [] } }),
      visualEditsPlugin(isDev && Boolean(visualBabelPlugin)),
      healthPlugin(isDev && env.ENABLE_HEALTH_CHECK === 'true'),
    ].filter(Boolean),
    resolve: { alias: { '@': path.resolve(__dirname, 'src') } },
    esbuild: {
      loader: 'jsx',
      include: /src\/.*\.jsx?$/,
      exclude: [],
    },
    optimizeDeps: {
      esbuildOptions: { loader: { '.js': 'jsx' } },
    },
    define: {
      'process.env.REACT_APP_BACKEND_URL': JSON.stringify(backendUrl),
      'process.env.NODE_ENV': JSON.stringify(isDev ? 'development' : 'production'),
      'process.env.PUBLIC_URL': JSON.stringify(env.PUBLIC_URL || ''),
    },
    server: {
      host: '0.0.0.0',
      port: 3000,
      proxy,
      watch: { ignored: ['**/build/**', '**/coverage/**'] },
    },
    build: {
      outDir: 'build',
      sourcemap: true,
      // The only chunk near this ceiling is html2pdf and it is loaded on demand
      // after a person clicks PDF export. The initial application entry stays
      // below 600 kB and monitoring is also deferred until after first render.
      chunkSizeWarningLimit: 1000,
    },
  };
});
