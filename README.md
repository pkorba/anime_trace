# Anime Trace Bot

A maubot plugin that allows user to trace back the scene from an anime screenshot using [trace.moe](https://trace.moe/) API.

![bot_anime_trace](https://github.com/user-attachments/assets/1159941f-d29a-49f5-a5d4-34ed797d7733)

## Usage

Do one of the following:  
1. Reply to a message containing a screenshot/video or an external link to a screenshot/video with a command `!trace`.  
2. Send a single message that contains a screenshot/video as an attachment and a command `!trace`.  
3. Send a single message that contains a link to the screenshot/video and a command `!trace <link>`.

If your message contains both an image and a link, then the attachment will be used.  
In order to check the search quota and limit send a message with a command: `!trace quota`.

## Configuration

You can configure the plugin in maubot's control panel.
* `preview_size` - controls the size of video preview and its thumbnail. Available options are:
  * `l` - large
  * `m` - medium (default)
  * `s` - small
* `api_key` - if you have your own trace.moe API key, you can put it here
* `mute` - controls whether the video previews have sound. Available options are `yes` and `no` (default)
* `cut_borders` - trace.moe can detect black borders automatically and cut away unnecessary parts of the images that would affect search results accuracy. This is useful if your image is a screencap from a smartphone or iPad that contains black bars. Available options are `yes` (default) and `no`.
* `max_results` - controls the number of displayed results (defaults to 5)

## Notes

- Plugin supports images and videos - according to trace.moe docs, any format that is supported by ffmpeg
- File size limit is 25 MB

## Disclaimer

This plugin is unofficial and is not affiliated with trace.moe. It is not intended for any purpose that violates trace.moe Terms of Service. By using this plugin, you acknowledge that you will not use it in a way that infringes on trace.moe terms. The official trace.moe website can be found at https://trace.moe/.
