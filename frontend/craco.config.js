// craco.config.js
const path = require("path");
require("dotenv").config();

// Check if we're in development/preview mode (not production build)
// Craco sets NODE_ENV=development for start, NODE_ENV=production for build
const isDevServer = process.env.NODE_ENV !== "production";

// Environment variable overrides
const config = {
  enableHealthCheck: process.env.ENABLE_HEALTH_CHECK === "true",
};

// Conditionally load health check modules only if enabled
let WebpackHealthPlugin;
let setupHealthEndpoints;
let healthPluginInstance;

if (config.enableHealthCheck) {
  WebpackHealthPlugin = require("./plugins/health-check/webpack-health-plugin");
  setupHealthEndpoints = require("./plugins/health-check/health-endpoints");
  healthPluginInstance = new WebpackHealthPlugin();
}

let webpackConfig = {
  jest: {
    configure: {
      moduleNameMapper: {
        '^react-router-dom$': '<rootDir>/node_modules/react-router-dom/dist/index.js',
        '^react-router$': '<rootDir>/node_modules/react-router/dist/development/index.js',
        '^react-router/dom$': '<rootDir>/node_modules/react-router/dist/development/dom-export.js',
      },
    },
  },
  eslint: {
    configure: {
      extends: ["plugin:react-hooks/recommended"],
      rules: {
        "react-hooks/rules-of-hooks": "error",
        // T11 / NEW-09 (2026-08-04). This was "warn", and 48 of them had piled up:
        // effects that never re-ran when their inputs changed, which is what "it
        // shows old data until I refresh" actually was. All 48 were cleared, and
        // the rule is now an ERROR on the production build so the count cannot
        // regrow — `npx craco build` fails outright on a new one.
        //
        // Still only a warning under `craco start`, so a half-written effect does
        // not block the dev server mid-edit.
        //
        // If a dependency is genuinely meant to be left out, do NOT relax this back
        // to "warn": put a scoped `// eslint-disable-next-line
        // react-hooks/exhaustive-deps` on the line, with a comment above it saying
        // why. The pattern is set in `src/components/tools/ToolPage.js`
        // (`useToolData`), the one place in the app where it is correct.
        "react-hooks/exhaustive-deps": isDevServer ? "warn" : "error",
      },
    },
  },
  webpack: {
    alias: {
      '@': path.resolve(__dirname, 'src'),
    },
    configure: (webpackConfig) => {

      // Add ignored patterns to reduce watched directories
        webpackConfig.watchOptions = {
          ...webpackConfig.watchOptions,
          ignored: [
            '**/node_modules/**',
            '**/.git/**',
            '**/build/**',
            '**/dist/**',
            '**/coverage/**',
            '**/public/**',
        ],
      };

      // Stop hunting for source maps inside other people's packages.
      //
      // `html2pdf.js` inlines a few libraries into its bundle and leaves their
      // `//# sourceMappingURL=…` comments behind, pointing at map files it never
      // ships (SVGPathData.module.js.map, performance-now.js.map). Every build and
      // every dev-server start then printed "Failed to parse source map", which is
      // a packaging mistake in that library and says nothing about this codebase.
      //
      // A warning that is always there and never actionable is worse than no
      // warning: it trains people to skim past the block where a real one appears.
      //
      // Narrow on purpose. Source maps for OUR code are untouched, so debugging
      // `src/` is exactly as it was; only `node_modules` is skipped.
      const sourceMapRule = (webpackConfig.module?.rules || []).find(
        (rule) => rule && rule.enforce === 'pre' && String(rule.loader || '').includes('source-map-loader'),
      );
      if (sourceMapRule) {
        sourceMapRule.exclude = [
          ...(Array.isArray(sourceMapRule.exclude) ? sourceMapRule.exclude : sourceMapRule.exclude ? [sourceMapRule.exclude] : []),
          /node_modules/,
        ];
      }

      // Add health check plugin to webpack if enabled
      if (config.enableHealthCheck && healthPluginInstance) {
        webpackConfig.plugins.push(healthPluginInstance);
      }
      return webpackConfig;
    },
  },
};

webpackConfig.devServer = (devServerConfig) => {
  // Add health check endpoints if enabled
  if (config.enableHealthCheck && setupHealthEndpoints && healthPluginInstance) {
    const originalSetupMiddlewares = devServerConfig.setupMiddlewares;

    devServerConfig.setupMiddlewares = (middlewares, devServer) => {
      // Call original setup if exists
      if (originalSetupMiddlewares) {
        middlewares = originalSetupMiddlewares(middlewares, devServer);
      }

      // Setup health endpoints
      setupHealthEndpoints(devServer, healthPluginInstance);

      return middlewares;
    };
  }

  return devServerConfig;
};

// Wrap with visual edits (automatically adds babel plugin, dev server, and overlay in dev mode)
if (isDevServer) {
  try {
    const { withVisualEdits } = require("@emergentbase/visual-edits/craco");
    webpackConfig = withVisualEdits(webpackConfig);
  } catch (err) {
    if (err.code === 'MODULE_NOT_FOUND' && err.message.includes('@emergentbase/visual-edits/craco')) {
      console.warn(
        "[visual-edits] @emergentbase/visual-edits not installed — visual editing disabled."
      );
    } else {
      throw err;
    }
  }
}

module.exports = webpackConfig;
