import asyncio
import os
import re
from typing import Optional, Union
from urllib.parse import parse_qs, urlparse

import aiohttp
import yt_dlp
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message
from py_yt import VideosSearch, Playlist

# Notty credentials must be injected at runtime. Never commit an API key here.
NOTTY_API_URL = "https://nottybots.dev"
NOTTY_API_KEY = "ntapi_e5gBSzd_8A7Ze_nRTtb5c-FiB7kZxtZj1wjrDqGscjM"
DOWNLOAD_DIR = "downloads"
_API_SESSION: Optional[aiohttp.ClientSession] = None
_API_SESSION_LOCK = asyncio.Lock()


def time_to_seconds(time):
    stringt = str(time)
    return sum(int(x) * 60 ** i for i, x in enumerate(reversed(stringt.split(":"))))


def _video_source(link: str) -> str:
    """Return a safe YouTube video ID when obvious, otherwise preserve the URL."""
    source = (link or "").strip()
    if not source:
        return ""
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", source):
        return source
    try:
        parsed = urlparse(source)
        if parsed.netloc.endswith("youtu.be"):
            candidate = parsed.path.strip("/").split("/")[0]
        else:
            candidate = parse_qs(parsed.query).get("v", [""])[0]
        if re.fullmatch(r"[A-Za-z0-9_-]{11}", candidate):
            return candidate
    except ValueError:
        pass
    return source


async def _api_session() -> aiohttp.ClientSession:
    global _API_SESSION
    async with _API_SESSION_LOCK:
        if _API_SESSION is None or _API_SESSION.closed:
            _API_SESSION = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=900, connect=15),
                headers={"User-Agent": "NottyMusicBot/1.0"},
            )
        return _API_SESSION


async def close_notty_api_session() -> None:
    global _API_SESSION
    async with _API_SESSION_LOCK:
        if _API_SESSION is not None and not _API_SESSION.closed:
            await _API_SESSION.close()
        _API_SESSION = None


async def _resolve_media(media_type: str, link: str) -> Optional[dict]:
    if not NOTTY_API_URL or not NOTTY_API_KEY:
        return None
    session = await _api_session()
    source = _video_source(link)
    params = {"api_key": NOTTY_API_KEY}
    params["video_id" if re.fullmatch(r"[A-Za-z0-9_-]{11}", source) else "url"] = source
    endpoint = f"{NOTTY_API_URL}/api/{media_type}"
    for attempt in range(4):
        try:
            async with session.get(endpoint, params=params) as response:
                payload = await response.json(content_type=None)
                if response.status == 200 and isinstance(payload.get("url"), str):
                    return payload
                if response.status not in {408, 425, 429, 500, 502, 503, 504}:
                    return None
                retry_after = response.headers.get("Retry-After")
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError):
            retry_after = None
        if attempt < 3:
            try:
                delay = float(retry_after) if retry_after else min(8.0, 0.5 * (2**attempt))
            except ValueError:
                delay = min(8.0, 0.5 * (2**attempt))
            await asyncio.sleep(delay)
    return None


async def _download_resolved(media_type: str, link: str, default_ext: str, timeout: float) -> Optional[str]:
    media = await _resolve_media(media_type, link)
    if not media:
        return None
    source = _video_source(link)
    video_id = source if re.fullmatch(r"[A-Za-z0-9_-]{11}", source) else re.sub(r"[^A-Za-z0-9_-]", "_", source)[:80]
    extension = str(media.get("ext") or default_ext).lower().lstrip(".")
    final_path = os.path.join(DOWNLOAD_DIR, f"{video_id}.{extension}")
    partial_path = f"{final_path}.part"
    if os.path.exists(final_path) and os.path.getsize(final_path) > 0:
        return final_path
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    session = await _api_session()
    for attempt in range(3):
        offset = os.path.getsize(partial_path) if os.path.exists(partial_path) else 0
        headers = {"Range": f"bytes={offset}-"} if offset else {}
        try:
            async with session.get(media["url"], headers=headers, timeout=aiohttp.ClientTimeout(total=timeout, connect=15)) as response:
                if response.status not in {200, 206}:
                    if response.status in {408, 425, 429, 500, 502, 503, 504} and attempt < 2:
                        await asyncio.sleep(min(8.0, 0.5 * (2**attempt)))
                        continue
                    return None
                append = offset > 0 and response.status == 206
                mode = "ab" if append else "wb"
                with open(partial_path, mode) as output:
                    async for chunk in response.content.iter_chunked(256 * 1024):
                        output.write(chunk)
            if os.path.getsize(partial_path) <= 0:
                return None
            os.replace(partial_path, final_path)
            return final_path
        except (aiohttp.ClientError, asyncio.TimeoutError, OSError):
            if attempt < 2:
                await asyncio.sleep(min(8.0, 0.5 * (2**attempt)))
    return None


