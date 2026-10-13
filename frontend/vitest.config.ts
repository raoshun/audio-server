// Vite の設定（Vitest 実行環境）。
// 既存の vite.config.js を拡張し、Vue プラグインと jsdom 環境を有効化する。
// frontend/tests 配下の .spec.ts を vitest が検出して実行する。
import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';

export default defineConfig({
  plugins: [vue()],
  test: {
    // Vue SFC を正しくコンパイルするため、jsdom を実行環境に指定する。
    environment: 'jsdom',
    globals: true,
    // 単一の実行モード（watch ではなく、CI で利用する）。
    run: true,
    // jsdom の未実装メディア API を no-op にするセットアップ。
    setupFiles: ['tests/setup.ts'],
    // テスト対象のファイルパターン（既存の test_* と整合させる）。
    include: ['tests/**/*.spec.ts'],
  },
});
