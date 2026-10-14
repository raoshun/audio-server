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
          @keydown.enter="performSearch"
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

      <!-- 暗転レイヤー。曲を選択すると表示され、背景を暗くする。
           最小化時は表示せず、直前の画面を操作できる状態へ戻す。 -->
      <div class="overlay" :style="{ display: modalVisible && !modalMinimized ? 'block' : 'none' }"></div>

      <!-- 中央再生ウィンドウ。最小化時は「表示」と「閉じる」の2ボタンだけのバーへ
           縮小する。閉じるボタンは再生を停止し、最小化ボタンは再生を継続する。
           .player と #player は既存テスト契約（Playwright / Vitest）が参照する
           ため、要素名・クラス・display のスタイル束縛は変更しない。 -->
      <div
        class="player-modal"
        :class="{ minimized: modalMinimized }"
        :style="{ display: modalVisible ? 'flex' : 'none' }"
      >
        <div class="modal-header">
          <div class="modal-track" v-if="!modalMinimized">
            <span class="modal-title">{{ modalTitle }}</span>
            <span class="modal-artist">{{ modalArtist }}</span>
          </div>
          <div class="modal-buttons">
            <button id="minimizeModalBtn" type="button" v-if="!modalMinimized" @click="minimizeModal">最小化</button>
            <button id="showModalBtn" type="button" v-if="modalMinimized" @click="showModal">表示</button>
            <button id="closeModalBtn" type="button" @click="closeModal">閉じる</button>
          </div>
        </div>

        <!-- 最小化時は曲情報・プレイヤー・歌詞を隠し、2ボタンだけ残す。 -->
        <div class="modal-body" v-show="!modalMinimized">
          <section class="player" :style="{ display: playerVisible ? 'block' : 'none' }">
            <audio
              id="player"
              ref="audioEl"
              controls
              :src="currentSrc"
              @ended="onEnded"
              @timeupdate="onTimeUpdate"
            ></audio>
          </section>

          <!-- 歌詞パネル。歌詞が無い曲・取得失敗時はメッセージを表示する。 -->
          <section class="lyrics" ref="lyricsPanel">
            <p v-if="lyricsLoading" class="lyrics-message">歌詞を取得中…</p>
            <p v-else-if="lyricsFailed" class="lyrics-message">歌詞を取得できませんでした</p>
            <p v-else-if="lyrics.length === 0" class="lyrics-message">歌詞はありません</p>
            <ul v-else id="lyricsList">
              <li
                v-for="(line, index) in lyrics"
                :key="index"
                class="lyric-line"
                :class="{ active: index === activeLyricIndex }"
              >
                {{ line.text }}
              </li>
            </ul>
          </section>
        </div>
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
// スタイルは style.css（vanilla 時代の既存スタイル）を使用し、バンドルへ取り込む。
// 表示・レイアウトは変更せず、既存のデザインをそのまま維持する。
import '../style.css';

import { nextTick, ref } from 'vue';

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
// 再生要素（vanilla と同一に load() 明示呼び出しと自動再生を行うため）。
const audioEl = ref<HTMLAudioElement | null>(null);

// モーダル（暗転オーバーレイ）の表示。曲を選択すると表示される。
const modalVisible = ref(false);
// 最小化状態。true のときは「表示」と「閉じる」の2ボタンだけのバーになり、
// 暗転は解かれて直前の画面を操作できる（再生は継続する）。
const modalMinimized = ref(false);
// モーダルヘッダへ表示する曲情報。
const modalTitle = ref('');
const modalArtist = ref('');
// 歌詞パネルの状態。
const lyrics = ref<LyricLineData[]>([]);
const lyricsLoading = ref(false);
const lyricsFailed = ref(false);
// 再生位置と同期してハイライトする行のインデックス。
const activeLyricIndex = ref(-1);
// 歌詞パネル要素（アクティブ行の自動スクロールに使用）。
const lyricsPanel = ref<HTMLElement | null>(null);

// 歌詞の1行（API 契約と同一。start は曲頭からのミリ秒 offset）。
interface LyricLineData {
  start: number;
  text: string;
}
// 曲情報（モーダルヘッダ表示用。既存 API 契約の song 型を拡張しない）。
interface TrackInfo extends Track {
  artist?: string;
}

