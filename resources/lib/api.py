import re
import json
from collections import namedtuple

import requests


VIDEO_DATA_RE = (
    r"React\.createElement\(Components\.TrendingGridModule, (.*?)\)"
    r", document.getElementById\("
)

URL = "https://www.tottenhamhotspur.com/trendinggrid/loadmore"

Video = namedtuple('Video', 'entry_id title caption thumbnail')


def image_url(path, height=720):
    return 'https://tot-tmp.azureedge.net/media/{0}?height={1}'.format(path, height)


def videos(tag_id=56552, page=1, items=100):
    response = requests.get(
        URL, dict(tagIds=tag_id, fromPage=page-1, toPage=page, itemsPerGrid=items)).text
    data = re.search(VIDEO_DATA_RE, response, re.DOTALL).group(1)
    modules = json.loads(data)['data']['modules']
    for module in modules:
        article = module['data']['article']
        video_data = article['media']
        if video_data is not None:
            yield Video(
                entry_id=video_data['entryId'],
                title=article['title'],
                caption=video_data['caption'],
                thumbnail=_thumbnail(video_data)
            )


def _thumbnail(video_data):
    for key in ['thumbnail', 'image']:
        try:
            return video_data.get(key) and video_data[key]['smallUrl']
        except KeyError:
            continue

