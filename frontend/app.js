document.addEventListener('DOMContentLoaded', () => {
    const queryInput = document.getElementById('query');
    const searchBtn = document.getElementById('searchBtn');
    const listAllBtn = document.getElementById('listAllBtn');
    const resultList = document.getElementById('resultList');
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
    queryInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') performSearch();
    });

    async function fetchAllTracks() {
        try {
            const resp = await fetch('/api/v1/tracks');
            const data = await resp.json();
            renderResults(data.results);
        } catch (e) {
            alert('全曲一覧の取得に失敗しました');
        }
    }
});