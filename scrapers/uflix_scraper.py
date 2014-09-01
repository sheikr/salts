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
import xbmc
import urllib
import urlparse
import re
import common
from salts_lib.db_utils import DB_Connection
from salts_lib import log_utils
from salts_lib.constants import VIDEO_TYPES
from salts_lib.constants import QUALITIES


QUALITY_MAP = {'HD': QUALITIES.HIGH, 'LOW': QUALITIES.LOW}

class UFlix_Scraper(scraper.Scraper):
    def __init__(self, timeout=scraper.DEFAULT_TIMEOUT):
        self.base_url = 'http://uflix.org'
        self.timeout=timeout
        self.db_connection = DB_Connection()
    
    @classmethod
    def provides(cls):
        return frozenset([VIDEO_TYPES.TVSHOW, VIDEO_TYPES.SEASON, VIDEO_TYPES.EPISODE, VIDEO_TYPES.MOVIE])
    
    def get_name(self):
        return 'UFlix.org'
    
    def resolve_link(self, link):
        url = urlparse.urljoin(self.base_url, link)
        html = self.__http_get(url, cache_limit=0)
        match = re.search('iframe\s+src="(.*?)"', html)
        if match:
            return match.group(1)
        else:
            match = re.search('var\s+url\s+=\s+\'(.*?)\'', html)
            if match:
                return match.group(1)
    
    def format_source_label(self, item):
        return '[%s] %s (%s Up, %s Down) (%s/100)' % (item['quality'], item['host'], item['up'], item['down'], item['rating'])
    
    def get_sources(self, video_type, title, year, season='', episode=''):
        url = urlparse.urljoin(self.base_url, self.get_url(video_type, title, year, season, episode))
        html = self.__http_get(url, cache_limit=.5)

        quality=None
        match = re.search('(?:qaulity|quality):\s*<span[^>]*>(.*?)</span>', html, re.DOTALL|re.I)
        if match:
            quality = QUALITY_MAP.get(match.group(1).upper())
            
        sources=[]
        pattern='class="btn btn-primary".*?href="(.*?)".*?\?domain=[^>]+>\s*(.*?)</.*?class="fa fa-thumbs-o-up">\s*\((\d+)\).*?\((\d+)\)\s*<i class="fa fa-thumbs-o-down'
        for match in re.finditer(pattern, html, re.DOTALL | re.I):
            url, host,up,down = match.groups()
            # skip ad match
            if host.upper()=='HDSTREAM':
                continue

            up=int(up)
            down=int(down)
            source = {'multi-part': False}
            source['url']=url.replace(self.base_url,'')
            source['host']=host.replace('<span>','').replace('</span>','')
            source['class']=self
            source['quality']=quality
            source['up']=up
            source['down']=down
            rating=up*100/(up+down) if (up>0 or down>0) else None
            source['rating']=rating
            source['views']=up+down
            sources.append(source)
        
        return sources

    def get_url(self, video_type, title, year, season='', episode=''):
        temp_video_type=video_type
        if video_type == VIDEO_TYPES.EPISODE: temp_video_type=VIDEO_TYPES.TVSHOW
        url = None

        result = self.db_connection.get_related_url(temp_video_type, title, year, self.get_name())
        if result:
            url=result[0][0]
            log_utils.log('Got local related url: |%s|%s|%s|%s|%s|' % (temp_video_type, title, year, self.get_name(), url))
        else:
            results = self.search(temp_video_type, title, year)
            if results:
                url = results[0]['url']
                self.db_connection.set_related_url(temp_video_type, title, year, self.get_name(), url)

        if url and video_type==VIDEO_TYPES.EPISODE:
            result = self.db_connection.get_related_url(VIDEO_TYPES.EPISODE, title, year, self.get_name(), season, episode)
            if result:
                url=result[0][0]
                log_utils.log('Got local related url: |%s|%s|%s|%s|%s|%s|%s|' % (video_type, title, year, season, episode, self.get_name(), url))
            else:
                show_url = url
                url = self.__get_episode_url(show_url, season, episode)
                if url:
                    self.db_connection.set_related_url(VIDEO_TYPES.EPISODE, title, year, self.get_name(), url, season, episode)
        
        return url
    
    def search(self, video_type, title, year):
        search_url = urlparse.urljoin(self.base_url, '/index.php?menu=search&query=')
        search_url += urllib.quote_plus(title)
        html = self.__http_get(search_url, cache_limit=.25)
        results=[]
        
        # filter the html down to only tvshow or movie results
        if video_type in [VIDEO_TYPES.TVSHOW, VIDEO_TYPES.SEASON, VIDEO_TYPES.EPISODE]:
            pattern='<div id="grid2".*'
        else:
            pattern='<div id="grid".*<div id="grid2"'
        match = re.search(pattern, html, re.DOTALL)
        try:
            fragment = match.group(0)
            pattern = '<a title="Watch (.*?) Online For FREE".*href="(.*?)".*\((\d{1,4})\)</a>'
            for match in re.finditer(pattern, fragment):
                result={}
                res_title, url, res_year = match.groups('')
                if not year or year == res_year:                
                    result['title']=res_title
                    result['url']=url.replace(self.base_url,'')
                    result['year']=res_year
                    results.append(result)
        except Exception as e:
            log_utils.log('Failure during %s search: |%s|%s|%s| (%s)' % (self.get_name(), video_type, title, year, str(e)), xbmc.LOGWARNING)
        
        return results
        
    def __get_episode_url(self, show_url, season, episode):
        url = urlparse.urljoin(self.base_url, show_url)
        html = self.__http_get(url, cache_limit=2)
        pattern = 'class="link"\s+href="(.*?/show/.*?/season/%s/episode/%s)"' % (season, episode)
        match = re.search(pattern, html)
        if match:
            url = match.group(1)
            return url.replace(self.base_url, '')
        
    def __http_get(self, url, cache_limit=8):
        return common.cached_http_get(url, self.base_url, self.timeout, cache_limit=cache_limit)
        