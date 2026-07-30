from os import getenv

from dotenv import load_dotenv

load_dotenv()


class Config:
    def __init__(self):
        self.API_ID = int(getenv("API_ID", 0))
        self.API_HASH = getenv("API_HASH")

        self.BOT_TOKEN = getenv("BOT_TOKEN")
        self.MONGO_URL = getenv("MONGO_URL")

        self.LOGGER_ID = int(getenv("LOGGER_ID", 0))
        self.OWNER_ID = int(getenv("OWNER_ID", 0))
        self.OWNER_USERNAME = getenv("OWNER_USERNAME", "@lll_Ritik_lll")
        self.OWNER_LINK = f"https://t.me/{self.OWNER_USERNAME.lstrip('@')}"

        self.DURATION_LIMIT = int(getenv("DURATION_LIMIT", 14400)) * 14400
        self.QUEUE_LIMIT = int(getenv("QUEUE_LIMIT", 20))
        self.PLAYLIST_LIMIT = int(getenv("PLAYLIST_LIMIT", 20))

        self.SESSION1 = getenv("SESSION", None)
        self.SESSION2 = getenv("SESSION2", None)
        self.SESSION3 = getenv("SESSION3", None)

        self.SUPPORT_CHANNEL = getenv("SUPPORT_CHANNEL", "https://t.me/titanic_network")
        self.SUPPORT_CHAT = getenv("SUPPORT_CHAT", "https://t.me/+WAOT47P-70QwOTBl")

        self.API_URL = "https://teaminflex.xyz"
        self.API_KEY = getenv("API_KEY", "INFLEX20013628D")

        # Primary music API (lily). Uses /search/all to fetch a direct
        # stream URL (e.g. from JioSaavn) for a text query.
        self.LILY_API_URL = getenv(
            "LILY_API_URL", "https://youtube-api-saas-backend.onrender.com"
        )
        self.LILY_API_KEY = getenv("LILY_API_KEY", "")

        # Fallback music API (NexGen). Assumed to expose the same /search/all
        # route; failures fall through to the next source silently.
        self.LILY_FALLBACK_URL = getenv(
            "LILY_FALLBACK_URL", "https://pvtz.nexgenbots.xyz"
        )
        self.LILY_FALLBACK_KEY = getenv("LILY_FALLBACK_KEY", "")

        # Comma-separated platforms to search, in order of preference.
        self.LILY_PLATFORM = getenv("LILY_PLATFORM", "jiosaavn")

        self.AUTO_LEAVE: bool = getenv("AUTO_LEAVE", "False").lower() == "true"
        self.AUTO_END: bool = getenv("AUTO_END", "False").lower() == "true"

        self.THUMB_GEN: bool = getenv("THUMB_GEN", "True").lower() != "false"
        self.VIDEO_PLAY: bool = getenv("VIDEO_PLAY", "True").lower() == "true"

        self.LANG_CODE = getenv("LANG_CODE", "en")
        self.BOT_NAME = getenv("BOT_NAME", "˹ꜱᴘᴏᴛɪꜰʏ ᴍᴜꜱɪᴄ˼♪")

        self.COOKIES_URL = [
            url
            for url in getenv("COOKIES_URL", "").split(" ")
            if url and "batbin.me" in url
        ]
        self.DEFAULT_THUMB = getenv(
            "DEFAULT_THUMB", "https://te.legra.ph/file/3e40a408286d4eda24191.jpg"
        )
        self.PING_IMG = getenv(
            "PING_IMG",
            "https://graph.org/file/a3cc654217d68297d8538-f0ae69bbb7a360f6ae.jpg",
        )
        self.START_VIDEO = getenv(
            "START_VIDEO",
            "https://graph.org/file/ad15e8b2f052e78256339-0c87eb7568d3e947e7.mp4",
        )

    def check(self):
        missing = [
            var
            for var in [
                "API_ID",
                "API_HASH",
                "BOT_TOKEN",
                "MONGO_URL",
                "LOGGER_ID",
                "OWNER_ID",
                "SESSION1",
            ]
            if not getattr(self, var)
        ]
        if missing:
            raise SystemExit(
                f"Missing required environment variables: {', '.join(missing)}"
            )