async def download_song(link: str) -> Optional[str]:
    return await _download_resolved("audio", link, "m4a", 600)


async def download_video(link: str) -> Optional[str]:
    return await _download_resolved("video", link, "mp4", 1800)


class YouTubeAPI:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.regex = r"(?:youtube\.com|youtu\.be)"
        self.status = "https://www.youtube.com/oembed?url="
        self.listbase = "https://youtube.com/playlist?list="
        self.reg = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")

    async def exists(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        return bool(re.search(self.regex, link))

    async def url(self, message_1: Message) -> Union[str, None]:
        messages = [message_1]
        if message_1.reply_to_message:
            messages.append(message_1.reply_to_message)
        for message in messages:
            if message.entities:
                for entity in message.entities:
                    if entity.type == MessageEntityType.URL:
                        text = message.text or message.caption
                        return text[entity.offset: entity.offset + entity.length]
            elif message.caption_entities:
                for entity in message.caption_entities:
                    if entity.type == MessageEntityType.TEXT_LINK:
                        return entity.url
        return None

    async def details(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            title = result["title"]
            duration_min = result["duration"]
            thumbnail = result["thumbnails"][0]["url"].split("?")[0]
            vidid = result["id"]
            duration_sec = int(time_to_seconds(duration_min)) if duration_min else 0
        return title, duration_min, duration_sec, thumbnail, vidid

    async def title(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            return result["title"]

    async def duration(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            return result["duration"]

    async def thumbnail(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            return result["thumbnails"][0]["url"].split("?")[0]

    async def video(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        try:
            downloaded_file = await download_video(link)
            if downloaded_file:
                return 1, downloaded_file
            return 0, "Video download failed"
        except Exception as e:
            return 0, f"Video download error: {e}"

    async def playlist(self, link, limit, user_id, videoid: Union[bool, str] = None):
        if videoid:
            link = self.listbase + link
        if "&" in link:
            link = link.split("&")[0]
        try:
            plist = await Playlist.get(link)
        except Exception:
            return []
        videos = plist.get("videos") or []
        ids = []
        for data in videos[:limit]:
            if not data:
                continue
            vid = data.get("id")
            if not vid:
                continue
            ids.append(vid)
        return ids

    async def track(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            title = result["title"]
            duration_min = result["duration"]
            vidid = result["id"]
            yturl = result["link"]
            thumbnail = result["thumbnails"][0]["url"].split("?")[0]
        track_details = {
            "title": title,
            "link": yturl,
            "vidid": vidid,
            "duration_min": duration_min,
            "thumb": thumbnail,
        }
        return track_details, vidid

    async def formats(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        ytdl_opts = {"quiet": True}
        ydl = yt_dlp.YoutubeDL(ytdl_opts)
        with ydl:
            formats_available = []
            r = ydl.extract_info(link, download=False)
            for format in r["formats"]:
                try:
                    if "dash" not in str(format["format"]).lower():
                        formats_available.append(
                            {
                                "format": format["format"],
                                "filesize": format.get("filesize"),
                                "format_id": format["format_id"],
                                "ext": format["ext"],
                                "format_note": format["format_note"],
                                "yturl": link,
                            }
                        )
                except Exception:
                    continue
        return formats_available, link

    async def slider(self, link: str, query_type: int, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        a = VideosSearch(link, limit=10)
        result = (await a.next()).get("result")
        title = result[query_type]["title"]
        duration_min = result[query_type]["duration"]
        vidid = result[query_type]["id"]
        thumbnail = result[query_type]["thumbnails"][0]["url"].split("?")[0]
        return title, duration_min, thumbnail, vidid

    async def download(
        self,
        link: str,
        mystic,
        video: Union[bool, str] = None,
        videoid: Union[bool, str] = None,
        songaudio: Union[bool, str] = None,
        songvideo: Union[bool, str] = None,
        format_id: Union[bool, str] = None,
        title: Union[bool, str] = None,
    ) -> str:
        if videoid:
            link = self.base + link
        try:
            if video:
                downloaded_file = await download_video(link)
            else:
                downloaded_file = await download_song(link)
            if downloaded_file:
                return downloaded_file, True
            return None, False
        except Exception:
            return None, False


YouTube = YouTubeAPI()
