import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [vue()],
  server: {
    open: true, //是否自动弹出浏览器页面
    host: 'localhost',
    port: 3000,
    proxy: {
      cors: 'true',
      "/api": {
        target: "http://121.199.53.131:9001", //API服务器的地址
        ws: true, //代理websockets
        changeOrigin: true, // 虚拟的站点需要更管origin
        rewrite: (path) => path.replace(/^\/api/, ''),
        secure: false
      },
    },
  },
})
