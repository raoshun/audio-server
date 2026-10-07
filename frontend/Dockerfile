# build context は frontend/ とする。runtime は docker-compose の bind-mount
# （./:/app）で frontend/dist をサーブするため、このイメージは dist を出力するだけ。
# runtime イメージのサイズを増やさない。

FROM node:20-slim

WORKDIR /app

# package.json と package-lock.json（存在する場合）を先にコピーし、依存をキャッシュする。
COPY package.json package*.json ./
RUN npm install

# ソース全体をコピーし、バンドルする。
COPY . ./

# Vite でバンドルし、frontend/dist へ出力する（vite.config.js の outDir 指定による）。
RUN npm run build

# ビルド成果物を確認するための出力（デバッグ用）。
RUN ls -la dist

# ビルド成果物（dist）を出力して終了する。
CMD ["ls", "-la", "dist"]
