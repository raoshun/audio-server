// App.vue のユニットテスト（Vitest + @vue/test-utils）。
// frontend/src/App.vue の全ロジックを検証する。
// 表示名（displayName）、検索、全曲一覧、アルバム一覧、アルバム開き、
// 順再生・ランダム再生、キュー再生・自動次曲、再生中ハイライト、
// Enter キー検索、load()/play() の明示呼び出しを含む。
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { flushPromises, mount } from '@vue/test-utils';
import App from '../src/App.vue';

// 各テストで利用する fetch / alert をモック化する。
// App.vue はグローバルな fetch と alert を直接使用するため、
// 環境に対して mock を設定する。
let fetchMock: ReturnType<typeof vi.fn>;
let alertMock: ReturnType<typeof vi.fn>;

// jsdom は HTMLMediaElement の load()/play() を実装していないため、
// テストでは no-op の mock に差し替える（呼び出し自体を検証する）。
function stubMedia(el: Element): { load: ReturnType<typeof vi.fn>; play: ReturnType<typeof vi.fn> } {
  const media = el as unknown as { load: () => void; play: () => Promise<void> };
  const load = vi.fn();
  const play = vi.fn(() => Promise.resolve());
  media.load = load;
  media.play = play;
  return { load, play };
}

// fetch のレスポンスを再現するためのヘルパー。
// 実際の fetch の戻り値（ok / status / json）を模倣する。
function mockFetchResponse(data: unknown, ok = true, status = 200) {
  return {
    ok,
    status,
    json: async () => data,
  };
}

// URL を照合して指定レスポンスを返す fetch モックを構成する。
function mockFetch(url: string, response: unknown, ok = true, status = 200) {
  fetchMock.mockImplementation(async (input: RequestInfo | URL) => {
    const reqUrl = String(input);
    if (reqUrl === url) {
      return mockFetchResponse(response, ok, status);
    }
    return mockFetchResponse({ error: 'unexpected url' }, false, 404);
  });
}

// アルバム一覧を描画し、最初のアルバムをクリックしてトラック一覧を表示する。
async function openFirstAlbum(wrapper: any, tracks: unknown) {
  mockFetch('/api/v1/albums', { albums: [{ id: 'a1', title: 'Album A', artist: 'Artist A' }] });
  await wrapper.find('#albumListBtn').trigger('click');
  await flushPromises();

  mockFetch('/api/v1/albums/a1', { tracks });
  await wrapper.findAll('#albumList li')[0].trigger('click');
  await flushPromises();
}

