#!/usr/bin/python3

from urllib.parse import urlencode, quote_plus
import json
import sys
import requests
from enum import Enum
from time import localtime, strftime
from multiprocessing import Pool
from concurrent.futures import ThreadPoolExecutor
import itertools

RADIOFRANCE_PAGE = "https://www.radiofrance.fr/"
BRAND_EXTENSION = "/api/live/webradios/"

NOT_ITEM_FORMAT = ["TYPED_ELEMENT_NEWSLETTER_SUBSCRIPTION", "TYPED_ELEMENT_AUTOPROMO_IMMERSIVE"]

class Model(Enum):
    OTHER = 0
    THEME = 1
    CONCEPT = 2
    HIGHLIGHT = 3
    HIGHLIGHTELEMENT = 4
    EXPRESSION = 5
    MANIFESTATIONAUDIO = 6
    EMBEDIMAGE = 7
    PAGETEMPLATE = 8
    BRAND = 9
    TAG = 10
    SEARCH = 11
    ARTICLE = 12
    EVENT = 13
    SLUG = 14
    STATION = 15
    STATIONPAGE = 16
    GRID = 17
    PROGRAM = 18

def fetch_data(url):
    response = requests.get(url)
    response.raise_for_status()
    return response.json()

def get_key_src(key, data):
    if data is None:
        return None
    value = data.get(key, {})
    if value is not None and 'src' in value:
        return value['src']
    return None

def create_item_from_page(data):
    if "model" not in data:
        if "content" in data:
            data = data["content"]
        elif "layout" in data:
            data = data["layout"]
        elif "podcastsData" in data:
            data = data["podcastsData"]

    item = create_item(0, data)
    if not isinstance(item, Item):
        _, data, e = item
        print(json.dumps(data))
        raise(e)
    index = 0
    while len(item.subs) == 1:
        new_item = create_item(index, item.subs[0])
        if isinstance(new_item, Item):
            item = new_item
        else:
            break
        index += 1
    return item

def create_item(index, data):
    model_map = {
        Model.OTHER.name: Other,
        Model.BRAND.name: Brand,
        Model.THEME.name: Theme,
        Model.CONCEPT.name: Concept,
        Model.HIGHLIGHT.name: Highlight,
        Model.HIGHLIGHTELEMENT.name: HighlightElement,
        Model.EXPRESSION.name: Expression,
        Model.MANIFESTATIONAUDIO.name: ManifestationAudio,
        Model.EMBEDIMAGE.name: EmbedImage,
        Model.PAGETEMPLATE.name: PageTemplate,
        Model.TAG.name: Tag,
        Model.ARTICLE.name: Article,
        Model.EVENT.name: Event,
        Model.SLUG.name: Slug,
        Model.STATIONPAGE.name: StationPage,
        Model.GRID.name: Grid,
        Model.PROGRAM.name: Program
    }

    try:
        if 'model' in data:
            model_name = data['model'].upper()
            item = model_map[model_name](data, index)
        elif 'stationName' in data:
            item = Station(data, index)
        elif 'items' in data and 'concepts' in data['items'] and 'expressions_articles' in data['items']:
            item = Search(data, index)
        elif 'slug' in data:
            item = model_map['SLUG'](data, index)
        elif 'brand' in data and not data.get('format', "") in NOT_ITEM_FORMAT :
            item = model_map['BRAND'](data, index)
        elif 'grid' in data:
            item = model_map['GRID'](data, index)
        elif 'concept' in data and 'expression' in data:
            item = model_map['PROGRAM'](data, index)
        else:
            item = model_map['OTHER'](data, index)
    except Exception as e:
        return (None, data, e)

    item.index = index
    item.remove_singletons()
    return item

class Item:
    def __init__(self, data, index):
        self.id = data.get('id', "x" * 8)
        self.model = Model[data.get('model', "Other").upper()]
        self.path = podcast_url(data.get('path', None))
        self.subs = []
        try:
            self.image = get_key_src('visual', data)
            self.icon = get_key_src('squaredVisual', data)
        except Exception as e:
            print(json.dumps(data), e)
            raise (e)
        self.pages = (1, 1)
        pagination = data.get('pagination', {'pageNumber': 1})
        self.pages = (pagination['pageNumber'], pagination.get('lastPage', pagination['pageNumber']))
        self.title = str(data.get('title', ""))
        self.index = index

    def remove_singletons(self):
        if self.path is None and len(self.subs) == 1:
            print(json.dumps(self.subs))
            new_item = create_item(self.index, self.subs[0])
            if not isinstance(new_item, Item):
                _, data, e = new_item
                print(json.dumps(data))
                raise(e)
            self = new_item
        while len(self.subs) == 1 and self.subs[0] is not None:
            sub_item = create_item(self.index, self.subs[0])
            if not isinstance(sub_item, Item):
                _, data, e = sub_item
                print(json.dumps(data))
                raise(e)
            self.subs = sub_item.subs if isinstance(sub_item, Item) else []
            self.index += 1

    def __str__(self):
        return (f"{self.pages}{''.join([f'{self.index}. {self.title} [{self.model}] [{len(self.subs)}] ({self.path}) — {self.id[:8]}'])}")

    def is_folder(self):
        return self.model in [Model.THEME, Model.CONCEPT, Model.HIGHLIGHT, Model.HIGHLIGHTELEMENT, Model.PAGETEMPLATE, Model.TAG, Model.ARTICLE, Model.SLUG, Model.STATIONPAGE, Model.GRID, Model.OTHER]

    def is_image(self):
        return self.model in [Model.EMBED_IMAGE]

    def is_audio(self):
        return not self.is_folder() and not self.is_image()

