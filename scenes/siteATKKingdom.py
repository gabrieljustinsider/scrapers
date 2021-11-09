import re
import json
import base64
import warnings
import requests
import dateparser
import scrapy
from scrapy.http import HtmlResponse

from tpdb.BaseSceneScraper import BaseSceneScraper
from tpdb.items import SceneItem

# Ignore dateparser warnings regarding pytz
warnings.filterwarnings(
    "ignore",
    message="The localize method is no longer necessary, as this time zone supports the fold attribute",
)


class ATKKingdomSpider(BaseSceneScraper):
    name = 'ATKKingdom'

    custom_settings = {
        'CONCURRENT_REQUESTS': 1
    }

    start_urls = [
        'https://www.atkexotics.com',
        'https://www.atkarchives.com',
        'https://www.atkpetites.com',
        'https://www.amkingdom.com',
        'https://www.atkhairy.com',
        'https://www.atkpremium.com',
    ]

    selector_map = {
        'title': '//title/text()',
        'description': '//b[contains(text(), "Description:")]/following-sibling::text()[1]|//span[@class="description"]/following-sibling::text()|//span[@class="description"]/following-sibling::span/text()',
        'date': '',
        'image': '//div[contains(@style, "background-image")]/@style',
        'image_blob': '//div[contains(@style, "background-image")]/@style',
        're_image': r'(https.*)\'',
        'performers': '',
        'tags': '//b[contains(text(), "Tags:")]/following-sibling::text()[1]|//span[@class="tags"]/following-sibling::text()',
        'external_id': r'model/(.*?)/',
        'trailer': '',
        'pagination': '/tour/movies/%s'
    }

    def start_requests(self):
        for link in self.start_urls:
            url = link + "/tour/movies"
            headers = self.headers
            headers['Content-Type'] = 'application/json'
            my_data = {'cmd': 'request.get', 'maxTimeout': 60000, 'url': url, 'cookies': [{'name': 'mypage', 'value': str(self.page)}]}
            yield scrapy.Request("http://192.168.1.151:8191/v1", method='POST', callback=self.parse, body=json.dumps(my_data), headers=headers, cookies=self.cookies)

    def parse(self, response, **kwargs):
        jsondata = response.json()
        htmlcode = jsondata['solution']['response']
        response = HtmlResponse(url=response.url, body=htmlcode, encoding='utf-8')
        cookies = jsondata['solution']['cookies']
        for cookie in cookies:
            if cookie['name'] == 'mypage':
                page = int(cookie['value'])
        indexdata = {}
        indexdata['response'] = response
        indexdata['url'] = jsondata['solution']['url']
        scenes = self.get_scenes(indexdata)
        count = 0
        for scene in scenes:
            count += 1
            yield scene

        if count:
            if page and page < self.limit_pages and page < 15:
                page = page + 1
                print('NEXT PAGE: ' + str(page))
                headers = self.headers
                headers['Content-Type'] = 'application/json'
                url = jsondata['solution']['url']
                if page > 2:
                    url = re.search(r'/(.*/)', url).group(1)
                url = self.get_next_page_url(url, page)
                page = str(page)
                my_data = {'cmd': 'request.get', 'maxTimeout': 60000, 'url': url, 'cookies': [{'name': 'mypage', 'value': page}]}
                yield scrapy.Request("http://192.168.1.151:8191/v1", method='POST', callback=self.parse, body=json.dumps(my_data), headers=headers, cookies=self.cookies)

    def get_scenes(self, indexdata):
        response = indexdata['response']
        response_url = indexdata['url']
        if "atkarchives" in response_url or "atkpetites" in response_url or "atkhairy" in response_url or "atkpremium" in response_url:
            scenes = response.xpath('//div[contains(@class, "tourMovieContainer")]')
        if "atkexotics" in response_url or "amkingdom" in response_url:
            scenes = response.xpath('//div[contains(@class, "movie-wrap")]')
        for scene in scenes:
            if "atkarchives" in response_url or "atkpetites" in response_url or "atkhairy" in response_url or "atkpremium" in response_url:
                link = scene.xpath('.//div[@class="player"]/a/@href').get()
                date = scene.xpath('.//span[contains(@class, "movie_date")]/text()').get()
                if date:
                    date = dateparser.parse(date.strip()).isoformat()
                else:
                    date = dateparser.parse('today').isoformat()
                performer = scene.xpath('./div/span[contains(@class,"video_name")]/a/text()').get()
                performer = performer.strip()
                if not performer:
                    performer = ''
            if "atkexotics" in response_url or "amkingdom" in response_url:
                link = scene.xpath('./div[@class="movie-image"]/a/@href').get()
                date = scene.xpath('./div[@class="date left clear"][2]/text()').get()
                if date:
                    date = dateparser.parse(date.strip()).isoformat()
                else:
                    date = dateparser.parse('today').isoformat()
                performer = scene.xpath('./div[@class="video-name"]/a/text()').get()
                performer = performer.strip()
                if not performer:
                    performer = ''

            if link:
                if "atkarchives" in response_url:
                    link = "https://www.atkarchives.com" + link
                if "atkexotics" in response_url:
                    link = "https://www.atkexotics.com" + link
                if "atkpremium" in response_url:
                    link = "https://www.atkpremium.com" + link
                if "atkpetites" in response_url:
                    link = "https://www.atkpetites.com" + link
                if "atkhairy" in response_url:
                    link = "https://www.atkhairy.com" + link
                if "amkingdom" in response_url:
                    link = "https://www.amkingdom.com" + link

                headers = self.headers
                headers['Content-Type'] = 'application/json'
                my_data = {'cmd': 'request.get', 'maxTimeout': 60000, 'url': link, 'cookies': [{'name': 'mydate', 'value': date}, {'name': 'performer', 'value': performer}]}
                if "?w=" not in link:
                    yield scrapy.Request("http://192.168.1.151:8191/v1", method='POST', callback=self.parse_scene, body=json.dumps(my_data), headers=headers, cookies=self.cookies)

    def get_tags(self, response):
        if self.get_selector_map('tags'):
            tags = self.process_xpath(
                response, self.get_selector_map('tags')).get()
            if tags:
                tags = tags.split(",")

                tags2 = tags.copy()
                for tag in tags2:
                    matches = ['4k']
                    if any(x in tag.lower() for x in matches):
                        tags.remove(tag)

                return list(map(lambda x: x.strip().title(), tags))
        return []

    def get_next_page_url(self, base, page):
        url = self.format_url(base, self.get_selector_map('pagination') % page)
        return url

    def parse_scene(self, response):
        jsondata = response.json()
        htmlcode = jsondata['solution']['response']
        response = HtmlResponse(url=response.url, body=htmlcode, encoding='utf-8')
        response_url = jsondata['solution']['url']
        cookies = jsondata['solution']['cookies']
        for cookie in cookies:
            if cookie['name'] == 'mydate':
                date = cookie['value']
            if cookie['name'] == 'performer':
                performer = cookie['value']
        item = SceneItem()
        if date:
            item['date'] = dateparser.parse(date).isoformat()
        else:
            item['date'] = dateparser.parse('today').isoformat()

        if performer:
            item['performers'] = [performer]
        else:
            item['performer'] = []

        item['title'] = self.get_title(response)
        item['description'] = self.get_description(response)
        item['image'] = self.get_image(response)
        item['image_blob'] = self.get_image_blob(response)
        item['tags'] = self.get_tags(response)
        if "" in item['tags']:
            item['tags'].remove("")
        item['id'] = re.search(r'/movie/(.*?)/', jsondata['solution']['url']).group(1)
        item['trailer'] = self.get_trailer(response)
        item['url'] = jsondata['solution']['url']
        item['network'] = "ATK Girlfriends"

        if "atkarchives" in response_url:
            item['parent'] = "ATK Archives"
            item['site'] = "ATK Archives"
        if "atkexotics" in response_url:
            item['parent'] = "ATK Exotics"
            item['site'] = "ATK Exotics"
        if "atkpremium" in response_url:
            item['parent'] = "ATK Premium"
            item['site'] = "ATK Premium"
        if "atkpetites" in response_url:
            item['parent'] = "ATK Petites"
            item['site'] = "ATK Petites"
        if "atkhairy" in response_url:
            item['parent'] = "ATK Hairy"
            item['site'] = "ATK Hairy"
        if "amkingdom" in response_url:
            item['parent'] = "ATK Galleria"
            item['site'] = "ATK Galleria"

        if self.debug:
            print(item)
        else:
            yield item

    def get_image(self, response):
        image = super().get_image(response)
        if not image:
            imagealt = response.xpath('//div[contains(@style,"background")]/@style')
            if imagealt:
                imagealt = re.search(r'url\(\"(http.*)\"\)', imagealt.get())
                if imagealt:
                    imagealt = imagealt.group(1)
                    imagealt = self.format_link(response, imagealt)
                    return imagealt.replace(" ", "%20")
            image = None
        return image

    def get_image_blob(self, response):
        image = super().get_image(response)
        if not image:
            imagealt = response.xpath('//div[contains(@style,"background")]/@style')
            if imagealt:
                imagealt = re.search(r'url\(\"(http.*)\"\)', imagealt.get())
                if imagealt:
                    imagealt = imagealt.group(1)
                    imagealt = self.format_link(response, imagealt)
                    image = imagealt.replace(" ", "%20")
        if image:
            return base64.b64encode(requests.get(image).content).decode('utf-8')
        return None