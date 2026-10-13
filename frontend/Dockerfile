# build context は frontend/ とする。runtime は docker-compose の bind-mount
# （./:/app）で frontend/dist をサーブするため、このイメージは dist を出力するだけ。
# runtime イメージのサイズを増やさない。

FROM node:20-slim

WORKDIR /app

# package.json と package-lock.json を先にコピーし、依存をキャッシュする。
# lockfile 準拠で解決するため `npm ci` を使う（コミット済み lockfile と一致させる）。
# ビルドには devDependencies（vite / @vitejs/plugin-vue）も必要なため、省略しない。
COPY package.json package-lock.json ./
RUN npm ci

# ソース全体をコピーし、バンドルする。
COPY . ./

# Vite でバンドルし、frontend/dist へ出力する（vite.config.js の outDir 指定による）。
RUN npm run build

# ビルド成果物を確認するための出力（デバッグ用）。
RUN ls -la dist

# ビルド成果物（dist）を出力して終了する。
CMD ["ls", "-la", "dist"]
