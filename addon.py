# coding=utf-8
##########################################################################
#
#  Copyright 2014 Lee Smith
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
# 
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
# 
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##########################################################################

import os
import re
from urlparse import urlparse, urlunparse, urljoin
from datetime import date, timedelta
import time

from xbmcswift2 import Plugin
from bs4 import BeautifulSoup
try:
    import requests2 as requests
except ImportError:
    import requests


HOST = "http://m.tottenhamhotspur.com"
BASE_URL = HOST + "/spurs-tv/"
SEARCH_URL = HOST + "/search/"
PARTNER_ID = 2000012

ENTRY_ID_RE = re.compile("entry_id/(\w+)/")
PAGE_RE = re.compile("page +(\d+) +of +(\d+)")

MEDIA_SCHEME = "http"
MEDIA_HOST = "mmp.streamuk.com"
MEDIA_URL_ROOT = urlunparse((MEDIA_SCHEME, MEDIA_HOST, "/p/{}/".format(PARTNER_ID), None, None, None))

THUMB_URL_FMT = MEDIA_URL_ROOT + "thumbnail/entry_id/{}/width/{}/"

MANIFEST_XML_FMT = (MEDIA_URL_ROOT +
                    "playManifest/entryId/{}/format/rtmp/a.f4m?referrer=" +
                    BASE_URL.encode('base-64'))

PLAYLIST_XML_FMT = urlunparse((MEDIA_SCHEME, MEDIA_HOST,
                               "index.php/partnerservices2/executeplaylist?" +
                               "partner_id={}&playlist_id={{}}".format(PARTNER_ID), None, None, None))

FIELD_NAME_ROOT_FMT = ("ctl00$ContentPlaceHolder1$DropZoneMainContent$columnDisplay$"
                       "ctl00$controlcolumn$ctl{:02d}$WidgetHost$WidgetHost_widget$")

PAGINATION_FMT = "Pagination1${}"

NAV_FMT = FIELD_NAME_ROOT_FMT.format(2) + PAGINATION_FMT

SEARCH_NAV_FMT = FIELD_NAME_ROOT_FMT.format(0) + PAGINATION_FMT

HEADERS = {'User-agent': "Mozilla/5.0"}


plugin = Plugin()

form_data = plugin.get_storage('form_data')

def get_soup(url, data=None):
    if data is not None:
        response = requests.post(url, data, headers=HEADERS)
    else:
        response = requests.get(url, headers=HEADERS)
    return BeautifulSoup(response.text, 'html5lib')

def get_viewstate(soup):
    return soup.find('input', id='__VIEWSTATE')['value']

def get_page_links(soup, endpoint, **kwargs):
    page = None
    links = []
    intro = soup.find('div', 'intro')
    if intro:
        page, npages = [int(n) for n in PAGE_RE.search(intro.contents[0]).groups()]
         
        if page > 1:
            item = {'label': "<< Page {:d}".format(page - 1),
                    'path': plugin.url_for(endpoint,
                                           navigate='prev',
                                           **kwargs)
                    }
            links.append(item)
      
        if page < npages:
            item = {'label': "Page {:d} >>".format(page + 1),
                    'path': plugin.url_for(endpoint,
                                           navigate='next',
                                           **kwargs)
                    }
            links.append(item)

    return page, links
        
def video_item(entry_id, title, date_str, date_format="%d %B %Y", duration_str=None, duration=None):
    video_date = date(*(time.strptime(date_str, date_format)[0:3]))

    item = {'label': title,
            'thumbnail': THUMB_URL_FMT.format(entry_id, 480),
            'is_playable': True,
            'path': plugin.url_for('play_video', entry_id=entry_id),
            'info': {'title': title,
                     'date': video_date.strftime("%d.%m.%Y")
                    },
            }
    
    if duration is not None:
        item['stream_info'] = {'video': {'duration': duration}}
    elif duration_str is not None:
        minutes, seconds = duration_str.split(':')
        duration = timedelta(minutes=int(minutes), seconds=int(seconds))
        item['stream_info'] = {'video': {'duration': duration.seconds}}
        
    return item

def get_videos(soup, category):
    page, links = get_page_links(soup, 'show_video_list', category=category)
    for page_link in links:
        yield page_link
    
    if category == 'latest' or category.startswith('tour') or page == 1:
        featured_video = soup.find('div', 'video')
    
        featured_entry_id = featured_video['data-videoid']
        title = featured_video['data-title']
        duration_str = featured_video.find_next('span', 'duration').string 
        featured_date = featured_video.find_previous('p', 'featured-date')
        date_str = featured_date.string.splitlines()[2].strip()
        
        yield video_item(featured_entry_id, title, date_str, duration_str=duration_str)
        
    for card in soup(class_='card'):
        entry_id = ENTRY_ID_RE.search(card.a['style']).group(1)
        title = card.find('span', 'video-title').contents[0]
        duration_str = card.find('span', 'duration').string
        date_str = card.find('em', 'video-date').string
        
        yield video_item(entry_id, title, date_str, duration_str=duration_str)

    form_data['viewstate'] = get_viewstate(soup)

