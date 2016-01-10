"""
    SALTS XBMC Addon
    Copyright (C) 2014 tknorris

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""
import scraper
import urlparse
import urllib
import re
from salts_lib import kodi
from salts_lib import log_utils
from salts_lib import dom_parser
from salts_lib.trans_utils import i18n
from salts_lib.constants import VIDEO_TYPES
from salts_lib.constants import FORCE_NO_MATCH

BASE_URL = 'http://iflix.ch'
BASE_URL2 = 'http://tvshows.iflix.ch'

class Iflix_Scraper(scraper.Scraper):
    base_url = BASE_URL
    tv_base_url = BASE_URL2

    def __init__(self, timeout=scraper.DEFAULT_TIMEOUT):
        self.timeout = timeout
        self.base_url = kodi.get_setting('%s-base_url' % (self.get_name()))
        self.tv_base_url = kodi.get_setting('%s-base_url2' % (self.get_name()))

    @classmethod
    def provides(cls):
        return frozenset([VIDEO_TYPES.TVSHOW, VIDEO_TYPES.EPISODE, VIDEO_TYPES.MOVIE])

    @classmethod
    def get_name(cls):
        return 'IFlix'

    def resolve_link(self, link):
        return link

    def format_source_label(self, item):
        return '[%s] %s' % (item['quality'], item['host'])

    def get_sources(self, video):
        source_url = self.get_url(video)
        sources = []
        if source_url and source_url != FORCE_NO_MATCH:
            url = urlparse.urljoin(self.base_url, source_url)
            html = self._http_get(url, cache_limit=.5)
#             source = {'multi-part': False, 'url': stream_url, 'host': host, 'class': self, 'quality': quality, 'views': None, 'rating': None, 'direct': True}
#             sources.append(source)

        return sources

    def get_url(self, video):
        return super(Iflix_Scraper, self)._default_get_url(video)

    def _get_episode_url(self, show_url, video):
        episode_pattern = 'href="([^"]+-season-%s-episode-%s/?)"' % (video.season, video.episode)
        title_pattern = 'href="(?P<url>[^"]+-season-\d+-episode-\d+/?)".*?<span\s+class="datix">.*?\((?P<title>[^)]*)'
        show_url = urlparse.urljoin(self.__get_base_url(video.video_type), show_url)
        return super(Iflix_Scraper, self)._default_get_episode_url(show_url, video, episode_pattern, title_pattern)

    def search(self, video_type, title, year):
        results = []
        search_url = urlparse.urljoin(self.__get_base_url(video_type), '/?s=%s' % (urllib.quote_plus(title)))
        html = self._http_get(search_url, cache_limit=1)
        for movie in dom_parser.parse_dom(html, 'div', {'class': 'movie'}):
            match = re.search('href="([^"]+)', movie)
            if match:
                match_url = match.group(1)
                if re.search('season-\d+-episode\d+', match_url): continue
                match_title_year = dom_parser.parse_dom(movie, 'img', ret='alt')
                if match_title_year:
                    match_title_year = match_title_year[0]
                    match = re.search('(.*?)\s+\((\d{4})\)', match_title_year)
                    if match:
                        match_title, match_year = match.groups()
                    else:
                        match_title = match_title_year
                        match_year = dom_parser.parse_dom(movie, 'div', {'class': 'year'})
                        try: match_year = match_year[0]
                        except: match_year = ''
                        
                    if not year or not match_year or year == match_year:
                        result = {'url': self._pathify_url(match_url), 'title': match_title, 'year': match_year}
                        results.append(result)

        return results

    @classmethod
    def get_settings(cls):
        settings = super(Iflix_Scraper, cls).get_settings()
        name = cls.get_name()
        settings.append('         <setting id="%s-base_url2" type="text" label="    %s %s" default="%s" visible="eq(-4,true)"/>' % (name, i18n('tv_shows'), i18n('base_url'), cls.tv_base_url))
        return settings
    
    def __get_base_url(self, video_type):
        if video_type in [VIDEO_TYPES.TVSHOW, VIDEO_TYPES.EPISODE]:
            base_url = self.tv_base_url
        else:
            base_url = self.base_url
        return base_url