class Event(Item):
    def __init__(self, data, index):
        super().__init__(data, index)
        self.path = podcast_url(data['href'])

class Station(Item):
    def __init__(self, data, index):
        super().__init__(data, index)
        self.model = Model.STATION
        self.title = f"{data['stationName']}: {data['now']['secondLine']['title']}"
        self.artists = data['stationName']
        self.duration = None
        self.release = None
        self.subs = []
        self.path = data['now']['media']['sources'][0]['url'] if 0 < len(data['now']['media']['sources']) else None

class StationPage(Item):
    def __init__(self, data, index):
        super().__init__(data, index)
        self.model = Model.STATION_PAGE
        self.title = data['stationName']
        self.path = podcast_url(data['stationName'])

class Grid(Item):
    def __init__(self, data, index):
        super().__init__(data, index)
        self.title = data['metadata']['seo']['title']
        self.model = Model.GRID
        self.subs = data['grid']['steps']

class Program(Item):
    def __init__(self, data, index):
        super().__init__(data['concept'], index)
        self.model = Model.PROGRAM
        if 'expression' in data and data['expression'] is not None:
            self.subs += [data['expression'] | {'model': "Expression"}]

class Tag(Item):
    def __init__(self, data, index):
        super().__init__(data, index)
        self.path = podcast_url(data['path'])
        self.subs = data.get('documents', {'items': []})['items']
        document = data.get('documents', {})
        pagination = document.get('pagination', {'pageNumber': 1})
        self.pages = (pagination['pageNumber'], pagination.get('lastPage', pagination['pageNumber']))

class Search(Item):
    def __init__(self, data, index):
        super().__init__(data, index)
        self.subs = data['items']['concepts']['contents'] + data['items']['expressions_articles']['contents']

class Article(Item):
    def __init__(self, data, index):
        super().__init__(data, index)

class Other(Item):
    def __init__(self, data, index):
        super().__init__(data, index)
        if 'link' in data and isinstance(data['link'], str) and data['link'] != "":
            self.path = podcast_url(data['link'])
        self.subs = []
        if "items" in data:
            if isinstance(data['items'], dict):
                for k in ['concepts', 'personalities', 'expressions_articles']:
                    if k in data['items']:
                        self.subs += data['items'][k]['contents']
            elif isinstance(data['items'], list):
                self.subs += data['items']
            else:
                self.subs = data['items'] if "items" in data else []

class PageTemplate(Item):
    def __init__(self, data, index):
        super().__init__(data, index)
        if data['model'].upper() == Model.PAGETEMPLATE.name:
            self.subs = [data.get('layout', None)]

class ManifestationAudio(Item):
    def __init__(self, data, index):
        super().__init__(data, index)
        if data['model'].upper() == Model.MANIFESTATIONAUDIO.name:
            self.path = podcast_url(data['url'])
            self.duration = int(data['duration'])
            self.release = strftime("%d-%m.%y", localtime(data['created']))

class Concept(Item):
    def __init__(self, data, index):
        super().__init__(data, index)
        self.model = Model.CONCEPT
        expressions = data.get('expressions', {'pageNumber': 1})
        self.subs = expressions.get('items', data.get('promoEpisode', {'items': []})['items'])
        self.pages = (expressions['pageNumber'], expressions.get('lastPage', expressions['pageNumber']))

class Highlight(Item):
    def __init__(self, data, index):
        super().__init__(data, index)
        if data['model'].upper() == Model.HIGHLIGHT.name:
            self.subs = data['highlights']
            if self.title is None and len(self.subs) == 1:
                self.title = self.subs[0]['title']

class HighlightElement(Item):
    def __init__(self, data, index):
        super().__init__(data, index)
        if data['model'].upper() == Model.HIGHLIGHTELEMENT.name:
            if 0 < len(data['links']):
                url = data['links'][0]['path']
                if data['links'][0]['type'] == "path":
                    local_link = data['context']['station'] if 'context' in data else ""
                    self.path = podcast_url(url, local_link)
                else:
                    self.path = podcast_url(url)
            self.subs = data.get('contents',[])
            self.image = data['mainImage']['src'] if data['mainImage'] is not None else None
            if self.title is None and len(self.subs) == 1:
                self.title = self.subs[0]['title']

