// Vue 3 App のエントリーポイント。
// vite build でバンドルされ、dist/index.html へ出力される。
// runtime は frontend/dist を bind-mount でサーブするため、这里は build 専用。

import { createApp } from 'vue';
import App from './App.vue';

createApp(App).mount('#app');
