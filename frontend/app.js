// 再生キュー（順再生/ランダム再生中の次曲リスト）。明示的に宣言する。
let queue = [];

document.addEventListener('DOMContentLoaded', () => {
    const queryInput = document.getElementById('query');
    const searchBtn = document.getElementById('searchBtn');
    const listAllBtn = document.getElementById('listAllBtn');
    const albumListBtn = document.getElementById('albumListBtn');
    const resultList = document.getElementById('resultList');
    const albumList = document.getElementById('albumList');
    const albumTracksSection = document.getElementById('albumTracksSection');
    const albumTracksList = document.getElementById('albumTracksList');
    const playSequentialBtn = document.getElementById('playSequentialBtn');
    const playShuffleBtn = document.getElementById('playShuffleBtn');
    const playerSection = document.querySelector('.player');
    const audioPlayer = document.getElementById('player');

    const renderResults = (items) => {
        resultList.innerHTML = '';
        items.forEach(item => {
            const li = document.createElement('li');
            // Navidrome provides "title" for tracks; "name" is not present.
            // Use title if available, otherwise fallback to name or a placeholder.
            const displayName = item.title ?? item.name ?? 'Unnamed track';
            li.textContent = `${displayName}`;
            li.dataset.id = item.id;
            li.style.cursor = 'pointer';
            li.addEventListener('click', async () => {
                try {
                    // Obtain a proxied stream URL that the browser can access.
                    // The backend proxy returns the raw audio stream directly.
                    // Use the proxy streaming endpoint directly as the audio source.
                    audioPlayer.src = `/api/v1/track/stream/${item.id}`;
                    // Load the new source before attempting playback to satisfy browsers that require explicit load.
                    audioPlayer.load();
                    playerSection.style.display = 'block';
                    audioPlayer.play();
                } catch (e) {
                    alert('再生に失敗しました');
                }
            });
            resultList.appendChild(li);
        });
    };

    // アルバム一覧を描画する。項目をクリックするとそのアルバムのトラック一覧を取得する。
    const renderAlbums = (items) => {
        albumList.innerHTML = '';
        items.forEach(album => {
            const li = document.createElement('li');
            li.textContent = `${album.title} — ${album.artist}`;
            li.dataset.id = album.id;
            li.style.cursor = 'pointer';
            li.addEventListener('click', async () => {
                try {
                    await openAlbum(album.id);
                } catch (e) {
                    alert('アルバムを開けませんでした');
                }
            });
            albumList.appendChild(li);
        });
    };

    // アルバムを選択すると、そのトラック一覧を取得してトラックリストと再生モードを表示する。
    async function openAlbum(albumId) {
        albumTracksList.innerHTML = '';
        albumTracksSection.style.display = 'none';
        queue = [];
        try {
            const resp = await fetch(`/api/v1/albums/${albumId}`);
            if (!resp.ok) {
                alert('アルバムを取れませんでした');
                return;
            }
            const data = await resp.json();
            const tracks = data.tracks || [];
            if (tracks.length === 0) {
                albumTracksSection.style.display = 'none';
                return;
            }
            albumTracksSection.style.display = 'block';
            playSequentialBtn.style.display = 'inline-block';
            playShuffleBtn.style.display = 'inline-block';
            tracks.forEach(track => {
                const li = document.createElement('li');
                li.textContent = `${track.title}`;
                li.dataset.id = track.id;
                li.style.cursor = 'pointer';
                li.addEventListener('click', () => {
                    playTrack(track.id);
                });
                albumTracksList.appendChild(li);
            });
        } catch (e) {
            albumTracksSection.style.display = 'none';
            alert('アルバムを開けませんでした');
        }
    }

    // アルバムのトラックを順再生する（トラックリストの先頭から順番に再生する）。
    function playAlbumSequential() {
        const ordered = Array.from(albumTracksList.querySelectorAll('li'))
            .map(li => li.dataset.id)
            .filter(x => typeof x === 'string');
        queue = ordered;
        playNext();
    }

    // アルバムのトラックをランダム再生する（シャッフル後に先頭から再生する）。
    function playAlbumShuffle() {
        const ids = Array.from(albumTracksList.querySelectorAll('li'))
            .map(li => li.dataset.id)
            .filter(x => typeof x === 'string');
        if (ids.length === 0) {
            return;
        }
        // Fisher-Yates シャッフルで再生順序を乱す。
        for (let i = ids.length - 1; i > 0; i -= 1) {
            const j = Math.floor(Math.random() * (i + 1));
            [ids[i], ids[j]] = [ids[j], ids[i]];
        }
        queue = ids;
        playNext();
    }

    // キューの先頭のトラックを再生する。トラックが終了したら次のトラックへ進む。
    function playNext() {
        if (!queue || queue.length === 0) {
            return;
        }
        const id = queue.shift();
        try {
            audioPlayer.src = `/api/v1/track/stream/${id}`;
            audioPlayer.load();
            playerSection.style.display = 'block';
            highlightActive(id);
            audioPlayer.play();
        } catch (e) {
            alert('再生に失敗しました');
        }
    }

    // 再生中のトラックをトラックリストにハイライトする。
    function highlightActive(id) {
        albumTracksList.querySelectorAll('li').forEach(li => {
            if (li.dataset.id === id) {
                li.classList.add('active');
            } else {
                li.classList.remove('active');
            }
        });
    }

    // 曲を1曲だけ再生する。
    function playTrack(id) {
        try {
            audioPlayer.src = `/api/v1/track/stream/${id}`;
            audioPlayer.load();
            playerSection.style.display = 'block';
            highlightActive(id);
            audioPlayer.play();
        } catch (e) {
            alert('再生に失敗しました');
        }
    }

    const performSearch = async () => {
        const query = queryInput.value.trim();
        if (!query) return;
        try {
            const resp = await fetch('/api/v1/search/music', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query })
            });
            const data = await resp.json();
            renderResults(data.results);
        } catch (e) {
            alert('検索に失敗しました');
        }
    };

    searchBtn.addEventListener('click', performSearch);
    listAllBtn.addEventListener('click', fetchAllTracks);
    albumListBtn.addEventListener('click', fetchAlbums);
    playSequentialBtn.addEventListener('click', () => {
        playAlbumSequential();
    });
    playShuffleBtn.addEventListener('click', () => {
        playAlbumShuffle();
    });
    queryInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') performSearch();
    });
    // 現在のトラックが終了したら、キューがあれば次のトラックへ進む。
    audioPlayer.addEventListener('ended', () => {
        if (queue.length > 0) {
            playNext();
        }
    });

    // 全曲一覧を取得する。
    async function fetchAllTracks() {
        try {
            const resp = await fetch('/api/v1/tracks');
            const data = await resp.json();
            renderResults(data.results);
        } catch (e) {
            alert('全曲一覧の取得に失敗しました');
        }
    }

    // アルバム一覧を取得する。
    async function fetchAlbums() {
        try {
            const resp = await fetch('/api/v1/albums');
            const data = await resp.json();
            renderAlbums(data.albums || []);
        } catch (e) {
            alert('アルバム一覧の取得に失敗しました');
        }
    }
});