class Brand(Item):
    def __init__(self, data, index):
        super().__init__(data, index)
        brand = data.get('slug', data.get('brand', "franceinter"))
        url = podcast_url(brand.split("_")[0] + BRAND_EXTENSION + brand)
        data = fetch_data(url)

        self.model = Model.BRAND
        self.station = data['stationName']
        self.now = data['now']['firstLine']['title']
        self.title = f"{self.now} ({self.station})"
        self.artists = data['now']['secondLine']['title']
        self.duration = 0
        try:
            self.release = data['now']['song']['release']['title']
        except:
            self.release = None
        self.genre = data['now']['thirdLine']['title']
        self.image = None
        for key in ['mainImage', 'visual']:
            if key in data and data[key] is not None and "src" in data[key]:
                self.image = data[key]['src']
        self.icon = None
        for key in ['squaredVisual']:
            if key in data and data[key] is not None and "src" in data[key]:
                self.icon = data[key]['src']
        self.path = data['now']['media']['sources'][0]['url']

class Slug(Item):
    def __init__(self, data, index):
        super().__init__(data, index)
        self.model = Model.SLUG
        name = data['slug']
        self.path = podcast_url(name)
        self.title = data.get('brand', name)

class Expression(Item):
    def __init__(self, data, index):
        super().__init__(data, index)
        self.model = Model.EXPRESSION
        self.artists = ", ".join([g['name'] for g in (data['guest'] if "guest" in data else [])])
        self.release = strftime("%d-%m.%y", localtime(data['publishedDate'])) if "publishedDate" in data else ""
        self.duration = 0
        manifestations_audio = list([d for d in data.get('manifestations', []) if d['model'] == "ManifestationAudio"])
        if 0 < len(manifestations_audio):
            manifestation = create_item(self.index, next(filter(lambda d: d['principal'], manifestations_audio), data['manifestations'][0]))
            self.duration = manifestation.duration
            self.path = podcast_url(manifestation.path)

class Theme(Item):
    pass

class EmbedImage(Item):
    pass

class BrandPage:
    def __init__(self, data, index):
        self.title = data['stationName']
        self.image = None
        for key in ['mainImage', 'visual']:
            if key in data and data[key] is not None and "src" in data[key]:
                self.image = data[key]['src']
        self.icon = None
        for key in ['squaredVisual']:
            if key in data and data[key] is not None and "src" in data[key]:
                self.icon = data[key]['src']
        self.path = data['now']['media']['sources'][0]['url']

def expand_json(data):
    parsed = json.loads(data)['nodes'][-1]['data']

    def expand_element(e):
        if isinstance(e, dict):
            return expand_dict(e)
        elif isinstance(e, tuple):
            return expand_tuple(e)
        elif isinstance(e, list):
            return expand_tuple(e)
        a = parsed[e]
        if isinstance(a, dict):
            return expand_dict(a)
        elif isinstance(a, tuple):
            return expand_tuple(a)
        elif isinstance(a, list):
            return expand_tuple(a)
        return a

    def expand_tuple(element):
        return [expand_element(v) for v in element]

    def expand_dict(element):
        return {k: expand_element(v) for k, v in list(element.items())}

    return expand_element(parsed[0])

def podcast_url(url, local=""):
    if url is None:
        return None
    return RADIOFRANCE_PAGE + local + "/" + url if url[:8] != "https://" else url

def localize(string_id: int, **kwargs) -> str:
    import xbmcaddon
    ADDON = xbmcaddon.Addon()
    if not isinstance(string_id, int) and not string_id.isdecimal():
        return string_id
    return ADDON.getLocalizedString(string_id)

def build_url(query):
    base_url = sys.argv[0]
    url = base_url + "?" + urlencode(query, quote_via=quote_plus)
    return url

def combine(l):
    while True:
        try:
            yield [next(a) for a in l]
        except StopIteration:
            break

if __name__ == "__main__":
    data = sys.stdin.read()
    data = expand_json(data)
    # print(json.dumps(data))
    # exit(0)

    item = create_item_from_page(data)
    subs = item.subs
    while 1 < len(sys.argv):
        index = int(sys.argv.pop())
        print(f"Using index: {index}")
        subs = create_item(0, subs[index]).subs

    def display(item):
        if isinstance(item, Item):
            if len(item.subs) != 0 or (item.path is not None and item.path != ""):
                print(item)
                if len(item.subs) == 1:
                    display(create_item(0, item.subs[0]))
        else:
            (_, data, e) = item
            print(f"Error : {e} on {json.dumps(data)}")
            raise e

    display(item)
    with ThreadPoolExecutor() as p:
        sub_items = list(p.map(create_item, itertools.count(), iter(subs)))
        list(map(display, sub_items))
