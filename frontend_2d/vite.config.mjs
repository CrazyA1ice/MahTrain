import {defineConfig} from 'vite';
import {fileURLToPath} from 'node:url';
export default defineConfig({
  root:fileURLToPath(new URL('./src/',import.meta.url)),
  base:'/classic/',
  publicDir:fileURLToPath(new URL('./assets/',import.meta.url)),
  build:{outDir:fileURLToPath(new URL('./dist/',import.meta.url)),
    emptyOutDir:true,rollupOptions:{input:fileURLToPath(new URL('./src/game.html',import.meta.url))}},
  server:{host:'127.0.0.1',port:5177,proxy:{'/api':'http://127.0.0.1:8765'}},
});
