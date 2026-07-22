/**
 * LOCAL DEV ONLY — never bundled into a production build.
 *
 * The deployed backend only allows browser requests from the real site's
 * origin, so a page served from http://localhost:3000 gets blocked by CORS.
 * Rather than widening the production CORS allow-list (a prod change, and a
 * permanent hole for a temporary need), the dev server proxies /api itself:
 * the browser only ever talks to localhost, so there is no cross-origin
 * request to block. Server-to-server calls are not subject to CORS.
 *
 * Requires REACT_APP_BACKEND_URL to be EMPTY in .env so api.js builds
 * relative URLs ("/api/..."). Target comes from DEV_API_TARGET.
 *
 * CRA/craco picks this file up automatically — no wiring needed.
 */
const { createProxyMiddleware } = require('http-proxy-middleware');

const target = process.env.DEV_API_TARGET;

module.exports = function (app) {
  if (!target) {
    console.warn('[dev-proxy] DEV_API_TARGET not set — /api is NOT proxied.');
    return;
  }
  console.log(`[dev-proxy] /api -> ${target}`);

  app.use(
    '/api',
    createProxyMiddleware({
      target,
      changeOrigin: true,          // send the backend its own Host, not localhost
      secure: true,
      // xfwd would add "X-Forwarded-Host: localhost:3000". AWS WAF in front of
      // this backend blocks requests that advertise localhost, so leave it off.
      xfwd: false,
      // Auth refresh uses an httpOnly cookie. The backend scopes it to its own
      // domain, which the browser would reject for localhost — rewrite it.
      cookieDomainRewrite: 'localhost',
      // Chat replies stream over SSE; buffering would make them arrive all at
      // once at the end of the turn instead of token by token.
      compress: false,
      proxyTimeout: 0,
      timeout: 0,
      onProxyReq(proxyReq, req) {
        // Strip headers that reveal this is a localhost dev machine, plus
        // tracing headers the backend has no use for.
        for (const h of [
          'referer', 'x-forwarded-host', 'x-forwarded-proto',
          'x-forwarded-port', 'x-forwarded-for',
          'sec-fetch-dest', 'sec-fetch-mode', 'sec-fetch-site', 'sec-fetch-user',
          'sec-ch-ua', 'sec-ch-ua-mobile', 'sec-ch-ua-platform',
          'baggage', 'sentry-trace',
        ]) {
          proxyReq.removeHeader(h);
        }

        // COOKIE ALLOW-LIST — this is the important one.
        //
        // In production the page (amplifyapp.com) and the API (cloudfront.net)
        // are different sites, so the analytics cookies set on the page are
        // never sent to the API. In local dev everything is on localhost, so
        // the browser attaches ALL of them — including PostHog's `ph_phc_*`,
        // whose value is URL-encoded JSON. AWS WAF's managed rules read that
        // as an injection attempt and return a 403 "Request blocked" before
        // the request ever reaches the backend.
        //
        // Forwarding only the auth cookie both fixes the 403 and keeps local
        // dev closer to how production actually behaves.
        const KEEP = ['eduflow_refresh_token'];
        const raw = req.headers.cookie;
        if (raw) {
          const kept = raw
            .split(';')
            .map((c) => c.trim())
            .filter((c) => KEEP.some((k) => c.startsWith(k + '=')));
          if (kept.length) proxyReq.setHeader('cookie', kept.join('; '));
          else proxyReq.removeHeader('cookie');
        }

        // Present the deployed site's origin so any origin check upstream passes.
        proxyReq.setHeader('origin', target);
        proxyReq.setHeader('referer', target + '/');
        if (process.env.DEV_PROXY_DEBUG === 'true') {
          console.log('[dev-proxy] ->', req.method, req.url, JSON.stringify(proxyReq.getHeaders()));
        }
      },
      onProxyRes(proxyRes, req) {
        if (process.env.DEV_PROXY_DEBUG === 'true') {
          console.log('[dev-proxy] <-', proxyRes.statusCode, req.url);
          if (proxyRes.statusCode >= 400) {
            let body = '';
            proxyRes.on('data', (c) => { if (body.length < 4000) body += c.toString(); });
            proxyRes.on('end', () => {
              console.log('[dev-proxy] BODY>>>', body.replace(/\s+/g, ' ').slice(0, 1200), '<<<END');
            });
          }
        }
      },
      onError(err, req, res) {
        console.error(`[dev-proxy] ${req.method} ${req.url} failed:`, err.message);
        if (!res.headersSent) res.writeHead(502, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ detail: `Dev proxy error: ${err.message}` }));
      },
    })
  );
};
