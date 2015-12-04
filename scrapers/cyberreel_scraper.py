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
import re
import urllib
import base64
from salts_lib import kodi
from salts_lib import dom_parser
from salts_lib import log_utils
from salts_lib.constants import VIDEO_TYPES
from salts_lib.constants import FORCE_NO_MATCH
from salts_lib.constants import USER_AGENT

BASE_URL = 'http://cyberreel.com'
HEIGHT_MAP = {'MOBILE': 240}
MAX_SOURCES = 3

class CyberReel_Scraper(scraper.Scraper):
    base_url = BASE_URL

    def __init__(self, timeout=scraper.DEFAULT_TIMEOUT):
        self.timeout = timeout
        self.base_url = kodi.get_setting('%s-base_url' % (self.get_name()))

    @classmethod
    def provides(cls):
        return frozenset([VIDEO_TYPES.MOVIE])

    @classmethod
    def get_name(cls):
        return 'CyberReel'

    def resolve_link(self, link):
        return link

    def format_source_label(self, item):
        return '[%s] %s' % (item['quality'], item['host'])

    def get_sources(self, video):
        source_url = self.get_url(video)
        hosters = []
        if source_url and source_url != FORCE_NO_MATCH:
            url = urlparse.urljoin(self.base_url, source_url)
            html = self._http_get(url, cache_limit=.5)
            hosters += self.__get_embedded(html, url)
            if not hosters:
                hosters += self.__get_in_page(html, url)
                        
        return hosters

    def __get_embedded(self, html, page_url):
        seen_source = {}
        hosters = []
        for source_count, item in enumerate(dom_parser.parse_dom(html, 'div', {'class': 'movieplay'})):
            src = dom_parser.parse_dom(item, 'iframe', ret='src')
            if src:
                if source_count >= MAX_SOURCES:
                    break
                
                html = self._http_get(src[0], cache_limit=.5)
                pattern = 'file\s*:\s*(.*?)"([^"]+)"\),\s*label\s*:\s*"([^"]+)",\s*type\s*:\s*"([^"]+)'
                for match in re.finditer(pattern, html):
                    func, stream_url, label, vid_type = match.groups()
                    if vid_type.lower() not in ['mp4', 'avi']: continue
                    if 'atob' in func: stream_url = base64.decodestring(stream_url)
                    if stream_url in seen_source: continue
                    seen_source[stream_url] = True
                    if self._get_direct_hostname(stream_url) == 'gvideo':
                        quality = self._gv_get_quality(stream_url)
                    else:
                        quality = self.__get_quality_from_label(label)

                    stream_url += '|User-Agent=%s&Referer=%s' % (USER_AGENT, urllib.quote(page_url))
                    hoster = {'multi-part': False, 'host': self._get_direct_hostname(stream_url), 'class': self, 'quality': quality, 'views': None, 'rating': None, 'url': stream_url, 'direct': True}
                    hosters.append(hoster)
        return hosters
    
    def __get_quality_from_label(self, label):
        label = label.upper()
        match = re.search('(\d{3,})', label)
        if match:
            label = match.group(1)

        height = HEIGHT_MAP.get(label.upper(), label)
        return self._height_get_quality(height)
        
    def __get_in_page(self, html, page_url):
        sources = []
        hosters = []
        fragment = dom_parser.parse_dom(html, 'div', {'class': 'entry-content'})
        if fragment:
            fragment = fragment[0]
            for source in dom_parser.parse_dom(fragment, 'iframe', ret='src'):
                sources.append(source)
            
            for match in re.finditer('<source\s+src="([^"]+)[^>]+type="video/mp4"', fragment):
                sources.append(match.group(1))
            
        for source in sources:
            if self._get_direct_hostname(source) == 'gvideo':
                quality = self._gv_get_quality(source)
                stream_url = source + '|User-Agent=%s&Referer=%s' % (USER_AGENT, urllib.quote(page_url))
                hoster = {'multi-part': False, 'host': self._get_direct_hostname(stream_url), 'class': self, 'quality': quality, 'views': None, 'rating': None, 'url': stream_url, 'direct': True}
                hosters.append(hoster)
        return hosters
    
    def get_url(self, video):
        return super(CyberReel_Scraper, self)._default_get_url(video)

    def search(self, video_type, title, year):
        results = []
        search_url = urlparse.urljoin(self.base_url, '/?s=')
        search_url += urllib.quote_plus(title)
        html = self._http_get(search_url, cache_limit=1)
        for item in dom_parser.parse_dom(html, 'div', {'class': 'item'}):
            match = re.search('href="([^"]+)', item)
            if match:
                url = match.group(1)
                match_title_year = dom_parser.parse_dom(item, 'span', {'class': 'tt'})
                if match_title_year:
                    match = re.search('(.*?)\s+\(?(\d{4})\)?', match_title_year[0])
                    if match:
                        match_title, match_year = match.groups()
                    else:
                        match_title = match_title_year[0]
                        match_year = ''
                    
                    year_frag = dom_parser.parse_dom(item, 'span', {'class': 'year'})
                    if year_frag:
                        match_year = year_frag[0]
                        
                    if (not year or not match_year or year == match_year):
                        result = {'url': self._pathify_url(url), 'title': match_title, 'year': match_year}
                        results.append(result)
        
        return results
