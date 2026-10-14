# フロントエンドテスト用イメージ（Vitest 実行）。
# Python 環境は Docker Compose の test サービスを使うが、Node 系は frontend/ を
# build context とする専用イメージで隔離する（ホストへ npm をインストールしない）。

FROM node:20-slim

WORKDIR /app

# package.json と package-lock.json を先にコピーし、依存をキャッシュする。
# lockfile に vitest / jsdom / @vue/test-utils が登録されているため、
# `npm ci` でテスト依存が正しく解決される。
COPY package.json package-lock.json ./
RUN npm ci

# テストソース（tests/ と src/）をコピーする。
COPY . ./

# Vitest を単発実行する（watch ではなく CI 向けの single run）。
CMD ["npm", "run", "test"]
