// Vitest のセットアップファイル。
// jsdom は HTMLMediaElement の load()/play() を実装していないため、
// 「Not implemented」エラーノイズが出る。テストでは再生動作そのものを
// 検証しないので、no-op に差し替えて出力をクリーンにする。
import { beforeEach } from 'vitest';

beforeEach(() => {
  const media = globalThis.HTMLMediaElement?.prototype;
  if (!media) return;
  media.load = () => {};
  media.play = () => Promise.resolve();
});
