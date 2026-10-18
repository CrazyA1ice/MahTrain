import {defineConfig} from 'vite';
import {fileURLToPath} from 'node:url';
export default defineConfig({
  root:fileURLToPath(new URL('./public/',import.meta.url)),
  base:'/3d/',
  publicDir:false,
  define:{__DEV__:JSON.stringify(false)},
  build:{
    outDir:fileURLToPath(new URL('./dist/',import.meta.url)),
    emptyOutDir:true,
    rollupOptions:{input:{game:fileURLToPath(new URL('./public/game.html',import.meta.url))}},
    chunkSizeWarningLimit:1500,
  },
  server:{port:5176,host:'127.0.0.1',
    proxy:{'/api':'http://127.0.0.1:8765'}},
});
