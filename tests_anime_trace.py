import aiohttp
import asyncio
import unittest
import mautrix.types.event
from anime_trace.anime_trace import AnimeTraceBot
from anime_trace.resources.datastructures import MessageData
from maubot import MessageEvent
from maubot.matrix import MaubotMatrixClient
from mautrix.api import HTTPAPI
from mautrix.types import MessageType, EventID, ContentURI, TextMessageEventContent, MediaMessageEventContent, Format, ImageInfo
from mautrix.util.logging import TraceLogger
from unittest.mock import AsyncMock, MagicMock


class TestAnimeTraceBot(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.session = aiohttp.ClientSession()
        api = HTTPAPI(base_url="http://matrix.example.com", client_session=self.session)
        client = MaubotMatrixClient(api=api)
        self.bot = AnimeTraceBot(
            client=client,
            loop=asyncio.get_event_loop(),
            http=self.session,
            instance_id="matrix.example.com",
            log=TraceLogger("testlogger"),
            config=None,
            database=None,
            webapp=None,
            webapp_url=None,
            loader=None
        )
        self.api_response_data = {
            "frameCount": 745506,
            "error": "",
            "result": [
                {
                    "anilist": {
                        "id": 99939,
                        "idMal": 34658,
                        "title": {"native": "ネコぱらOVA", "romaji": "Nekopara OVA", "english": None},
                        "synonyms": ["Neko Para OVA"],
                        "isAdult": False
                    },
                    "filename": "Nekopara - OVA (BD 1280x720 x264 AAC).mp4",
                    "episode": None,
                    "from": 97.75,
                    "to": 98.92,
                    "similarity": 0.9440424588727485,
                    "video": "https://api.trace.moe/video/99939/Nekopara%20-%20OVA%20(BD%201280x720%20x264%20AAC).mp4?t=98.335&now=1653892514&token=xxxxxxxxxxxxxx",
                    "image": "https://api.trace.moe/image/99939/Nekopara%20-%20OVA%20(BD%201280x720%20x264%20AAC).mp4.jpg?t=98.335&now=1653892514&token=xxxxxxxxxxxxxx"
                }
            ]
        }

    async def asyncTearDown(self):
        await self.session.close()

    async def create_resp(self, status_code=200, json=None, resp_bytes=None, content_type=None, content_length=0):
        headers = {
            "x-video-start": 50,
            "x-video-end": 100,
        }
        resp = AsyncMock(status_code=status_code, content_type=content_type, content_length=content_length, headers=headers)
        resp.json.return_value = json
        resp.read.return_value = resp_bytes
        return resp

    async def test_extract_media_url_when_message_with_link_then_return_external_url(self):
        # Arrange
        url = "https://example.com/image.png"
        msg_event = MessageEvent(mautrix.types.event.message.MessageEvent(None, None, None, None, None, TextMessageEventContent()), self.bot.client)
        msg_event.content.msgtype = MessageType.TEXT

        # Act
        media_external_url, media_url, content_type = await self.bot.extract_media_url(msg_event, None, (url, ""))

        # Assert
        self.assertEqual(media_external_url, url)
        self.assertEqual(media_url, "")
        self.assertEqual(content_type, "")

    async def test_extract_media_url_when_message_with_attachment_then_return_internal_url_and_mimetype(self):
        # Arrange
        url = "https://example.com/image.png"
        mimetype = "image/png"
        msg_content = MediaMessageEventContent()
        msg_content.info = ImageInfo(mimetype=mimetype)
        msg_event = MessageEvent(mautrix.types.event.message.MessageEvent(None, None, None, None, None, msg_content), self.bot.client)
        msg_event.content.msgtype = MessageType.IMAGE
        msg_event.content.url = ContentURI(url)

        # Act
        media_external_url, media_url, content_type = await self.bot.extract_media_url(msg_event, None, ("", ""))

        # Assert
        self.assertEqual(media_external_url, "")
        self.assertEqual(media_url, url)
        self.assertEqual(content_type, mimetype)

    async def test_extract_media_url_when_reply_to_message_with_link_then_return_external_url(self):
        # Arrange
        url = "https://example.com/image.png"
        reply_event = MessageEvent(mautrix.types.event.message.MessageEvent(None, None, None, None, None, TextMessageEventContent()), self.bot.client)
        msg_event = MessageEvent(mautrix.types.event.message.MessageEvent(None, None, EventID("test_id"), None, None, TextMessageEventContent()), self.bot.client)
        msg_event.content.msgtype = MessageType.TEXT
        msg_event.content.body = f"!trace {url}"
        self.bot.client.get_event = AsyncMock(return_value=msg_event)

        # Act
        media_external_url, media_url, content_type = await self.bot.extract_media_url(reply_event, msg_event.event_id, (url, ""))

        # Assert
        self.assertEqual(media_external_url, url)
        self.assertEqual(media_url, "")
        self.assertEqual(content_type, "")

    async def test_extract_media_url_when_reply_to_message_with_attachment_then_return_internal_url_and_mimetype(self):
        # Arrange
        url = "https://example.com/image.png"
        mimetype = "image/png"
        msg_content = MediaMessageEventContent()
        msg_content.info = ImageInfo(mimetype=mimetype)
        msg_event = MessageEvent(mautrix.types.event.message.MessageEvent(None, None, EventID("test_id"), None, None, msg_content), self.bot.client)
        msg_event.content.msgtype = MessageType.IMAGE
        msg_event.content.url = ContentURI(url)
        self.bot.client.get_event = AsyncMock(return_value=msg_event)
        reply_event = MessageEvent(mautrix.types.event.message.MessageEvent(None, None, None, None, None, TextMessageEventContent()), self.bot.client)

        # Act
        media_external_url, media_url, content_type = await self.bot.extract_media_url(reply_event, msg_event.event_id, ("", ""))

        # Assert
        self.assertEqual(media_external_url, "")
        self.assertEqual(media_url, url)
        self.assertEqual(content_type, mimetype)

    async def test_trace_by_external_url_when_url_is_correct_then_return_json(self):
        # Arrange
        url = "https://example.com/image.png"
        json_data = {'test': 1}
        self.bot.http.get = AsyncMock(return_value=await self.create_resp(200, json=json_data))

        # Act
        json_response = await self.bot.trace_by_external_url(url)

        # Assert
        self.assertEqual(json_response, json_data)

    async def test_trace_by_external_url_when_aiohttp_error_then_raise_exception(self):
        # Arrange
        url = "https://example.com/image.png"
        self.bot.http.get = AsyncMock(side_effect=aiohttp.ClientError)

        # Assert
        with self.assertRaisesRegex(Exception, "Connection to trace.moe API failed"):
            # Act
            await self.bot.trace_by_external_url(url)

    async def test_validate_external_url_when_data_is_correct_then_return_None(self):
        # Arrange
        url = "https://example.com/image.png"
        content_types = ["image/png", "video/mp4"]
        for content_type in content_types:
            with self.subTest(content_type=content_type):
                self.bot.http.head = AsyncMock(return_value=await self.create_resp(200, content_type=content_type, content_length=self.bot.size_limit))

                # Act
                result = await self.bot.validate_external_url(url)

                # Assert
                self.assertEqual(result, None)

    async def test_validate_external_url_when_aiohttp_error_then_raise_exception(self):
        # Arrange
        url = "https://example.com/image.png"
        self.bot.http.head = AsyncMock(side_effect=aiohttp.ClientError)

        # Assert
        with self.assertRaisesRegex(Exception, "Could not validate file from external URL"):
            # Act
            await self.bot.validate_external_url(url)

    async def test_validate_external_url_when_wrong_content_type_then_raise_exception(self):
        # Arrange
        url = "https://example.com/image.png"
        self.bot.http.head = AsyncMock(return_value=await self.create_resp(200, content_type="text/html", content_length=self.bot.size_limit))

        # Assert
        with self.assertRaisesRegex(Exception, "External file type not supported"):
            # Act
            await self.bot.validate_external_url(url)

    async def test_validate_external_url_when_wrong_size_then_raise_exception(self):
        # Arrange
        url = "https://example.com/image.png"
        self.bot.http.head = AsyncMock(return_value=await self.create_resp(200, content_type="image/png", content_length=self.bot.size_limit + 1))

        # Assert
        with self.assertRaisesRegex(Exception, "External image size too big"):
            # Act
            await self.bot.validate_external_url(url)

    async def test_get_matrix_media_when_successful_then_return_byte_data(self):
        # Arrange
        url = "mxc://matrix.example.com/image.png"
        bytes_data = b"image_data"
        self.bot.client.download_media = AsyncMock(return_value=bytes_data)

        # Act
        data = await self.bot.get_matrix_media(url)

        # Assert
        self.assertEqual(data, bytes_data)
        self.assertEqual(type(data), bytes)

    async def test_get_matrix_media_when_download_fails_then_raise_exception(self):
        # Arrange
        url = "mxc://matrix.example.com/image.png"
        self.bot.client.download_media = AsyncMock(side_effect=Exception)

        # Assert
        with self.assertRaisesRegex(Exception, "Media download from Matrix server failed"):
            # Act
            await self.bot.get_matrix_media(url)

    async def test_trace_by_media_when_request_is_successful_then_return_json(self):
        # Arrange
        bytes_data = b"image_data"
        content_type = "image/png"
        json_data = {'test': 1}
        self.bot.http.post = AsyncMock(return_value=await self.create_resp(200, json=json_data))

        # Act
        json_response = await self.bot.trace_by_media(bytes_data, content_type)

        # Assert
        self.assertEqual(json_response, json_data)

    async def test_trace_by_media_when_aiohttp_error_then_raise_exception(self):
        # Arrange
        bytes_data = bytes("image_data", 'utf-8')
        content_type = "image/png"
        self.bot.http.post = AsyncMock(side_effect=aiohttp.ClientError)

        # Assert
        with self.assertRaisesRegex(Exception, "Connection to trace.moe API failed"):
            # Act
            await self.bot.trace_by_media(bytes_data, content_type)

    async def test_prepare_message_content_when_correct_data_provided_then_return_message_data(self):
        # Arrange
        self.bot.get_max_results = MagicMock(return_value=5)

        # Act
        message_data = await self.bot.prepare_message_content(self.api_response_data)

        # Assert
        self.assertEqual(message_data.video_url, self.api_response_data["result"][0]["video"])
        self.assertEqual(message_data.image_url, self.api_response_data["result"][0]["image"])

    async def test_prepare_message_content_when_error_then_return_empty_MessageData(self):
        # Arrange
        data = {
            "error": "File not found",
            "result": []
        }
        self.bot.get_max_results = MagicMock(return_value=5)

        # Act
        message_data = await self.bot.prepare_message_content(data)

        # Assert
        self.assertEqual(message_data.video_url, "")
        self.assertEqual(message_data.image_url, "")
        self.assertEqual(message_data.body, "")
        self.assertEqual(message_data.html, "")

    async def test_prepare_message_content_when_zero_results_then_return_empty_MessageData(self):
        # Arrange
        data = {
            "error": None,
            "result": []
        }
        self.bot.get_max_results = MagicMock(return_value=5)

        # Act
        message_data = await self.bot.prepare_message_content(data)

        # Assert
        self.assertEqual(message_data.video_url, "")
        self.assertEqual(message_data.image_url, "")
        self.assertEqual(message_data.body, "")
        self.assertEqual(message_data.html, "")

    async def get_video_image(self, **kwargs):
        if kwargs.get("mime_type") == "image/png":
            return "image_url"
        elif kwargs.get("mime_type") == "video/mp4":
            return "video_url"

    async def test_prepare_message_when_correct_data_provided_then_return_MediaMessageEventContent(self):
        # Arrange
        # white 10x10 png rectangle
        image = (b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\n\x00\x00\x00\n\x08\x06\x00\x00\x00\x8d2\xcf\xbd\x00'
                 b'\x00\x00\tpHYs\x00\x00\x0e\xc4\x00\x00\x0e\xc4\x01\x95+\x0e\x1b\x00\x00\x00\x18IDAT\x18\x95c\xfc\xff'
                 b'\xff\xff\x7f\x06"\x00\x131\x8aF\x15RO!\x00i\x9a\x04\x10\x8a\x8d\x0bh\x00\x00\x00\x00IEND\xaeB`\x82')
        duration = 2000
        width = 10
        height = 10
        video_mime = "video/mp4"
        image_mime = "image/png"
        video = b"video_data"
        self.bot.get_max_results = MagicMock(return_value=5)
        self.bot.get_mute = MagicMock(return_value=False)
        self.bot.get_video_preview = AsyncMock(return_value=(video, video_mime, duration))
        self.bot.get_preview_thumbnail = AsyncMock(return_value=(image, image_mime))
        self.bot.client.upload_media = AsyncMock(side_effect=self.get_video_image)
        msg_data = MessageData(
            body="Body text",
            html="HTML text",
            video_url="https://example.com/video.mp4",
            image_url="https://example.com/image.png"
        )

        # Act
        message_data = await self.bot.prepare_message(msg_data)

        # Assert
        self.assertEqual(type(message_data), MediaMessageEventContent)
        self.assertEqual(message_data.msgtype, MessageType.VIDEO)
        self.assertEqual(message_data.body, msg_data.body)
        self.assertEqual(message_data.format, Format.HTML)
        self.assertEqual(message_data.formatted_body, msg_data.html)
        self.assertEqual(message_data.external_url, msg_data.video_url)
        self.assertEqual(message_data.url, "video_url")
        self.assertEqual(message_data.filename, "anime-preview.mp4")
        self.assertEqual(message_data.info.mimetype, video_mime)
        self.assertEqual(message_data.info.size, len(video))
        self.assertEqual(message_data.info.duration, duration)
        self.assertEqual(message_data.info.height, height)
        self.assertEqual(message_data.info.width, width)
        self.assertEqual(message_data.info.thumbnail_url, "image_url")
        self.assertEqual(message_data.info.thumbnail_info.mimetype, image_mime)
        self.assertEqual(message_data.info.thumbnail_info.size, len(image))
        self.assertEqual(message_data.info.thumbnail_info.height, height)
        self.assertEqual(message_data.info.thumbnail_info.width, width)

    async def test_prepare_message_when_cannot_detect_image_dimensions_then_return_MediaMessageEventContent_with_default_size(self):
        # Arrange
        image = (b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\n\x00\x00\x00\n\x08\x06\x00\x00\x00\x8d2\xcf\xbd\x00'
                 b'\x00\x00\tpHYs\x00\x00\x0e\xc4\x00\x00\x0e\xc4\x01\x95+\x0e\x1b\x00\x00\x00\x18IDAT\x18\x95c\xfc\xff'
                 b'\xff\xff\x7f\x06"\x00\x131\x8aF\x15RO!\x00i\x9a\x04\x10\x8a\x8d\x0bh\x00\x00\x00\x00IEND\xaeB`\x82')
        duration = 2000
        video_mime = "video/mp4"
        image_mime = "image/png"
        video = b"video_data"
        self.bot.get_image_dimensions = MagicMock(side_effect=Exception)
        self.bot.get_max_results = MagicMock(return_value=5)
        self.bot.get_mute = MagicMock(return_value=False)
        self.bot.get_video_preview = AsyncMock(return_value=(video, video_mime, duration))
        self.bot.get_preview_thumbnail = AsyncMock(return_value=(image, image_mime))
        self.bot.client.upload_media = AsyncMock(side_effect=self.get_video_image)
        msg_data = MessageData(
            body="Body text",
            html="HTML text",
            video_url="https://example.com/video.mp4",
            image_url="https://example.com/image.png"
        )

        # Act
        message_data = await self.bot.prepare_message(msg_data)

        # Assert
        self.assertEqual(type(message_data), MediaMessageEventContent)
        self.assertEqual(message_data.msgtype, MessageType.VIDEO)
        self.assertEqual(message_data.body, msg_data.body)
        self.assertEqual(message_data.format, Format.HTML)
        self.assertEqual(message_data.formatted_body, msg_data.html)
        self.assertEqual(message_data.external_url, msg_data.video_url)
        self.assertEqual(message_data.url, "video_url")
        self.assertEqual(message_data.filename, "anime-preview.mp4")
        self.assertEqual(message_data.info.mimetype, video_mime)
        self.assertEqual(message_data.info.size, len(video))
        self.assertEqual(message_data.info.duration, duration)
        self.assertEqual(message_data.info.height, 360)
        self.assertEqual(message_data.info.width, 640)
        self.assertEqual(message_data.info.thumbnail_url, "image_url")
        self.assertEqual(message_data.info.thumbnail_info.mimetype, image_mime)
        self.assertEqual(message_data.info.thumbnail_info.size, len(image))
        self.assertEqual(message_data.info.thumbnail_info.height, 360)
        self.assertEqual(message_data.info.thumbnail_info.width, 640)

    async def test_prepare_message_when_correct_data_but_no_video_then_return_TextMessageEventContent(self):
        # Arrange
        self.bot.get_max_results = MagicMock(return_value=5)
        msg_data = MessageData(
            body="Body text",
            html="HTML text",
            video_url="",
            image_url=""
        )

        # Act
        message_data = await self.bot.prepare_message(msg_data)

        # Assert
        self.assertEqual(type(message_data), TextMessageEventContent)
        self.assertEqual(message_data.msgtype, MessageType.NOTICE)
        self.assertEqual(message_data.body, msg_data.body)
        self.assertEqual(message_data.format, Format.HTML)
        self.assertEqual(message_data.formatted_body, msg_data.html)

    async def test_prepare_message_when_uploading_image_to_matrix_failed_then_return_TextMessageEventContent(self):
        # Arrange
        # white 10x10 png rectangle
        image = (b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\n\x00\x00\x00\n\x08\x06\x00\x00\x00\x8d2\xcf\xbd\x00'
                 b'\x00\x00\tpHYs\x00\x00\x0e\xc4\x00\x00\x0e\xc4\x01\x95+\x0e\x1b\x00\x00\x00\x18IDAT\x18\x95c\xfc\xff'
                 b'\xff\xff\x7f\x06"\x00\x131\x8aF\x15RO!\x00i\x9a\x04\x10\x8a\x8d\x0bh\x00\x00\x00\x00IEND\xaeB`\x82')
        duration = 2000
        video_mime = "video/mp4"
        image_mime = "image/png"
        video = b"video_data"
        self.bot.get_max_results = MagicMock(return_value=5)
        self.bot.get_mute = MagicMock(return_value=False)
        self.bot.get_video_preview = AsyncMock(return_value=(video, video_mime, duration))
        self.bot.get_preview_thumbnail = AsyncMock(return_value=(image, image_mime))
        self.bot.client.upload_media = AsyncMock(side_effect=Exception)
        msg_data = MessageData(
            body="Body text",
            html="HTML text",
            video_url="https://example.com/video.mp4",
            image_url="https://example.com/image.png"
        )

        # Act
        message_data = await self.bot.prepare_message(msg_data)

        # Assert
        self.assertEqual(type(message_data), TextMessageEventContent)
        self.assertEqual(message_data.msgtype, MessageType.NOTICE)
        self.assertEqual(message_data.body, msg_data.body)
        self.assertEqual(message_data.format, Format.HTML)
        self.assertEqual(message_data.formatted_body, msg_data.html)

    async def test_prepare_message_when_no_video_then_return_TextMessageEventContent(self):
        # Arrange
        msg_data = MessageData(
            body="Body text",
            html="HTML text",
            video_url="",
            image_url=""
        )
        self.bot.get_max_results = MagicMock(return_value=5)

        # Act
        message_data = await self.bot.prepare_message(msg_data)

        # Assert
        self.assertEqual(type(message_data), TextMessageEventContent)
        self.assertEqual(message_data.msgtype, MessageType.NOTICE)
        self.assertEqual(message_data.body, msg_data.body)
        self.assertEqual(message_data.formatted_body, msg_data.html)

    async def test_prepare_message_when_incorrect_data_provided_then_return_None(self):
        # Arrange
        msg_data = MessageData(
            body="",
            html="",
            video_url="",
            image_url=""
        )
        self.bot.get_max_results = MagicMock(return_value=5)

        # Act
        message_data = await self.bot.prepare_message(msg_data)

        # Assert
        self.assertEqual(message_data, None)

    async def test_get_video_preview_when_success_then_return_valid_data(self):
        # Arrange
        self.bot.get_preview_size = MagicMock(return_value="l")
        self.bot.get_mute = MagicMock(return_value=True)
        video_data = b"video_data"
        content_type = "video/mp4"
        self.bot.http.get = AsyncMock(return_value=await self.create_resp(200, content_type=content_type, resp_bytes=video_data))

        # Act
        video, video_type, video_duration = await self.bot.get_video_preview("https://example.com/video.mp4")

        # Assert
        self.assertEqual(video, video_data)
        self.assertEqual(video_type, content_type)
        self.assertEqual(video_duration, 50000)

    async def test_get_video_preview_when_exception_then_return_empty_values(self):
        # Arrange
        self.bot.get_preview_size = MagicMock(return_value="l")
        self.bot.get_mute = MagicMock(return_value=True)
        self.bot.http.get = AsyncMock(side_effect=aiohttp.ClientError)

        # Act
        video, video_type, video_duration = await self.bot.get_video_preview("https://example.com/video.mp4")

        # Assert
        self.assertEqual(video, b"")
        self.assertEqual(video_type, "")
        self.assertEqual(video_duration, 0)

    async def test_get_preview_thumbnail_when_success_then_return_valid_data(self):
        # Arrange
        self.bot.get_preview_size = MagicMock(return_value="l")
        image_data = b"image_data"
        content_type = "video/mp4"
        self.bot.http.get = AsyncMock(return_value=await self.create_resp(200, content_type=content_type, resp_bytes=image_data))

        # Act
        image, image_type = await self.bot.get_preview_thumbnail("https://example.com/image.png")

        # Assert
        self.assertEqual(image, image_data)
        self.assertEqual(image_type, content_type)

    async def test_get_preview_thumbnail_when_exception_then_return_empty_values(self):
        # Arrange
        self.bot.get_preview_size = MagicMock(return_value="l")
        self.bot.http.get = AsyncMock(side_effect=aiohttp.ClientError)

        # Act
        image, image_type = await self.bot.get_preview_thumbnail("https://example.com/image.png")

        # Assert
        self.assertEqual(image, b"")
        self.assertEqual(image_type, "")

    async def test_get_quota_when_success_then_return_valid_data(self):
        # Arrange
        json = {"test": 1}
        self.bot.http.get = AsyncMock(return_value=await self.create_resp(200, json=json))

        # Act
        result = await self.bot.get_quota()

        # Assert
        self.assertEqual(result, json)

    async def test_get_quota_when_exception_then_return_None(self):
        # Arrange
        self.bot.http.get = AsyncMock(side_effect=aiohttp.ClientError)

        # Act
        result = await self.bot.get_quota()

        # Assert
        self.assertEqual(result, None)

    async def test_prepare_message_quota_return_TextMessageEventContent(self):
        # Arrange
        data = {
          "id": "127.0.0.1",
          "priority": 0,
          "concurrency": 1,
          "quota": 1000,
          "quotaUsed": 43
        }
        # Act
        result = await self.bot.prepare_message_quota(data)

        # Assert
        self.assertEqual(type(result), TextMessageEventContent)
        self.assertEqual(result.msgtype, MessageType.NOTICE)

    async def test_get_preview_size(self):
        # Arrange
        config = (
            ({"preview_size": "s"}, "s"),
            ({"preview_size": "m"}, "m"),
            ({"preview_size": "l"}, "l"),
            ({"preview_size": ""}, "m"),
            ({"preview_size": "z"}, "m"),
            ({"ppreview_size": "l"}, "m")
        )
        for config_dict, expected_result in config:
            with self.subTest(config_dict=config_dict, expected_result=expected_result):
                self.bot.config = config_dict

                # Act
                result = self.bot.get_preview_size()

                # Assert
                self.assertEqual(result, expected_result)

    async def test_get_mute(self):
        # Arrange
        config = (
            ({"mute": "yes"}, True),
            ({"mute": "no"}, False),
            ({"mute": "dunno"}, False),
            ({"mute": ""}, False),
            ({"mmute": "yes"}, False)
        )
        for config_dict, expected_result in config:
            with self.subTest(config_dict=config_dict, expected_result=expected_result):
                self.bot.config = config_dict

                # Act
                result = self.bot.get_mute()

                # Assert
                self.assertEqual(result, expected_result)

    async def test_get_cut_borders(self):
        # Arrange
        config = (
            ({"cut_borders": "yes"}, True),
            ({"cut_borders": "no"}, False),
            ({"cut_borders": "dunno"}, True),
            ({"cut_borders": ""}, True),
            ({"ccut_borders": "yes"}, True)
        )
        for config_dict, expected_result in config:
            with self.subTest(config_dict=config_dict, expected_result=expected_result):
                self.bot.config = config_dict

                # Act
                result = self.bot.get_cut_borders()

                # Assert
                self.assertEqual(result, expected_result)

    async def test_get_max_results(self):
        # Arrange
        config = (
            ({"max_results": "string"}, 5),
            ({"max_results": -5}, 1),
            ({"max_results": 0}, 1),
            ({"max_results": 3}, 3),
            ({"mmax_results": 2}, 5)
        )
        for config_dict, expected_result in config:
            with self.subTest(config_dict=config_dict, expected_result=expected_result):
                self.bot.config = config_dict

                # Act
                result = self.bot.get_max_results()

                # Assert
                self.assertEqual(result, expected_result)

    async def test_get_image_dimensions(self):
        # Arrange
        # white 5x10 png rectangle
        image = (b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x05\x00\x00\x00\n\x08\x06\x00\x00\x00|9\x940\x00'
                 b'\x00\x00\tpHYs\x00\x00\x0e\xc4\x00\x00\x0e\xc4\x01\x95+\x0e\x1b\x00\x00\x00\x15IDAT\x08\x99c\xfc'
                 b'\xff\xff\xff\x7f\x064\xc0\x84.0\x94\x04\x01C\xf5\x04\x10\xadS\xf5\xda\x00\x00\x00\x00IEND\xaeB`\x82')

        # Act
        width, height = self.bot.get_image_dimensions(image)

        # Assert
        self.assertEqual(width, 5)
        self.assertEqual(height, 10)


if __name__ == '__main__':
    unittest.main()
