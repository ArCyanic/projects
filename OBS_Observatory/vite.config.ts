import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import path from 'path'

import AutoImport from "unplugin-auto-import/vite";
import Components from "unplugin-vue-components/vite";
import { ElementPlusResolver } from "unplugin-vue-components/resolvers";

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [
    vue(),
    AutoImport({
      resolvers: [ElementPlusResolver()],
    }),
    Components({
      resolvers: [ElementPlusResolver()],
    }),
  ],
  server: {
    open: true, //是否自动弹出浏览器页面
    host: "localhost",
    port: 3000,
    proxy: {
      cors: "true",
      "/api": {
        target: "http://1.15.121.222:8080", //API Server
        ws: true, 
        changeOrigin: true, 
        rewrite: (path) => path.replace(/^\/api/, ""),
        secure: false,
      },
    },
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  }
});
