import aiohttp
import re
import mimetypes
import io
from typing import Tuple, Any, Type
from maubot import Plugin, MessageEvent
from maubot.handlers import command
from mautrix.types import (MessageType, EventID, ContentURI, TextMessageEventContent, MediaMessageEventContent,
                           MessageEventContent, Format, VideoInfo, ThumbnailInfo)
from mautrix.util.config import BaseProxyConfig, ConfigUpdateHelper
from time import gmtime
from time import strftime
from PIL import Image


class MessageData:
    def __init__(self, html: str, body: str, video_url: str, image_url: str):
        self.html: str = html
        self.body: str = body
        self.video_url: str = video_url
        self.image_url: str = image_url


class Config(BaseProxyConfig):
    def do_update(self, helper: ConfigUpdateHelper) -> None:
        helper.copy("preview_size")
        helper.copy("api_key")
        helper.copy("mute")
        helper.copy("cut_borders")
        helper.copy("max_results")


class AnimeTraceBot(Plugin):
    size_limit = 25000000  # 25 MB
    api_url = "https://api.trace.moe/search?anilistInfo"
    api_me = "https://api.trace.moe/me"
    headers = {
        "User-Agent": "AnimeTraceBot/1.2.0"
   }

    async def start(self) -> None:
        await super().start()
        self.config.load_and_update()
        if self.get_cut_borders():
            self.api_url += "&cutBorders"
        if self.config.get("api_key", ""):
            self.headers["x-trace-key"] = self.config["api_key"]

    @command.new(name="trace", help="Trace back the scene from an anime screenshot", require_subcommand=False, arg_fallthrough=False,
                 msgtypes=[MessageType.TEXT, MessageType.IMAGE, MessageType.VIDEO])
    @command.argument("query", pass_raw=True, required=False, matches=r"(https?://\S+)")
    async def trace(self, evt: MessageEvent, query: Tuple[str, Any]) -> None:
        await evt.mark_read()

        # Get ID of the message user replied to
        event_id = evt.content.get_reply_to()
        if not event_id and not query and evt.content.msgtype == MessageType.TEXT:
            await evt.reply("**Usage:**  \n"
                            "In reply to the message that contains a screenshot or link to a screenshot: `!trace`  \n"
                            "In a message that contains a link to a screenshot: `!trace <link>`  \n"
                            "In a message that contains a screenshot as an attachment: `!trace`  \n"
                            "To check the search quota and limit: `!trace quota`")
            return

        media_external_url, media_url, content_type = await self.extract_media_url(evt, event_id, query)

        if media_external_url:
            try:
                trace_json = await self.trace_by_external_url(media_external_url)
            except Exception as e:
                await evt.reply(f"{e}")
                return
        else:
            try:
                trace_json = await self.trace_by_media(media_url, content_type)
            except Exception as e:
                await evt.reply(f"{e}")
                return

        message = await self.prepare_message(trace_json)
        if message:
            await evt.reply(message)
        else:
            await evt.reply("Couldn't find an anime based on the provided screenshot/video.")

    async def extract_media_url(self, evt: MessageEvent, event_id: EventID, query: Tuple[str, Any]) -> Tuple[str, str, str]:
        media_external_url = ""
        media_url = ""
        content_type = ""
        # User requested to analyze the content of the message with the ID obtained in the previous step
        if event_id:
            # Get message for analysis
            message: MessageEvent = await self.client.get_event(room_id=evt.room_id, event_id=event_id)
            if message.content.msgtype == MessageType.TEXT:
                media_external_url = re.search(r"(https?://\S+)", message.content.body, re.I)
                media_external_url = media_external_url.group(1) if media_external_url else None
            else:
                media_url = message.content.url
                content_type = message.content.info.mimetype
        # User requested to analyze the content of their own message
        else:
            if evt.content.msgtype == MessageType.TEXT:
                if query:
                    media_external_url = query[0]
            else:
                media_url = evt.content.url
                content_type = evt.content.info.mimetype
        return media_external_url, media_url, content_type

    async def trace_by_external_url(self, media_url: str) -> Any:
        # Check the headers for size and type
        try:
            response = await self.http.head(media_url, raise_for_status=True)
            content_type = response.content_type
            content_length = response.content_length
        except aiohttp.ClientError as e:
            self.log.error(f"Connection failed during checks of image from external URL: {e}")
            raise Exception("Could not validate file from external URL") from e

        # Verify if content conforms trace.moe requirements
        if content_length > self.size_limit:
            self.log.error(f"External image size too big: {content_length}")
            raise Exception(f"External image size too big: {content_length} bytes")
        if not content_type.startswith("image/") and not content_type.startswith("video/"):
            self.log.error(f"External file type not supported: {content_type}")
            raise Exception(f"External file type not supported: {content_type}")

        # Send request as a link
        params = {
            "url": media_url
        }
        try:
            response = await self.http.get(self.api_url, headers=self.headers, params=params, raise_for_status=True)
            response_json = await response.json()
            return response_json
        except aiohttp.ClientError as e:
            self.log.error(f"Connection to trace.moe API failed: {e}")
            raise Exception("Connection to trace.moe API failed.") from e

    async def trace_by_media(self, media_url: str, content_type: str) -> str:
        # Download media file from Matrix server first
        try:
            data = await self.client.download_media(ContentURI(media_url))
        except Exception as e:
            self.log.error(f"Media download from Matrix server failed: {e}")
            raise Exception("Media download from Matrix server failed.") from e

        headers = self.headers.copy()
        headers["Content-Type"] = content_type
        try:
            response = await self.http.post(self.api_url, data=data, headers=headers, raise_for_status=True)
            response_json = await response.json()
            return response_json
        except aiohttp.ClientError as e:
            self.log.error(f"Connection to trace.moe API failed: {e}")
            raise Exception("Connection to trace.moe API failed.") from e

    async def prepare_message_content(self, data: Any) -> MessageData:
        body = ""
        html = ""
        video_url = ""
        image_url = ""
        if data["error"]:
            self.log.error(f"{data["error"]}")
        elif len(data["result"]) > 0:
            result = data["result"][0]
            video_url = result["video"]
            image_url = result["image"]
            tfrom = strftime("%H:%M:%S", gmtime(result["from"]))
            tto = strftime("%H:%M:%S", gmtime(result["to"]))

            # Title Romaji
            html = (
                f"<div>"
                f"<blockquote>"
                f"<a href=\"https://anilist.co/anime/{result["anilist"]["id"]}\">"
                f"<h3>{result["anilist"]["title"]["romaji"]}</h3>"
                f"</a>"
            )
            body = (
                f"> ### [{result["anilist"]["title"]["romaji"]}](https://anilist.co/anime/{result["anilist"]["id"]})  \n"
                f"> \n"
            )

            # Title English
            if result["anilist"]["title"]["english"]:
                html += f"<blockquote><b>English title:</b> {result["anilist"]["title"]["english"]}</blockquote>"
                body += (
                    f"> > **English title:** {result["anilist"]["title"]["english"]}  \n"
                )

            # AniList, MyAnimeList links
            html += (
                f"<blockquote>"
                f"<a href=\"https://anilist.co/anime/{result["anilist"]["id"]}\">AniList</a>, "
                f"<a href=\"https://myanimelist.net/anime/{result["anilist"]["idMal"]}\">MyAnimeList</a>"
                f"</blockquote>"
            )
            body += (
                f"> > [AniList](https://anilist.co/anime/{result["anilist"]["id"]}), "
                f"[MyAnimeList](https://myanimelist.net/anime/{result["anilist"]["idMal"]})  \n"
            )

            # Alternative titles
            if result["anilist"]["synonyms"]:
                html += f"<blockquote><b>Alternative titles:</b> {", ".join(result["anilist"]["synonyms"])}</blockquote>"
                body += f"> > **Alternative titles:** {", ".join(result["anilist"]["synonyms"])}  \n"

            # Similarity, filename, episode, time
            html += (
                f"<blockquote><b>Similarity:</b> {"{:.2f}".format(result["similarity"] * 100)}%</blockquote>"
                f"<blockquote><b>Filename:</b> {result["filename"]}</blockquote>"
                f"<blockquote><b>Episode:</b> {result["episode"] if result["episode"] else "-"}</blockquote>"
                f"<blockquote><b>Time :</b> {tfrom} - {tto}</blockquote>"
            )
            body += (
                f"> > **Similarity:** {"{:.2f}".format(result["similarity"] * 100)}%  \n"
                f"> > **Filename:** {result["filename"]}  \n"
                f"> > **Episode:** {result["episode"] if result["episode"] else "-"}  \n"
                f"> > **Time:** {tfrom} - {tto}  \n"
                f"> \n"
            )

            # Other results
            max_results = self.get_max_results()
            if len(data["result"]) > 1 and max_results > 1:
                html += (
                    f"<details>"
                    f"<br><summary><b>Other results:</b></summary>"
                )
                body += f"> **Other results:**  \n"
            end = max_results if len(data["result"]) >= max_results else len(data["result"])
            for i in range(1, end):
                result = data["result"][i]
                tfrom = strftime("%H:%M:%S", gmtime(result["from"]))
                tto = strftime("%H:%M:%S", gmtime(result["to"]))
                html += (
                    f"<blockquote>"
                    f"{i}. <a href=\"https://anilist.co/anime/{result["anilist"]["id"]}\">"
                    f"{result["anilist"]["title"]["english"] if result["anilist"]["title"]["english"] else result["anilist"]["title"]["romaji"]}</a>"
                    f" (<a href=\"https://myanimelist.net/anime/{result["anilist"]["idMal"]}\">MAL</a>)"
                    f" <b>S:</b> {"{:.2f}".format(result["similarity"] * 100)}%,"
                    f"{(" <b>Ep:</b> " + str(result["episode"]) + ",") if result["episode"] else ""}"
                    f" <b>T:</b> {tfrom} - {tto}"
                    f"</blockquote>"
                )
                body += (
                    f"> > {i}. [{result["anilist"]["title"]["english"] if result["anilist"]["title"]["english"] else result["anilist"]["title"]["romaji"]}]"
                    f"(https://anilist.co/anime/{result["anilist"]["id"]})"
                    f" ([MAL](https://myanimelist.net/anime/{result["anilist"]["idMal"]}))"
                    f" **S:** {"{:.2f}".format(result["similarity"] * 100)}%,"
                    f" {(" **Ep:** " + str(result["episode"]) + ",") if result["episode"] else ""}"
                    f" **T:** {tfrom} - {tto}  \n"
                )

            # Footer
            html += (
                f"</details>"
                f"<p><b><sub>Results from trace.moe</sub></b></p>"
                f"</blockquote>"
                f"</div>"
            )
            body += (
                f"> \n"
                f"> > **Results from trace.moe**"
            )

        return MessageData(
            html=html,
            body=body,
            video_url=video_url,
            image_url=image_url
        )

    async def prepare_message(self, data: Any) -> MessageEventContent | None:
        msg_data = await self.prepare_message_content(data)
        content = None
        video = None
        image = None
        video_type = None
        video_duration = 0
        image_type = None
        params = {
            "size": self.get_preview_size()
        }
        if msg_data.video_url:
            if self.get_mute():
                msg_data.video_url += "&mute"
            try:
                response = await self.http.get(msg_data.video_url, headers=self.headers, params=params, raise_for_status=True)
                video_type = response.content_type
                video_start = float(response.headers.get("x-video-start", 0))
                video_end = float(response.headers.get("x-video-end", 0))
                video_duration = int((video_end - video_start) * 1000)
                video = await response.read()
            except aiohttp.ClientError as e:
                self.log.error(f"Error downloading video preview from API: {e}")
            try:
                response = await self.http.get(msg_data.image_url, headers=self.headers, params=params, raise_for_status=True)
                image_type = response.content_type
                image = await response.read()
            except aiohttp.ClientError as e:
                self.log.error(f"Error downloading video thumbnail from API: {e}")

        if video:
            height = 360
            width = 640
            try:
                img = Image.open(io.BytesIO(image))
                height = img.height
                width = img.width
            except Exception as e:
                self.log.error(f"Error reading image dimensions: {e}")
            try:
                video_extension = mimetypes.guess_extension(video_type)
                image_extension = mimetypes.guess_extension(image_type)
                video_uri = await self.client.upload_media(
                    data=video,
                    mime_type=video_type,
                    filename=f"anime-preview{video_extension}",
                    size=len(video))
                image_uri = await self.client.upload_media(
                    data=image,
                    mime_type=image_type,
                    filename=f"anime-preview-thumbnail{image_extension}",
                    size=len(image))
                content = MediaMessageEventContent(
                    format=Format.HTML,
                    formatted_body=msg_data.html,
                    url=video_uri,
                    body=msg_data.body,
                    filename=f"anime-preview{video_extension}",
                    msgtype=MessageType.VIDEO,
                    external_url=msg_data.video_url,
                    info=VideoInfo(
                        mimetype=video_type,
                        size=len(video),
                        duration=video_duration,
                        height=height,
                        width=width,
                        thumbnail_url=image_uri,
                        thumbnail_info=ThumbnailInfo(
                            mimetype=image_type,
                            size=len(image),
                            height=height,
                            width=width
                        )
                    )
                )
            except Exception as e:
                self.log.error(f"Error uploading video preview to Matrix server: {e}")
        elif msg_data.html:
            content = TextMessageEventContent(
                msgtype=MessageType.NOTICE,
                format=Format.HTML,
                body=msg_data.body,
                formatted_body=msg_data.html
            )
        return content

    @trace.subcommand("quota", help="Check the search quota and limit")
    async def check_quota(self, evt: MessageEvent) -> None:
        await evt.mark_read()
        try:
            response = await self.http.get(self.api_me, headers=self.headers, raise_for_status=True)
            response_json = await response.json()
            body = (
                f"> ### trace.moe quota  \n"
                f"> **Priority:** {response_json['priority']}  \n"
                f"> **Concurrency:** {response_json['concurrency']}  \n"
                f"> **Quota:** {response_json['quota']}  \n"
                f"> **Quota used:** {response_json['quotaUsed']}"
            )
            html = (
                f"<blockquote>"
                f"<h3>trace.moe quota</h3>"
                f"<p><b>Priority:</b> {response_json['priority']}"
                f"<br><b>Concurrency:</b> {response_json['concurrency']}"
                f"<br><b>Quota:</b> {response_json['quota']}"
                f"<br><b>Quota used:</b> {response_json['quotaUsed']}"
                f"</p></blockquote>"
            )

            content = TextMessageEventContent(
                msgtype=MessageType.NOTICE,
                format=Format.HTML,
                body=body,
                formatted_body=html
            )
            await evt.reply(content)
        except aiohttp.ClientError as e:
            self.log.error(f"Connection to trace.moe API failed: {e}")
            await evt.reply("Connection to trace.moe API failed")

    def get_preview_size(self) -> str:
        base_preview_sizes = ["s", "m", "l"]
        size = self.config.get("preview_size", "m")
        if size in base_preview_sizes:
            return size
        return "m"

    def get_mute(self) -> bool:
        base_mute = {
            "yes": True,
            "no": False
        }
        return base_mute.get(self.config.get("mute", "no"), base_mute["no"])

    def get_cut_borders(self) -> bool:
        base_cut_borders = {
            "yes": True,
            "no": False
        }
        return base_cut_borders.get(self.config.get("cut_borders", "yes"), base_cut_borders["yes"])

    def get_max_results(self) -> int:
        try:
            max_results = int(self.config.get("max_results", 5))
            max_results = 1 if max_results < 1 else max_results
        except ValueError:
            self.log.error("Incorrect 'max_results' config value. Setting default value of 5.")
            max_results = 5
        return max_results

    @classmethod
    def get_config_class(cls) -> Type[BaseProxyConfig]:
        return Config
