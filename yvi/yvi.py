from . import config
import emoji
import json
import re
import requests
import time
from . import util
from . exceptions import InvalidVideoIdException, VideoInfoParseError, PatternUnmatchError, UnknownConnectionError
from requests.exceptions import HTTPError, ConnectTimeout, ConnectionError
pattern = re.compile(r"['\"]PLAYER_CONFIG['\"]:\s*({.*})")
pattern2 = re.compile(r"yt\.setConfig\((\{[\s\S]*?\})\);")

item_channel_id = [
    "videoDetails",
    "embeddedPlayerOverlayVideoDetailsRenderer",
    "channelThumbnailEndpoint",
    "channelThumbnailEndpoint",
    "urlEndpoint",
    "urlEndpoint",
    "url"
]

item_renderer = [
    "embedPreview",
    "thumbnailPreviewRenderer"
]

item_response = [
    "args",
    "embedded_player_response"
]

item_response2 = [
    "PLAYER_VARS",
    "embedded_player_response"
]

item_owner_image = [
    "videoDetails",
    "embeddedPlayerOverlayVideoDetailsRenderer",
    "channelThumbnail",
    "thumbnails",
    0,
    "url"
]

item_thumbnail = [
    "defaultThumbnail",
    "thumbnails",
    2,
    "url"
]

item_owner_name = [
    "videoDetails",
    "embeddedPlayerOverlayVideoDetailsRenderer",
    "expandedRenderer",
    "embeddedPlayerOverlayVideoDetailsExpandedRenderer",
    "title",
    "runs",
    0,
    "text"
]

item_user_name = [
    "args",
    "user_display_name",
]

item_user_image = [
    "args",
    "user_display_image",
]


class VideoInfo:
    '''
    VideoInfo object retrieves YouTube video information.

    Parameter
    ---------
    video_id : str

    Exception
    ---------
    InvalidVideoIdException :
        Occurs when video_id does not exist on YouTube.
    '''

    def __init__(self, video_id, session:requests.Session = None):
        if session:
            self.session = session
        else:
            self.session = requests.Session()

        self.video_id = video_id
        self.new_pattern_text = False
        for _ in range(3):
            try:
                text = self._get_page_text(video_id)
                self._parse(text)
                break
            except PatternUnmatchError:
                time.sleep(2)
                pass
        else:
            raise PatternUnmatchError("Pattern Unmatch")

    def _get_page_text(self, video_id):
        url = f"https://www.youtube.com/embed/{video_id}"
        err = None
        for _ in range(3):
            try:
                resp = self.session.get(url)
                resp.raise_for_status()
                break
            except (HTTPError, ConnectTimeout, ConnectionError) as e:
                err = e
                time.sleep(3)
        else:
            raise UnknownConnectionError(str(err))

        return resp.text


    def _parse(self, text):
        result = re.search(pattern, text)
        if result is None:
            result = re.search(pattern2, text)
            if result is None:
                raise VideoInfoParseError("Failed to parse video info.")
            else:
                self.new_pattern_text = True

        decoder = json.JSONDecoder()
        if self.new_pattern_text:
            self._res = decoder.raw_decode(result.group(1))[0]
        else:
            self._res = decoder.raw_decode(result.group(1)[:-1])[0]
        if self.new_pattern_text:
            response = self._get_item(self._res, item_response2)
        else:
            response = self._get_item(self._res, item_response)
        if response is None:
            if self.new_pattern_text:
                self._check_video_is_private(self._res.get("PLAYER_VARS"))
            else:
                self._check_video_is_private(self._res.get("args"))
        self._renderer = self._get_item(json.loads(response), item_renderer)
        if self._renderer is None:
            raise InvalidVideoIdException(
                f"No renderer found in video_id: [{self.video_id}].")

    def _check_video_is_private(self, args):
        if args and args.get("video_id"):
            raise InvalidVideoIdException(
                f"video_id [{self.video_id}] is private or deleted.")
        raise InvalidVideoIdException(
            f"video_id [{self.video_id}] is invalid.")

    def _get_item(self, dict_body, items: list):
        for item in items:
            if dict_body is None:
                break
            if isinstance(dict_body, dict):
                dict_body = dict_body.get(item)
                continue
            if isinstance(item, int) and \
               isinstance(dict_body, list) and \
               len(dict_body) > item:
                dict_body = dict_body[item]
                continue
            return None
        return dict_body

    def get_duration(self):
        duration_seconds = self._renderer.get("videoDurationSeconds")
        if duration_seconds:
            '''Fetched value is string, so cast to integer.'''
            return int(duration_seconds)
        '''When key is not found, explicitly returns None.'''
        return None

    def get_title(self):
        if self._renderer.get("title"):
            return [''.join(run["text"])
                    for run in self._renderer["title"]["runs"]][0]
        return None

    def get_title_escaped(self):
        return self._no_emoji(self.get_title())

    def get_channel_id(self):
        channel_url = self._get_item(self._renderer, item_channel_id)
        if channel_url:
            return channel_url[9:]
        return None

    def get_thumbnail(self):
        return self._get_item(self._renderer, item_thumbnail)

    def get_owner_image(self):
        return self._get_item(self._renderer, item_owner_image)

    def get_owner_name(self):
        return self._get_item(self._renderer, item_owner_name)

    def get_owner_name_escaped(self):
        return self._no_emoji(self.get_owner_name())

    def get_user_name(self):
        return self._get_item(self._res, item_user_name)

    def get_user_name_escaped(self):
        return self._no_emoji(self.get_user_name())

    def get_user_image(self):
        return self._get_item(self._res, item_user_image)

    def _no_emoji(self, text:str):
        if text is None:
            return None
        return ''.join(c for c in text
            if c not in emoji.UNICODE_EMOJI)    

def get_info(video_id:str, session:requests.Session = None) -> VideoInfo:
    """
    Paaramters
    ----------
    video_id : str :
        video_id
    
    session : requests.Session
        session object
    """

    return VideoInfo(video_id = video_id, session = session)
