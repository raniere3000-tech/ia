import { defineConfig, type Plugin } from 'vite';
import react from '@vitejs/plugin-react';
import { copyFileSync, mkdirSync } from 'node:fs';
import { resolve } from 'node:path';

// Copia o motor de detecção de rosto (MediaPipe) para o site, sem depender de CDN.
const mediapipe = (): Plugin => ({
  name: 'copiar-mediapipe',
  closeBundle(){
    const de = resolve(__dirname,'node_modules/@mediapipe/tasks-vision/wasm'), para = resolve(__dirname,'dist/mediapipe');
    mkdirSync(para,{recursive:true});
    for(const f of ['vision_wasm_internal.js','vision_wasm_internal.wasm']) copyFileSync(resolve(de,f),resolve(para,f));
  },
});

export default defineConfig({plugins:[react(),mediapipe()],base:'/ia/',worker:{format:'es'}});