describe('App.vue', () => {
  beforeEach(() => {
    fetchMock = vi.fn();
    alertMock = vi.fn();
    // グローバル fetch と alert をモックに差し替える。
    // @ts-expect-error - テスト環境ではグローバルを差し替える。
    global.fetch = fetchMock;
    // @ts-expect-error - テスト環境ではグローバルを差し替える。
    global.alert = alertMock;
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('表示名（displayName）', () => {
    it('検索結果の表示名は title を優先して描画する', async () => {
      // 検索 API は results を返す。
      mockFetch('/api/v1/search/music', { results: [{ id: 't1', title: 'Song Title' }] });

      const wrapper = mount(App);
      await wrapper.find('#query').setValue('Song');
      await wrapper.find('#searchBtn').trigger('click');
      await flushPromises();

      // #resultList の最初の li のテキストは title になる。
      const firstLi = wrapper.findAll('#resultList li')[0];
      expect(firstLi.text()).toBe('Song Title');
    });

    it('title が無ければ name を使う', async () => {
      // title が無いため name を表示する。
      mockFetch('/api/v1/search/music', { results: [{ id: 't2', name: 'Song Name' }] });

      const wrapper = mount(App);
      await wrapper.find('#query').setValue('Name');
      await wrapper.find('#searchBtn').trigger('click');
      await flushPromises();

      const firstLi = wrapper.findAll('#resultList li')[0];
      expect(firstLi.text()).toBe('Song Name');
    });

    it('title と name の両方が無ければ Unnamed track を表示する', async () => {
      // title も name も無い。
      mockFetch('/api/v1/search/music', { results: [{ id: 't3' }] });

      const wrapper = mount(App);
      await wrapper.find('#query').setValue('NoName');
      await wrapper.find('#searchBtn').trigger('click');
      await flushPromises();

      const firstLi = wrapper.findAll('#resultList li')[0];
      expect(firstLi.text()).toBe('Unnamed track');
    });
  });

  describe('検索（performSearch）', () => {
    it('空文字列の時は検索しない', async () => {
      const wrapper = mount(App);
      // query を空にしたまま検索ボタンを押す。
      await wrapper.find('#searchBtn').trigger('click');
      await flushPromises();

      // fetch は呼ばれない。
      expect(fetchMock).not.toHaveBeenCalled();
    });

    it('検索に成功すると結果を描画する', async () => {
      mockFetch('/api/v1/search/music', { results: [{ id: 't1', title: 'Hit' }] });

      const wrapper = mount(App);
      await wrapper.find('#query').setValue('Hit');
      await wrapper.find('#searchBtn').trigger('click');
      await flushPromises();

      const firstLi = wrapper.findAll('#resultList li')[0];
      expect(firstLi.text()).toBe('Hit');
      expect(firstLi.attributes('data-id')).toBe('t1');
    });

    it('検索失敗時は警告を表示する', async () => {
      // fetch が失敗する。
      fetchMock.mockResolvedValue({
        ok: false,
        status: 500,
        json: async () => ({ error: 'server error' }),
      });

      const wrapper = mount(App);
      await wrapper.find('#query').setValue('Fail');
      await wrapper.find('#searchBtn').trigger('click');
      await flushPromises();

      expect(alertMock).toHaveBeenCalledWith('検索に失敗しました');
    });

    it('Enter キーで検索する（vanilla の keypress 相当）', async () => {
      mockFetch('/api/v1/search/music', { results: [{ id: 't1', title: 'Enter Hit' }] });

      const wrapper = mount(App);
      await wrapper.find('#query').setValue('Enter');
      await wrapper.find('#query').trigger('keydown.enter');
      await flushPromises();

      expect(fetchMock).toHaveBeenCalled();
      expect(wrapper.findAll('#resultList li')[0].text()).toBe('Enter Hit');
    });
  });

  describe('全曲一覧（fetchAllTracks）', () => {
    it('全曲一覧を取得し、描画する', async () => {
      mockFetch('/api/v1/tracks', { results: [{ id: 't1', title: 'All' }] });

      const wrapper = mount(App);
      await wrapper.find('#listAllBtn').trigger('click');
      await flushPromises();

      const firstLi = wrapper.findAll('#resultList li')[0];
      expect(firstLi.text()).toBe('All');
    });

    it('全曲一覧の取得失敗時は警告を表示する', async () => {
      fetchMock.mockResolvedValue({
        ok: false,
        status: 500,
        json: async () => ({ error: 'server error' }),
      });

      const wrapper = mount(App);
      await wrapper.find('#listAllBtn').trigger('click');
      await flushPromises();

      expect(alertMock).toHaveBeenCalledWith('全曲一覧の取得に失敗しました');
    });
  });

  describe('アルバム一覧（fetchAlbums）', () => {
    it('アルバム一覧を取得し、描画する', async () => {
      mockFetch('/api/v1/albums', {
        albums: [{ id: 'a1', title: 'Album A', artist: 'Artist A' }],
      });

      const wrapper = mount(App);
      await wrapper.find('#albumListBtn').trigger('click');
      await flushPromises();

      const firstLi = wrapper.findAll('#albumList li')[0];
      expect(firstLi.attributes('data-id')).toBe('a1');
      expect(firstLi.text()).toContain('Album A');
    });

    it('アルバム一覧の取得失敗時は警告を表示する', async () => {
      fetchMock.mockResolvedValue({
        ok: false,
        status: 500,
        json: async () => ({ error: 'server error' }),
      });

      const wrapper = mount(App);
      await wrapper.find('#albumListBtn').trigger('click');
      await flushPromises();

      expect(alertMock).toHaveBeenCalledWith('アルバム一覧の取得に失敗しました');
    });
  });

  describe('アルバム開き（openAlbum）', () => {
    it('アルバムを開くとトラック一覧を表示し、順再生・ランダム再生ボタンを表示する', async () => {
      const wrapper = mount(App);
      await openFirstAlbum(wrapper, [{ id: 't1', title: 'T1' }, { id: 't2', title: 'T2' }]);

      const section = wrapper.find('#albumTracksSection');
      expect(section.attributes('style')).toContain('block');

      const tracks = wrapper.findAll('#albumTracksList li');
      expect(tracks.length).toBe(2);
      expect(wrapper.find('#playSequentialBtn').exists()).toBe(true);
      expect(wrapper.find('#playShuffleBtn').exists()).toBe(true);
    });

    it('アルバムが開けない場合は警告し、セクションを隠す', async () => {
      const wrapper = mount(App);
      await openFirstAlbum(wrapper, [{ id: 't1', title: 'T1' }]);

      // アルバムを開く fetch が失敗する（HTTP 404）。
      mockFetch('/api/v1/albums/a1', { error: 'not found' }, false, 404);
      await wrapper.findAll('#albumList li')[0].trigger('click');
      await flushPromises();

      expect(alertMock).toHaveBeenCalledWith('アルバムを開けませんでした');
      expect(wrapper.find('#albumTracksSection').attributes('style')).toContain('none');
    });

    it('fetch の例外時は警告し、セクションを隠す', async () => {
      const wrapper = mount(App);
      await openFirstAlbum(wrapper, [{ id: 't1', title: 'T1' }]);

      // fetch 自体が例外を投げる。
      fetchMock.mockRejectedValue(new Error('network down'));
      await wrapper.findAll('#albumList li')[0].trigger('click');
      await flushPromises();

      expect(alertMock).toHaveBeenCalledWith('アルバムを開けませんでした');
      expect(wrapper.find('#albumTracksSection').attributes('style')).toContain('none');
    });
  });

  describe('順再生（playAlbumSequential）', () => {
    it('順再生を開始すると、プレイヤーを表示し、現在のトラック ID を設定する', async () => {
      const wrapper = mount(App);
      await openFirstAlbum(wrapper, [{ id: 't1', title: 'T1' }, { id: 't2', title: 'T2' }]);

      // 順再生ボタンを押す。
      await wrapper.find('#playSequentialBtn').trigger('click');
      await flushPromises();

      // プレイヤーが表示される。
      const player = wrapper.find('.player');
      expect(player.attributes('style')).toContain('block');

      // #player の src は再生中のトラックを指す。
      const audio = wrapper.find('#player');
      expect(audio.attributes('src')).toContain('/api/v1/track/stream/t1');
    });
  });

  describe('ランダム再生（playAlbumShuffle）', () => {
    it('ランダム再生を開始すると、プレイヤーを表示し、現在のトラック ID を設定する', async () => {
      const wrapper = mount(App);
      await openFirstAlbum(wrapper, [{ id: 't1', title: 'T1' }, { id: 't2', title: 'T2' }]);

      // ランダム再生ボタンを押す。
      await wrapper.find('#playShuffleBtn').trigger('click');
      await flushPromises();

      // プレイヤーが表示される。
      const player = wrapper.find('.player');
      expect(player.attributes('style')).toContain('block');

      // #player の src は再生中のトラックを指す。
      const audio = wrapper.find('#player');
      expect(audio.attributes('src')).toContain('/api/v1/track/stream/');
    });
  });

  describe('自動次曲（onEnded）', () => {
    it('現在のトラックが終了したら、キューがあれば次のトラックへ進む', async () => {
      const wrapper = mount(App);
      await openFirstAlbum(wrapper, [{ id: 't1', title: 'T1' }, { id: 't2', title: 'T2' }]);

      // 順再生を開始。
      await wrapper.find('#playSequentialBtn').trigger('click');
      await flushPromises();

      // 現在のトラックは t1。
      expect(wrapper.find('#player').attributes('src')).toContain('t1');

      // プレイヤーが終了したことをシミュレート。
      await wrapper.find('#player').trigger('ended');
      await flushPromises();

      // 次のトラック t2 へ進む。
      expect(wrapper.find('#player').attributes('src')).toContain('t2');
    });
  });

  describe('単曲再生（playTrack）', () => {
    it('load() と play() を明示的に呼ぶ（vanilla と同一挙動）', async () => {
      mockFetch('/api/v1/search/music', { results: [{ id: 't1', title: 'Play' }] });

      const wrapper = mount(App);
      const media = stubMedia(wrapper.find('#player').element);
      await wrapper.find('#query').setValue('Play');
      await wrapper.find('#searchBtn').trigger('click');
      await flushPromises();

      await wrapper.findAll('#resultList li')[0].trigger('click');
      await flushPromises();

      expect(media.load).toHaveBeenCalled();
      expect(media.play).toHaveBeenCalled();
      expect(wrapper.find('#player').attributes('src')).toContain('/api/v1/track/stream/t1');
    });
  });

  describe('再生中ハイライト', () => {
    it('再生中のトラックがハイライトされる', async () => {
      const wrapper = mount(App);
      await openFirstAlbum(wrapper, [{ id: 't1', title: 'T1' }, { id: 't2', title: 'T2' }]);

      // 順再生を開始。
      await wrapper.find('#playSequentialBtn').trigger('click');
      await flushPromises();

      // 再生中のトラック t1 が active クラスでハイライトされる。
      const activeItems = wrapper.findAll('#albumTracksList li.active');
      expect(activeItems.length).toBe(1);
      expect(activeItems[0].attributes('data-id')).toBe('t1');
    });
  });
  describe('暗転モーダル再生UI', () => {
    it('曲を選択するとオーバーレイと中央再生ウィンドウを表示する', async () => {
      mockFetch('/api/v1/search/music', { results: [{ id: 't1', title: 'Modal Song', artist: 'Artist A' }] });
      mockFetch('/api/v1/lyrics/t1', { track_id: 't1', synced: false, lines: [] });

      const wrapper = mount(App);
      await wrapper.find('#query').setValue('Modal');
      await wrapper.find('#searchBtn').trigger('click');
      await flushPromises();

      // 初期はオーバーレイが非表示、曲をクリックすると表示される。
      expect(wrapper.find('.overlay').attributes('style')).toContain('none');
      await wrapper.findAll('#resultList li')[0].trigger('click');
      await flushPromises();

      expect(wrapper.find('.overlay').attributes('style')).toContain('block');
      expect(wrapper.find('.player-modal').exists()).toBe(true);
      expect(wrapper.find('.modal-title').text()).toBe('Modal Song');
      expect(wrapper.find('.modal-artist').text()).toBe('Artist A');

      // 既存契約（.player / #player）はモーダル内でも維持される。
      expect(wrapper.find('.player').attributes('style')).toContain('block');
      expect(wrapper.find('#player').attributes('src')).toContain('/api/v1/track/stream/t1');
    });

    it('閉じるボタンでオーバーレイを閉じ、再生は継続する', async () => {
      mockFetch('/api/v1/search/music', { results: [{ id: 't1', title: 'Song' }] });
      mockFetch('/api/v1/lyrics/t1', { track_id: 't1', synced: false, lines: [] });

      const wrapper = mount(App);
      await wrapper.find('#query').setValue('Song');
      await wrapper.find('#searchBtn').trigger('click');
      await flushPromises();
      await wrapper.findAll('#resultList li')[0].trigger('click');
      await flushPromises();

      await wrapper.find('#closeModalBtn').trigger('click');
      await flushPromises();

      // オーバーレイは閉じるが、プレイヤーと再生元はそのまま残る。
      expect(wrapper.find('.overlay').attributes('style')).toContain('none');
      expect(wrapper.find('.player').attributes('style')).toContain('block');
      expect(wrapper.find('#player').attributes('src')).toContain('/api/v1/track/stream/t1');
    });
  });

  describe('歌詞の同期表示', () => {
    it('歌詞がある曲は歌詞行を描画する', async () => {
      mockFetch('/api/v1/search/music', { results: [{ id: 't1', title: 'Lyric Song' }] });
      mockFetch('/api/v1/lyrics/t1', {
        track_id: 't1',
        synced: true,
        lines: [
          { start: 0, text: 'First line.' },
          { start: 11640, text: 'Second line.' },
        ],
      });

      const wrapper = mount(App);
      await wrapper.find('#query').setValue('Lyric');
      await wrapper.find('#searchBtn').trigger('click');
      await flushPromises();
      await wrapper.findAll('#resultList li')[0].trigger('click');
      await flushPromises();

      const lines = wrapper.findAll('#lyricsList li');
      expect(lines.length).toBe(2);
      expect(lines[0].text()).toBe('First line.');
      // 再生位置 0 秒の行がアクティブになる。
      expect(lines[0].classes()).toContain('active');
    });

    it('timeupdate で再生位置に対応する行がハイライトされる', async () => {
      mockFetch('/api/v1/search/music', { results: [{ id: 't1', title: 'Lyric Song' }] });
      mockFetch('/api/v1/lyrics/t1', {
        track_id: 't1',
        synced: true,
        lines: [
          { start: 0, text: 'First line.' },
          { start: 11640, text: 'Second line.' },
        ],
      });

      const wrapper = mount(App);
      await wrapper.find('#query').setValue('Lyric');
      await wrapper.find('#searchBtn').trigger('click');
      await flushPromises();
      await wrapper.findAll('#resultList li')[0].trigger('click');
      await flushPromises();

      // jsdom は HTMLMediaElement の currentTime を代入できるため、
      // 12 秒（12000ms）へ進めた timeupdate を発火して同期を検証する。
      const audio = wrapper.find('#player');
      (audio.element as unknown as { currentTime: number }).currentTime = 12;
      await audio.trigger('timeupdate');
      await flushPromises();

      const lines = wrapper.findAll('#lyricsList li');
      expect(lines[1].classes()).toContain('active');
      expect(lines[0].classes()).not.toContain('active');
    });

    it('歌詞がない曲は「歌詞はありません」を表示する', async () => {
      mockFetch('/api/v1/search/music', { results: [{ id: 't1', title: 'No Lyric' }] });
      mockFetch('/api/v1/lyrics/t1', { track_id: 't1', synced: false, lines: [] });

      const wrapper = mount(App);
      await wrapper.find('#query').setValue('NoLyric');
      await wrapper.find('#searchBtn').trigger('click');
      await flushPromises();
      await wrapper.findAll('#resultList li')[0].trigger('click');
      await flushPromises();

      expect(wrapper.find('.lyrics-message').text()).toBe('歌詞はありません');
      expect(wrapper.find('#lyricsList').exists()).toBe(false);
    });

    it('歌詞取得に失敗した場合は警告メッセージを表示する', async () => {
      mockFetch('/api/v1/search/music', { results: [{ id: 't1', title: 'Fail' }] });
      mockFetch('/api/v1/lyrics/t1', { error: 'not found' }, false, 404);

      const wrapper = mount(App);
      await wrapper.find('#query').setValue('Fail');
      await wrapper.find('#searchBtn').trigger('click');
      await flushPromises();
      await wrapper.findAll('#resultList li')[0].trigger('click');
      await flushPromises();

      expect(wrapper.find('.lyrics-message').text()).toBe('歌詞を取得できませんでした');
    });

    it('アルバムトラックの再生でも歌詞を取得する', async () => {
      const wrapper = mount(App);
      await openFirstAlbum(wrapper, [{ id: 't1', title: 'T1', artist: 'Artist A' }]);

      mockFetch('/api/v1/lyrics/t1', {
        track_id: 't1',
        synced: true,
        lines: [{ start: 0, text: 'Album line.' }],
      });

      await wrapper.find('#playSequentialBtn').trigger('click');
      await flushPromises();

      expect(wrapper.find('.overlay').attributes('style')).toContain('block');
      expect(wrapper.find('.modal-title').text()).toBe('T1');
      expect(wrapper.findAll('#lyricsList li')[0].text()).toBe('Album line.');
    });
  });
});
