from dataclasses import dataclass


@dataclass
class MessageData:
    html: str
    body: str
    video_url: str
    image_url: str