def get_playlist_videos(playlist_id):
    playlist_url = PLAYLIST_XML_FMT.format(playlist_id)
    xml = requests.get(playlist_url).text
    for entry in BeautifulSoup(xml, 'html5lib').entries:
        entry_id = entry.id.string
        title = entry.find('name').string
        date_str = entry.createdat.string.split()[0]
        yield video_item(entry_id, title, date_str, date_format="%Y-%m-%d",
                         duration=entry.duration.string)

def get_search_result_videos(soup, query):
    page, links = get_page_links(soup, 'search_result', query=query)
    for page_link in links:
        yield page_link
    
    for card in soup(class_='card'):
        entry_id = ENTRY_ID_RE.search(card.a['style']).group(1)
        title = card.parent.find('h3').text
        date_str = " ".join(card.parent.find('span', 'date').contents[0].split()[4:-1])
        
        yield video_item(entry_id, title, date_str, date_format="%d %b %Y")
        
    form_data['viewstate'] = get_viewstate(soup)
        
def get_categories():
    soup = get_soup(BASE_URL)
    
    yield {'label': "Tour 2014",
           'path': plugin.url_for('show_video_list', category='tour2014')}
    
    yield {'label': "Latest",
           'path': plugin.url_for('show_video_list', category='latest')}

    yield {'label': "Search",
           'path': plugin.url_for('search')}
    
    for a in soup.find('map', id='inside-nav')('a')[1:-3]:
        category = a['title']
        path = os.path.basename(os.path.normpath(a['href']))
        yield {'label': category,
               'path': plugin.url_for('show_video_list', category=path)}



@plugin.route('/')
def index():
    return get_categories()
    
@plugin.route('/category/<category>')
def show_video_list(category):
    if category == 'latest':
        url = BASE_URL
    elif category.startswith('tour'):
        url = urljoin(HOST, category + '/spurs-tv/')
    else: 
        url = urljoin(BASE_URL, category + '/')
        
    if 'navigate' in plugin.request.args:
        navigate = plugin.request.args['navigate'][0]
        viewstate = form_data['viewstate']
        data = {NAV_FMT.format(navigate): '',
                '__VIEWSTATE': viewstate}
        soup = get_soup(url, data)
        update_listing = True
    else:
        soup = get_soup(url)
        update_listing = False

    return plugin.finish(get_videos(soup, category),
                         sort_methods=['playlist_order', 'date', 'duration', 'title'],
                         update_listing=update_listing)

@plugin.route('/playlist/<playlist_id>')
def show_playlist(playlist_id):
    return plugin.finish(get_playlist_videos(playlist_id),
                         sort_methods=['playlist_order', 'date', 'duration', 'title'])

@plugin.route('/search')
def search():
    query = plugin.keyboard(heading="Search")
    if query:
        url = plugin.url_for('search_result', query=query, page=1)
        plugin.redirect(url)

@plugin.route('/search/<query>')
def search_result(query):
    
    search_data = {FIELD_NAME_ROOT_FMT.format(0) + "drpTaxonomyCategoriesFilter": '144',
                   FIELD_NAME_ROOT_FMT.format(0) + "hdSearchTerm": query}
    
    if 'navigate' in plugin.request.args:
        navigate = plugin.request.args['navigate'][0]
        search_data[SEARCH_NAV_FMT.format(navigate)] = ''
        viewstate = form_data['viewstate']
        update_listing = True
    else:
        soup = get_soup(SEARCH_URL)
        viewstate = get_viewstate(soup)
        update_listing = False
        
    search_data['__VIEWSTATE'] = viewstate

    soup = get_soup(SEARCH_URL, search_data)

    return get_search_result_videos(soup, query)

@plugin.route('/video/<entry_id>')
def play_video(entry_id):
    xml = requests.get(MANIFEST_XML_FMT.format(entry_id)).text
    media = BeautifulSoup(xml, 'html.parser').find_all('media')
    url = media[-1]['url'] # highest resolution
    
    video_url = urlunparse((MEDIA_SCHEME, MEDIA_HOST, urlparse(url)[2], None, None, None))

    return plugin.set_resolved_url(video_url)


if __name__ == '__main__':
    plugin.run()
