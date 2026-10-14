import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';

// Vite の設定。オフライン家庭内サーバー向けに、ローカルでバンドルした成果物を
// frontend/dist へ出力する。runtime は docker-compose の bind-mount（./:/app）で
// frontend/dist をサーブするため、出力先を dist に固定する。
export default defineConfig({
  plugins: [vue()],
  build: {
    // 出力先を frontend/dist に固定する（CommonJS / StaticFiles で直接サーブするため）。
    outDir: 'dist',
    emptyOutDir: true,
    // 圧縮するとファイル名が変わるため、静的サーブを安定させる。
    minify: 'esbuild',
    sourcemap: false,
  },
});
