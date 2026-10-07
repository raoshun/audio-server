<template>
  <!-- Vue 3 App のルートマウントポイント。
       runtime は frontend/dist の index.html をサーブするため、ここは build 専用。 -->
  <div id="app">
    <header>
      <h1>DWE 曲検索 &amp; 再生</h1>
    </header>
    <main>
      <!-- 検索・一覧ボタン群。Playwright テストは #query と #searchBtn に依存する。 -->
      <section class="search">
        <input
          type="text"
          id="query"
          v-model="query"
          placeholder="曲名やアーティストを入力"
        />
        <button id="searchBtn" type="button" @click="performSearch">検索</button>
        <button id="listAllBtn" type="button" @click="fetchAllTracks">全曲一覧</button>
        <button id="albumListBtn" type="button" @click="fetchAlbums">アルバム一覧</button>
      </section>

      <!-- アルバム一覧。項目をクリックすると openAlbum へ。 -->
      <section class="albums">
        <ul id="albumList">
          <li
            v-for="album in albums"
            :key="album.id"
            :data-id="album.id"
            @click="openAlbum(album.id)"
          >
            {{ `${album.title} — ${album.artist}` }}
          </li>
        </ul>
      </section>

      <!-- アルバムトラック一覧とモードボタン。初期は表示（vanilla と同様に display:none を付けない）。 -->
      <section id="albumTracksSection" :style="{ display: albumTracksVisible ? 'block' : 'none' }" class="album-tracks">
        <div class="mode-buttons">
          <button id="playSequentialBtn" type="button" class="mode-btn" @click="playAlbumSequential">順再生</button>
          <button id="playShuffleBtn" type="button" class="mode-btn" @click="playAlbumShuffle">ランダム再生</button>
        </div>
        <ul id="albumTracksList">
          <li
            v-for="track in albumTracks"
            :key="track.id"
            :data-id="track.id"
            :class="{ active: track.id === activeTrackId }"
            @click="playTrack(track.id)"
          >
            {{ track.title }}
          </li>
        </ul>
      </section>

      <!-- 検索・全曲の一覧結果。li は data-id を持ち、クリックで単体再生。 -->
      <section class="results">
        <ul id="resultList">
          <li
            v-for="item in results"
            :key="item.id"
            :data-id="item.id"
            @click="playTrack(item.id)"
          >
            {{ displayName(item) }}
          </li>
        </ul>
      </section>

      <!-- プレイヤー。初期は display:none（Playwright は .player の表示と #player の src を確認する）。 -->
      <section class="player" :style="{ display: playerVisible ? 'block' : 'none' }">
        <audio id="player" controls :src="currentSrc" @ended="onEnded"></audio>
      </section>
    </main>
  </div>
</template>

<script setup lang="ts">
// スタイルは style.css（vanilla 時代の既存スタイル）を使用し、バンドルへ取り込む。
// 表示・レイアウトは変更せず、既存のデザインをそのまま維持する。
import '../style.css';

import { ref } from 'vue';

// 再生中のトラックを保持する応答型のキュー（順再生/ランダム再生の次曲リスト）。
const queue = ref<string[]>([]);
// 再生中のトラック ID（ハイライト用）。
const activeTrackId = ref<string | null>(null);
// プレイヤー表示の切り替え。
const playerVisible = ref(false);
// アルバムトラックセクションの表示。初期は visible（vanilla と同一挙動）。
const albumTracksVisible = ref(true);
// 入力値・一覧状態。
const query = ref('');
const results = ref<Track[]>([]);
const albums = ref<Album[]>([]);
const albumTracks = ref<AlbumTrack[]>([]);
// 現在の再生元（:src 束縛用）。
const currentSrc = ref<string | null>(null);

// 型定義（既存 API 契約に基づき、変更しない）。
interface Track {
  id: string;
  title?: string;
  name?: string;
}
interface AlbumTrack extends Track {}
interface Album {
  id: string;
  title: string;
  artist: string;
}

