#Kanha [ @xoknha ]


import os
import random
import re

import aiohttp
from py_yt import Playlist, VideosSearch

from VampireMusic import logger
from VampireMusic.helpers import Track, utils

# Shruti download API — primary download backend.
# Get a key from Telegram bot: @SHRUTIAPIBOT
SHRUTI_API_URL = os.environ.get("SHRUTI_API_URL", "https://api.shrutibots.site")
SHRUTI_API_KEY = os.environ.get("SHRUTI_API_KEY", "ShrutiBotsOKChMnKPT8mJA5xKDo1e")

# Inflex download API — fallback backend, used only if Shruti fails.
# Get a key from Telegram bot: @InflexAPIBot
INFLEX_API_URL = os.environ.get("INFLEX_API_URL", "https://teaminflex.xyz")
INFLEX_API_KEY = os.environ.get("INFLEX_API_KEY", "INFLEX20013628D")

DOWNLOAD_DIR = "downloads"


class YouTube:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.cookies = []
        self.checked = False
        self.cookie_dir = "Kanha/cookies"
        self.warned = False
        self.regex = re.compile(
            r"(https?://)?(www\.|m\.|music\.)?"
            r"(youtube\.com/(watch\?v=|shorts/|playlist\?list=)|youtu\.be/)"
            r"([A-Za-z0-9_-]{11}|PL[A-Za-z0-9_-]+)([&?][^\s]*)?"
        )
        self.iregex = re.compile(
            r"https?://(?:www\.|m\.|music\.)?(?:youtube\.com|youtu\.be)"
            r"(?!/(watch\?v=[A-Za-z0-9_-]{11}|shorts/[A-Za-z0-9_-]{11}"
            r"|playlist\?list=[A-Za-z0-9_-]+|[A-Za-z0-9_-]{11}))\S*"
        )

    def get_cookies(self):
        if not self.checked:
            for file in os.listdir(self.cookie_dir):
                if file.endswith(".txt"):
                    self.cookies.append(f"{self.cookie_dir}/{file}")
            self.checked = True
        if not self.cookies:
            if not self.warned:
                self.warned = True
                logger.warning("Cookies are missing; downloads might fail.")
            return None
        return random.choice(self.cookies)

    async def save_cookies(self, urls: list[str]) -> None:
        logger.info("Saving cookies from urls...")
        async with aiohttp.ClientSession() as session:
            for url in urls:
                name = url.split("/")[-1]
                link = "https://batbin.me/raw/" + name
                async with session.get(link) as resp:
                    resp.raise_for_status()
                    with open(f"{self.cookie_dir}/{name}.txt", "wb") as fw:
                        fw.write(await resp.read())
        logger.info(f"Cookies saved in {self.cookie_dir}.")

    def valid(self, url: str) -> bool:
        return bool(re.match(self.regex, url))

    def invalid(self, url: str) -> bool:
        """True only for a YouTube link that is malformed."""
        low = (url or "").lower()
        if "youtube.com" in low or "youtu.be" in low:
            return bool(re.match(self.iregex, url))
        return False

    async def search(self, query: str, m_id: int, video: bool = False) -> Track | None:
        try:
            _search = VideosSearch(query, limit=1, with_live=False)
            results = await _search.next()
        except Exception:
            return None

        if results and results["result"]:
            data = results["result"][0]
            return Track(
                id=data.get("id"),
                channel_name=data.get("channel", {}).get("name"),
                duration=data.get("duration"),
                duration_sec=utils.to_seconds(data.get("duration")),
                message_id=m_id,
                title=data.get("title")[:25],
                thumbnail=data.get("thumbnails", [{}])[-1].get("url").split("?")[0],
                url=data.get("link"),
                view_count=data.get("viewCount", {}).get("short"),
                video=video,
            )
        return None

    async def search_multi(self, query: str, m_id: int, video: bool = False, limit: int = 5) -> list[Track]:
        try:
            _search = VideosSearch(query, limit=limit, with_live=False)
            results = await _search.next()
        except Exception:
            return []
        tracks = []
        if results and results["result"]:
            for data in results["result"]:
                tracks.append(
                    Track(
                        id=data.get("id"),
                        channel_name=data.get("channel", {}).get("name"),
                        duration=data.get("duration"),
                        duration_sec=utils.to_seconds(data.get("duration")),
                        message_id=m_id,
                        title=data.get("title")[:25],
                        thumbnail=data.get("thumbnails", [{}])[-1].get("url").split("?")[0],
                        url=data.get("link"),
                        view_count=data.get("viewCount", {}).get("short"),
                        video=video,
                    )
                )
        return tracks

    async def playlist(self, limit: int, user: str, url: str, video: bool) -> list[Track | None]:
        tracks = []
        try:
            plist = await Playlist.get(url)
            for data in plist["videos"][:limit]:
                track = Track(
                    id=data.get("id"),
                    channel_name=data.get("channel", {}).get("name", ""),
                    duration=data.get("duration"),
                    duration_sec=utils.to_seconds(data.get("duration")),
                    title=data.get("title")[:25],
                    thumbnail=data.get("thumbnails")[-1].get("url").split("?")[0],
                    url=data.get("link").split("&list=")[0],
                    user=user,
                    view_count="",
                    video=video,
                )
                tracks.append(track)
        except Exception:
            pass
        return tracks

    @staticmethod
    def _extract_id(link: str) -> str:
        """Accepts either a raw 11-char video ID or a full watch URL."""
        return link.split("v=")[-1].split("&")[0] if "v=" in link else link

    @staticmethod
    def _cleanup(path: str) -> None:
        if os.path.exists(path):
            try:
                os.remove(path)
            except Exception:
                pass

    async def _shruti_download(self, vid: str, media_type: str, path: str) -> bool:
        """Primary backend. Returns True on a verified, non-empty file."""
        tag = media_type.upper()
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{SHRUTI_API_URL}/download",
                    params={"url": vid, "type": media_type, "api_key": SHRUTI_API_KEY},
                    timeout=aiohttp.ClientTimeout(total=300 if media_type == "audio" else 600),
                ) as resp:
                    if resp.status != 200:
                        logger.error(f"[SHRUTI][{tag}] API returned HTTP {resp.status} for ID: {vid}")
                        return False
                    with open(path, "wb") as f:
                        async for chunk in resp.content.iter_chunked(131072):
                            f.write(chunk)

            if os.path.exists(path) and os.path.getsize(path) > 0:
                logger.info(f"[SHRUTI] {tag} download completed for {vid}")
                return True
            self._cleanup(path)
            return False

        except Exception as e:
            logger.error(f"[SHRUTI][{tag}] Exception for ID {vid}: {e}")
            self._cleanup(path)
            return False

    async def _inflex_download(self, vid: str, media_type: str, path: str) -> bool:
        """Fallback backend, only tried if Shruti fails. Returns True on a verified, non-empty file."""
        tag = media_type.upper()
        try:
            async with aiohttp.ClientSession() as session:
                payload = {"url": vid, "type": media_type}
                headers = {"Content-Type": "application/json", "X-API-KEY": INFLEX_API_KEY}

                async with session.post(
                    f"{INFLEX_API_URL}/download",
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=300 if media_type == "audio" else 600),
                ) as resp:
                    data = await resp.json(content_type=None)

                    if resp.status != 200:
                        logger.error(f"[INFLEX][{tag}] API returned HTTP {resp.status} → {data}")
                        return False
                    if data.get("status") == "error":
                        logger.error(f"[INFLEX][{tag}] API Error: {data.get('detail', 'Unknown error')}")
                        return False
                    if data.get("status") != "success" or not data.get("download_url"):
                        logger.error(f"[INFLEX][{tag}] Unexpected API response: {data}")
                        return False

                    download_link = f"{INFLEX_API_URL}{data['download_url']}"

                async with session.get(download_link) as file_resp:
                    if file_resp.status != 200:
                        logger.error(f"[INFLEX][{tag}] Download failed ({file_resp.status}) for ID: {vid}")
                        return False
                    with open(path, "wb") as f:
                        async for chunk in file_resp.content.iter_chunked(131072):
                            f.write(chunk)

            if os.path.exists(path) and os.path.getsize(path) > 0:
                logger.info(f"[INFLEX] {tag} download completed for {vid}")
                return True
            self._cleanup(path)
            return False

        except Exception as e:
            logger.error(f"[INFLEX][{tag}] Exception for ID {vid}: {e}")
            self._cleanup(path)
            return False

    async def _download_audio(self, video_id: str):
        vid = self._extract_id(video_id)
        if not vid or len(vid) < 3:
            return None

        os.makedirs(DOWNLOAD_DIR, exist_ok=True)
        path = os.path.join(DOWNLOAD_DIR, f"{vid}.mp3")
        if os.path.exists(path) and os.path.getsize(path) > 0:
            logger.info(f"🎵 [LOCAL] Found existing audio for ID {vid}")
            return path

        if await self._shruti_download(vid, "audio", path):
            return path

        logger.warning(f"[AUDIO] Shruti failed for {vid}, trying Inflex fallback...")
        if await self._inflex_download(vid, "audio", path):
            return path

        logger.error(f"[AUDIO] All backends failed for ID: {vid}")
        return None

    async def _download_video(self, video_id: str):
        vid = self._extract_id(video_id)
        if not vid or len(vid) < 3:
            return None

        os.makedirs(DOWNLOAD_DIR, exist_ok=True)
        path = os.path.join(DOWNLOAD_DIR, f"{vid}.mp4")
        if os.path.exists(path) and os.path.getsize(path) > 0:
            logger.info(f"🎥 [LOCAL] Found existing video for ID {vid}")
            return path

        if await self._shruti_download(vid, "video", path):
            return path

        logger.warning(f"[VIDEO] Shruti failed for {vid}, trying Inflex fallback...")
        if await self._inflex_download(vid, "video", path):
            return path

        logger.error(f"[VIDEO] All backends failed for ID: {vid}")
        return None

    async def download(self, video_id: str, video: bool = False):
        if video:
            return await self._download_video(video_id)
        return await self._download_audio(video_id)
