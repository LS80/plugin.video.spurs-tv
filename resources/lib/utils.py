import time
from datetime import date

import xbmc, xbmcaddon

__addon__ = xbmcaddon.Addon("plugin.video.spurs-tv")

def log(txt, level=xbmc.LOGDEBUG):
    if __addon__.getSetting('debug') == 'true':
        msg = '{} v{}: {}'.format(__addon__.getAddonInfo('name'),
                                  __addon__.getAddonInfo('version'), txt)
        xbmc.log(msg, level)

def date_from_str(date_str, date_format):
    return date(*(time.strptime(date_str, date_format)[0:3]))

def add_item_info(item, title, item_date):
    item['info'] = {'title': title,
                    'date': item_date.strftime("%d.%m.%Y")}