// 表示名は title を優先し、無ければ name またはプレースホルダーを使う（vanilla と同一）。
function displayName(item: Track): string {
  return item.title ?? item.name ?? 'Unnamed track';
}

// 再生に失敗したときの警告（vanilla と同一の alert メッセージ）。
function warn(message: string): void {
  alert(message);
}

// 検索を実行する。POST /api/v1/search/music に { query } を送信し、結果を描画する。
async function performSearch(): Promise<void> {
  const trimmed = query.value.trim();
  if (!trimmed) return;
  try {
    const resp = await fetch('/api/v1/search/music', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query: trimmed }),
    });
    const data = await resp.json();
    results.value = Array.isArray(data.results) ? data.results : [];
  } catch {
    warn('検索に失敗しました');
  }
}

// 全曲一覧を取得する（GET /api/v1/tracks）。
async function fetchAllTracks(): Promise<void> {
  try {
    const resp = await fetch('/api/v1/tracks');
    const data = await resp.json();
    results.value = Array.isArray(data.results) ? data.results : [];
  } catch {
    warn('全曲一覧の取得に失敗しました');
  }
}

// アルバム一覧を取得する（GET /api/v1/albums）。
async function fetchAlbums(): Promise<void> {
  try {
    const resp = await fetch('/api/v1/albums');
    const data = await resp.json();
    albums.value = Array.isArray(data.albums) ? data.albums : [];
  } catch {
    warn('アルバム一覧の取得に失敗しました');
  }
}

// アルバムを選択すると、そのトラック一覧を取得してトラックリストを表示する。
// アルバムが開けない場合は警告し、セクションを隠す（vanilla と同一の処理）。
async function openAlbum(albumId: string): Promise<void> {
  albumTracksVisible.value = false;
  queue.value = [];
  try {
    const resp = await fetch(`/api/v1/albums/${albumId}`);
    if (!resp.ok) {
      warn('アルバムを取れませんでした');
      return;
    }
    const data = await resp.json();
    const tracks = Array.isArray(data.tracks) ? data.tracks : [];
    if (tracks.length === 0) {
      albumTracksVisible.value = false;
      return;
    }
    albumTracks.value = tracks;
    albumTracksVisible.value = true;
  } catch {
    albumTracksVisible.value = false;
    warn('アルバムを開けませんでした');
  }
}

// アルバムのトラック ID の配列を取得する（リスト順を維持）。
function albumTrackIds(): string[] {
  return albumTracks.value
    .map((t) => t.id)
    .filter((id): id is string => typeof id === 'string' && id.length > 0);
}

// アルバムのトラックを順再生する（トラックリストの先頭から順番に再生する）。
function playAlbumSequential(): void {
  queue.value = albumTrackIds();
  playNext();
}

// アルバムのトラックをランダム再生する（Fisher-Yates でシャッフル後に再生する）。
function playAlbumShuffle(): void {
  const ids = albumTrackIds();
  if (ids.length === 0) return;
  for (let i = ids.length - 1; i > 0; i -= 1) {
    const j = Math.floor(Math.random() * (i + 1));
    [ids[i], ids[j]] = [ids[j], ids[i]];
  }
  queue.value = ids;
  playNext();
}

// キューの先頭のトラックを再生する。トラックが終了したら次のトラックへ進む。
function playNext(): void {
  if (queue.value.length === 0) return;
  const id = queue.value.shift() as string;
  try {
    currentSrc.value = `/api/v1/track/stream/${id}`;
    playerVisible.value = true;
    activeTrackId.value = id;
  } catch {
    warn('再生に失敗しました');
  }
}

// 曲を1曲だけ再生する。
function playTrack(id: string): void {
  try {
    currentSrc.value = `/api/v1/track/stream/${id}`;
    playerVisible.value = true;
    activeTrackId.value = id;
  } catch {
    warn('再生に失敗しました');
  }
}

// 現在のトラックが終了したら、キューがあれば次のトラックへ進む。
function onEnded(): void {
  if (queue.value.length > 0) {
    playNext();
  }
}
</script>