// 型定義（既存 API 契約に基づき、変更しない）。
interface Track {
  id: string;
  title?: string;
  name?: string;
  artist?: string;
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

// 曲 ID から表示用の曲情報を検索する。検索結果・アルバムトラックのどちらに
// あっても参照できるように、両方の一覧から照合する。
function lookupTrack(id: string): TrackInfo | null {
  const fromResults = results.value.find((item) => item.id === id);
  if (fromResults) return fromResults;
  const fromAlbum = albumTracks.value.find((item) => item.id === id);
  return fromAlbum ?? null;
}

// 歌詞を取得する（GET /api/v1/lyrics/{track_id}）。
// 歌詞は Navidrome の .lrc サイドカーからバックエンド経由で取得するため、
// 失敗時は歌詞パネルに「歌詞を取得できませんでした」を表示する。
async function fetchLyrics(id: string): Promise<void> {
  lyrics.value = [];
  activeLyricIndex.value = -1;
  lyricsFailed.value = false;
  lyricsLoading.value = true;
  try {
    // バックエンドの歌詞 API（GET /api/v1/lyrics/{track_id}）を呼ぶ。
    const resp = await fetch(`/api/v1/lyrics/${id}`);
    if (!resp.ok) {
      lyricsLoading.value = false;
      lyricsFailed.value = true;
      return;
    }
    const data = await resp.json();
    lyrics.value = Array.isArray(data.lines) ? data.lines : [];
    lyricsLoading.value = false;
    // 取得直後の再生位置（load() 前でも currentTime は保持される）で
    // アクティブ行を初期化する。
    syncLyricIndex();
  } catch {
    lyricsLoading.value = false;
    lyricsFailed.value = true;
  }
}

// 再生位置（秒）に対応する歌詞行のインデックスを算出し、パネル内へ
// アクティブ行が見えるようスクロールする。jsdom（テスト環境）は
// scrollIntoView を実装していないため、存在を確認してから呼ぶ。
function syncLyricIndex(): void {
  if (lyrics.value.length === 0) return;
  const el = audioEl.value;
  const currentMs = Math.floor((el?.currentTime ?? 0) * 1000);
  let index = -1;
  for (let i = 0; i < lyrics.value.length; i += 1) {
    if (lyrics.value[i].start <= currentMs) {
      index = i;
    } else {
      break;
    }
  }
  activeLyricIndex.value = index;
  if (index < 0) return;
  const panel = lyricsPanel.value;
  const target = panel?.querySelector(`li.lyric-line:nth-child(${index + 1})`);
  if (target && typeof target.scrollIntoView === 'function') {
    target.scrollIntoView({ block: 'nearest' });
  }
}

// 再生位置が進んだときに歌詞を同期させる（audio の timeupdate）。
function onTimeUpdate(): void {
  syncLyricIndex();
}

// 再生を停止する。pause() で再生を止め、キューを空にすることで
// 曲終了時の自動次曲送りも止める。
function stopPlayback(): void {
  const el = audioEl.value;
  if (el && typeof el.pause === 'function') {
    el.pause();
  }
  queue.value = [];
  activeTrackId.value = null;
  playerVisible.value = false;
}

// 暗転オーバーレイを閉じる。閉じるボタンは再生を停止する。
function closeModal(): void {
  stopPlayback();
  modalVisible.value = false;
  modalMinimized.value = false;
}

// 最小化する。再生は継続したまま、暗転を解いて直前の画面を操作可能にする。
// ヘッダは「表示」と「閉じる」の2ボタンだけのバーへ切り替わる。
function minimizeModal(): void {
  modalMinimized.value = true;
}

// 最小化から復帰し、直前の表示（曲情報・プレイヤー・歌詞）へ戻す。
// 再生は継続したままなので、操作を再開できる。
function showModal(): void {
  modalMinimized.value = false;
}

// src を設定して再生を開始する。vanilla（app.js）と同一に load() を明示し、
// play() で自動再生する。play() の拒否（ブラウザの自動再生ブロック）は
// vanilla では catch していないため、ここでは黙って無視する。
async function startPlayback(id: string): Promise<void> {
  currentSrc.value = `/api/v1/track/stream/${id}`;
  playerVisible.value = true;
  activeTrackId.value = id;
  // 曲を選択したときに暗転オーバーレイの中央再生ウィンドウを表示する。
  // 最小化された状態から新しい曲を選んだ場合は、フル表示へ戻す。
  modalVisible.value = true;
  modalMinimized.value = false;
  const info = lookupTrack(id);
  modalTitle.value = info ? displayName(info) : 'Unnamed track';
  modalArtist.value = info?.artist ?? '';
  await fetchLyrics(id);
  // :src 束縛が DOM へ反映されてから load()/play() を呼ぶ。
  await nextTick();
  const el = audioEl.value;
  if (!el) return;
  try {
    el.load();
    const p = el.play();
    if (p && typeof p.catch === 'function') {
      p.catch(() => {
        // 自動再生がブロックされた場合はユーザー操作を待つ（vanilla と同一）。
      });
    }
  } catch {
    warn('再生に失敗しました');
  }
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
    if (!resp.ok) {
      warn('検索に失敗しました');
      return;
    }
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
    if (!resp.ok) {
      warn('全曲一覧の取得に失敗しました');
      return;
    }
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
    if (!resp.ok) {
      warn('アルバム一覧の取得に失敗しました');
      return;
    }
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
      warn('アルバムを開けませんでした');
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
async function playAlbumSequential(): Promise<void> {
  queue.value = albumTrackIds();
  await playNext();
}

// アルバムのトラックをランダム再生する（Fisher-Yates でシャッフル後に再生する）。
async function playAlbumShuffle(): Promise<void> {
  const ids = albumTrackIds();
  if (ids.length === 0) return;
  for (let i = ids.length - 1; i > 0; i -= 1) {
    const j = Math.floor(Math.random() * (i + 1));
    [ids[i], ids[j]] = [ids[j], ids[i]];
  }
  queue.value = ids;
  await playNext();
}

// キューの先頭のトラックを再生する。トラックが終了したら次のトラックへ進む。
async function playNext(): Promise<void> {
  if (queue.value.length === 0) return;
  const id = queue.value.shift() as string;
  try {
    await startPlayback(id);
  } catch {
    warn('再生に失敗しました');
  }
}

// 曲を1曲だけ再生する。
async function playTrack(id: string): Promise<void> {
  try {
    await startPlayback(id);
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
