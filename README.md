# Anime Trace Bot

A maubot for Matrix messaging that allows user to trace back the scene from an anime screenshot using [trace.moe](https://trace.moe/) API. It requires no configuration.

![bot_anime_trace](https://github.com/user-attachments/assets/951c9295-7990-40c6-9f4c-d55d6ce8ac26)


## Usage

Do one of the following:  
1. Reply to a message containing a screenshot/video or an external link to a screenshot/video with a command `[p]trace`.  
2. Send a single message that contains a screenshot/video as an attachment and a command `[p]trace`.  
3. Send a single message that contains a link to the screenshot/video and a command `[p]trace link`.  

If your message contains both an image and a link, then the attachment will be used.

## Notes

- Current version doesn't support user's API keys. It may be added in future release.
- Plugin supports images and videos - according to trace.moe API, any format that is supported by ffmpeg
- File size limit is 25 MB
