import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// https://vitejs.dev/config/
export default defineConfig({
    plugins: [react()],
    build: {
        outDir: "../dist/static",
        emptyOutDir: true,
        sourcemap: true,
        // Optimize chunk splitting to reduce bundle size
        chunkSizeWarningLimit: 800,
        rollupOptions: {
            output: {
                manualChunks(id) {
                    // Split vendor chunks for better caching
                    if (id.includes('node_modules')) {
                        // Keep React and Fluent together to avoid circular deps
                        if (id.includes('react') || id.includes('@fluentui')) {
                            return 'vendor-ui';
                        }
                        if (id.includes('lodash')) {
                            return 'vendor-utils';
                        }
                    }
                }
            }
        },
        // Use esbuild for faster minification
        minify: 'esbuild',
        target: 'es2020'
    },
    server: {
        host: true,
        proxy: {
            "/api": {
                target: "http://127.0.0.1:5050",
                changeOrigin: true,
                secure: false
            }
        }
    },
    // Pre-bundle deps for faster dev server startup
    optimizeDeps: {
        include: ['react', 'react-dom', '@fluentui/react', 'lodash']
    },
    // Enable caching for faster rebuilds
    cacheDir: 'node_modules/.vite'
});
