#!/usr/bin/python3

from urllib.parse import urlencode, quote_plus
import base64
import json
import sys
import time
import requests
from enum import Enum
from time import localtime, strftime
from concurrent.futures import ThreadPoolExecutor
import itertools

RADIOFRANCE_PAGE = "https://www.radiofrance.fr"
# The site's player endpoints ("transistor"):
#  - live radios: `transistor/live/<brand id>` gives the stream (HLS) and the name of the
#    "now playing" rule (`liveApiRule`), which is then looked up under LIVEMETA_URL;
#  - episodes: `transistor/aod/<expression id>` gives the audio files.
TRANSISTOR_PATH = "/transistor/live/"
AOD_PATH = "/transistor/aod/"
LIVEMETA_URL = "https://api.radiofrance.fr/livemeta/"
SITE_HEADERS = {"Referer": RADIOFRANCE_PAGE + "/", "Origin": RADIOFRANCE_PAGE}  # what the site's own player sends
# Search is a SvelteKit "remote function" call: /_app/remote/<hash>/<name>?payload=<devalue args>.
# The hash identifies the site's search module (it was the same across captures a day apart, but
# it is the one thing here that a site rebuild might change: if search stops working, capture a
# search in the browser's network tab, look for `getSearchItems`, and update it).
SEARCH_REMOTE = "/_app/remote/7lqoro/getSearchItems"
HTTP_TIMEOUT = 15
LIVE_TTL = 60  # seconds a live-station answer is reused

# Old data model: `format` values that are not browsable items.
NOT_ITEM_FORMAT = ["TYPED_ELEMENT_NEWSLETTER_SUBSCRIPTION", "TYPED_ELEMENT_AUTOPROMO_IMMERSIVE"]
# New data model: HighlightElement `kind` values that are not browsable items
# (newsletter sign-up, "ask the Radio France AI" promo).
NOT_ITEM_KIND = ["newsletter_subscription", "ebu"]

# Keys under which a node may carry its children, most specific first. Only the
# first non-empty one is used: several of them repeat the same children
# (e.g. `items` is the union of `mainItem` and `secondaryItems`).
SUB_KEYS = ('items', 'highlights', 'documents', 'expressions', 'promoEpisode', 'item',
            'elements', 'elementAt', 'mainItem', 'secondaryItems', 'mainItem1_6', 'secondaryItems1_6')

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
    SLIDER = 19
    ARTICLEVIDEO = 20
    EMBEDVIDEO = 21

    @classmethod
    def from_data(cls, data):
        return cls.__members__.get(typename(data), cls.OTHER)

class Format(Enum):
    SLIDER_CHAINE = 1

def typename(data):
    """Upper-cased model name of a node, for both data models.

    New model: `__typename` ("Expression", "Highlight_SLIDER_EPISODE", ...).
    Old model: `model`. All `Highlight_<FORMAT>` flavours are plain highlights.
    """
    raw = data.get('__typename') or data.get('model') or ""
    if not isinstance(raw, str):
        return ""
    if raw.startswith("Highlight_"):
        return "HIGHLIGHT"
    return raw.upper()

def fetch_data(url, headers=None):
    response = requests.get(url, headers=headers, timeout=HTTP_TIMEOUT)
    response.raise_for_status()
    return response.json()

_live_cache = {}

def fetch_live(url):
    """fetch_data() with a short-lived cache: "now playing" is asked for every brand on every listing."""
    hit = _live_cache.get(url)
    if hit is not None and time.time() - hit[0] < LIVE_TTL:
        if isinstance(hit[1], Exception):
            raise hit[1]
        return hit[1]
    try:
        data = fetch_data(url, SITE_HEADERS)
    except Exception as e:
        _live_cache[url] = (time.time(), e)  # don't hammer an endpoint that is failing
        raise
    _live_cache[url] = (time.time(), data)
    return data

def _dig(data, *keys):
    for key in keys:
        if not isinstance(data, dict):
            return None
        data = data.get(key)
    return data

def _clean(value):
    return value.strip() if isinstance(value, str) and value.strip() else None

def image_src(visual):
    """URL of an image node. New model images may only carry an `id`: the CDN serves it from /pikapi/images/<id>."""
    if not isinstance(visual, dict):
        return None
    if _clean(visual.get('src')):
        return visual['src']
    if _clean(visual.get('id')):
        return f"{RADIOFRANCE_PAGE}/pikapi/images/{visual['id']}"
    return None

def get_key_src(key, data):
    if not isinstance(data, dict):
        return None
    return image_src(data.get(key))

def first_src(data, keys):
    for key in keys:
        src = get_key_src(key, data)
        if src:
            return src
    return None

def station_prefix(context):
    station = context.get('station') if isinstance(context, dict) else None
    return "/" + station if isinstance(station, str) and station else ""

def find_title(data):
    for value in (data.get('title'), _dig(data, 'titleProps', 'title')):
        if _clean(value):
            return value.strip()
    return ""

def find_path(data, context):
    """Where a node leads to. Handles `link`, `path`, `href`, `titleProps.href` and `originPath`."""
    link = data.get('link')
    if isinstance(link, dict) and link.get('type', "") != "mail":
        url_station = station_prefix(context) if data.get('format') == "TYPED_ELEMENT_AUTOPROMO" else ""
        for key in ('path', 'url', 'href'):
            if _clean(link.get(key)):
                return podcast_url(link[key], url_station)
    for value in (data.get('path'), data.get('href'), _dig(data, 'titleProps', 'href'), data.get('originPath')):
        if _clean(value):
            return podcast_url(value.strip())
    return None

def format_release(timestamp):
    try:
        return strftime("%Y-%m-%d", localtime(int(timestamp)))
    except (TypeError, ValueError, OverflowError, OSError):
        return None

def is_not_item(data):
    if not isinstance(data, dict):
        return False
    if str(data.get('format', "")).upper() in NOT_ITEM_FORMAT:
        return True
    return typename(data) == Model.HIGHLIGHTELEMENT.name and data.get('kind') in NOT_ITEM_KIND

def _unwrap(value):
    """Flatten the various ways children are nested (list, {contents: ...}, {items: ...}, single node)."""
    if isinstance(value, list):
        return list(itertools.chain.from_iterable(_unwrap(v) for v in value))
    if isinstance(value, dict):
        if not typename(value):
            for key in ('contents', 'items'):
                if key in value:
                    return _unwrap(value[key])
        return [value]
    return []

def collect_subs(data, keys=SUB_KEYS):
    for key in keys:
        subs = [s for s in _unwrap(data.get(key)) if not is_not_item(s)]
        if subs:
            return subs
    return []

def _pagination(data):
    pagination = data.get('pagination')
    if not isinstance(pagination, dict):
        pagination = {}
    number = pagination.get('pageNumber', 1)
    return (number, pagination.get('lastPage', number))

def remote_payload(args):
    """`payload` query value of a SvelteKit remote function call: the arguments object in devalue's
    flat form (every value of an object/array is the *index* of another entry; the root is tagged
    `__skrao`), JSON-serialised then base64url-encoded without padding."""
    flat = [["__skrao", 1], None]
    seen = {}

    def add(value):
        if value is None:
            return -1  # undefined
        if isinstance(value, (list, tuple)):
            flat.append(None)
            index = len(flat) - 1
            flat[index] = [add(v) for v in value]
            return index
        key = (type(value), value)
        if key not in seen:  # devalue stores a given primitive once
            flat.append(value)
            seen[key] = len(flat) - 1
        return seen[key]

    flat[1] = {k: add(v) for k, v in args.items()}
    raw = json.dumps(flat, separators=(',', ':'), ensure_ascii=False)
    return base64.urlsafe_b64encode(raw.encode()).rstrip(b'=').decode()

def fetch_remote(url, headers=None):
    """Call a SvelteKit remote function and decode its devalue-encoded result."""
    answer = fetch_data(url, headers)
    if answer.get('type') != 'result':
        raise ValueError(f"remote function failed: {str(answer)[:200]}")
    return devalue_parse(json.loads(answer['result']))

def fetch_search(term):
    """Results of a search as a page (`content` = concepts, personalities and expressions/articles)."""
    args = {'durations': [], 'entities': [], 'globalAggregations': False, 'limitConcepts': 6,
            'sort': None, 'stations': [], 'term': term, 'years': []}
    headers = dict(SITE_HEADERS, Referer=f"{RADIOFRANCE_PAGE}/recherche?q={quote_plus(term)}")
    content = fetch_remote(f"{RADIOFRANCE_PAGE}{SEARCH_REMOTE}?{urlencode({'payload': remote_payload(args)})}", headers)
    return {'content': content, 'context': {'station': None}}

class ItemCreationError(Exception):
    """An item could not be built from `data`; wraps the exception that was raised."""
    def __init__(self, data, original_exception):
        super().__init__(f"{type(original_exception).__name__}: {original_exception}")
        self.data = data
        self.original_exception = original_exception

def create_item_from_page(data):
    context = data.get('context', {})

    if not typename(data):
        for key in ("content", "layout", "podcastsData"):
            if key in data:
                data = data[key]
                break

    item = create_item(0, data, context)
    index = 0
    while len(item.subs) == 1:
        try:
            item = create_item(index, item.subs[0], context)
        except ItemCreationError:
            break
        index += 1
    return item

def create_item(index, data, context = None):
    context = context if context is not None else {}
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
        Model.ARTICLEVIDEO.name: ArticleVideo,
        Model.EVENT.name: Event,
        Model.SLUG.name: Slug,
        Model.STATIONPAGE.name: StationPage,
        Model.STATION.name: Station,
        Model.GRID.name: Grid,
        Model.PROGRAM.name: Program
    }
    format_map = {
        Format.SLIDER_CHAINE.name : Slider
    }

    try:
        if typename(data) in model_map:
            model_class = model_map[typename(data)]
            item = model_class(data, index, context)
        elif str(data.get('format') or "").upper() in format_map:
            format_class = format_map[data['format'].upper()]
            item = format_class(data, index, context)
        elif 'stationName' in data:
            item = StationDir(data, index, context)
        elif 'items' in data and isinstance(data['items'], dict) and 'concepts' in data['items'] and 'expressions_articles' in data['items']:
            item = Search(data, index, context)
        elif 'concepts' in data and 'expressionsArticles' in data:
            item = Search(data, index, context)
        elif 'slug' in data:
            item = model_map['SLUG'](data, index, context)
        elif isinstance(data.get('brand'), str) and not typename(data) and not data.get('format') in NOT_ITEM_FORMAT :
            item = model_map['BRAND'](data, index, context)
        elif 'grid' in data:
            item = model_map['GRID'](data, index, context)
        elif 'concept' in data and 'expression' in data:
            item = model_map['PROGRAM'](data, index, context)
        else:
            item = model_map['OTHER'](data, index, context)
    except Exception as e:
        raise ItemCreationError(data, e) from e

    item.index = index
    item.clean_subs()
    item.remove_singletons()
    return item

class Item:
    def __init__(self, data, index, context = None):
        self.id = str(data.get('id') or "x" * 8)
        self.context = context if context is not None else {}
        self.model = Model.from_data(data)
        self.path = find_path(data, self.context)
        self.subs = []
        self.image = first_src(data, ('visual', 'mainImage', 'poster', 'landscape'))
        self.icon = first_src(data, ('squaredVisual', 'square', 'round'))
        self.pages = _pagination(data)
        self.title = find_title(data)
        self.index = index
        # Attributes read by the GUI layer for anything playable
        self.artists = ""
        self.duration = 0
        self.release = None
        self.genre = "podcast"
        self.lazy = False  # True: `path` is a page to resolve to a stream when played

    def clean_subs(self) :
        self.subs = list(filter(lambda i : i is not None, self.subs))

    def remove_singletons(self):
        """Collapse wrapper chains: a link-less container whose only child is itself a
        link-less container is replaced by that child's children. A leaf (playable) or a
        child with its own link is never swallowed."""
        while self.path is None and len(self.subs) == 1:
            try:
                child = create_item(self.index, self.subs[0], self.context)
            except ItemCreationError:
                break
            if child.path is not None or len(child.subs) == 0:
                break
            self.subs = child.subs

    def __str__(self):
        return (f"{self.pages}{''.join([f'{self.index}. {self.title} [{self.model}] [{len(self.subs)}] ({self.path}) — {self.id[:8]}'])}")

    def is_folder(self):
        return self.model in [Model.THEME, Model.CONCEPT, Model.HIGHLIGHT, Model.HIGHLIGHTELEMENT, Model.PAGETEMPLATE, Model.TAG, Model.ARTICLE, Model.SLUG, Model.STATIONPAGE, Model.GRID, Model.SLIDER, Model.OTHER]

    def is_image(self):
        return self.model in [Model.EMBEDIMAGE]

    def is_audio(self):
        return not self.is_folder() and not self.is_image()

class Event(Item):
    def __init__(self, data, index, context = None):
        super().__init__(data, index, context)
        self.path = podcast_url(data.get('href')) if data.get('href') else self.path

class StationDir(Item):
    def __init__(self, data, index, context = None):
        super().__init__(data, index, context)
        self.model = Model.STATIONPAGE
        self.title = data['stationName']
        self.subs += [dict(data, **{'model': "Station"}), dict(data, **{'model': "StationPage"})]

class Station(Item):
    def __init__(self, data, index, context = None):
        super().__init__(data, index, context)
        self.model = Model.STATION
        self.title = f"{data['stationName']}: {data['now']['secondLine']['title']}"
        self.artists = data['stationName']
        self.duration = None
        self.release = None
        self.path = data['now']['media']['sources'][0]['url'] if 0 < len(data['now']['media']['sources']) else None

class StationPage(Item):
    def __init__(self, data, index, context = None):
        super().__init__(data, index, context)
        self.model = Model.STATIONPAGE
        self.title = data['stationName']
        self.path = podcast_url(data['stationName'])

class Grid(Item):
    def __init__(self, data, index, context = None):
        super().__init__(data, index, context)
        self.title = data['metadata']['seo']['title']
        self.model = Model.GRID
        self.subs = data['grid']['steps']

class Program(Item):
    def __init__(self, data, index, context = None):
        super().__init__(data['concept'], index, context)
        self.model = Model.PROGRAM
        if 'expression' in data and data['expression'] is not None:
            self.subs += [data['expression'] | {'model': "Expression"}]

class Tag(Item):
    def __init__(self, data, index, context = None):
        super().__init__(data, index, context)
        documents = data.get('documents')
        self.subs = collect_subs(data, ('documents', 'items', 'highlights'))
        if isinstance(documents, dict):
            self.pages = _pagination(documents)

class Search(Item):
    def __init__(self, data, index, context = None):
        super().__init__(data, index, context)
        items = data.get('items')
        if isinstance(items, dict) and 'concepts' in items:  # old model
            self.subs = items['concepts']['contents'] + items['expressions_articles']['contents']
        else:  # concepts first, then people, then episodes/articles
            self.subs = [sub for key in ('concepts', 'personalities', 'expressionsArticles') for sub in collect_subs(data, (key,))]

class Article(Item):
    pass

class Other(Item):
    def __init__(self, data, index, context = None):
        super().__init__(data, index, context)
        items = data.get('items')
        if isinstance(items, dict) and any(k in items for k in ('concepts', 'personalities', 'expressions_articles')):
            for k in ['concepts', 'personalities', 'expressions_articles']:
                if k in items:
                    self.subs += _unwrap(items[k].get('contents', []))
        else:
            self.subs = collect_subs(data)

class PageTemplate(Item):
    def __init__(self, data, index, context = None):
        super().__init__(data, index, context)
        if _clean(data.get('slug')):
            self.path = podcast_url(data['slug'])
        self.title = _clean(data.get('label')) or self.title
        # new model: a flat `highlights` list; old model: a single `layout` node
        self.subs = collect_subs(data, ('highlights', 'items')) or collect_subs(data, ('layout',))

class ManifestationAudio(Item):
    def __init__(self, data, index, context = None):
        super().__init__(data, index, context)
        self.model = Model.MANIFESTATIONAUDIO
        if _clean(data.get('url')):
            self.path = podcast_url(data['url'])
        self.duration = int(data.get('duration') or 0)
        self.release = format_release(data.get('created'))

class ArticleVideo(Item):
    """Video report: the file is directly in `mainResource.url` (an EmbedVideo)."""
    def __init__(self, data, index, context = None):
        super().__init__(data, index, context)
        self.model = Model.ARTICLEVIDEO
        resource = data.get('mainResource') if isinstance(data.get('mainResource'), dict) else {}
        self.path = _clean(resource.get('url'))
        self.duration = int(data.get('duration') or resource.get('duration') or 0)
        self.artists = data.get('brand') or ""

class Concept(Item):
    def __init__(self, data, index, context = None):
        super().__init__(data, index, context)
        self.model = Model.CONCEPT
        self.title = self.title or _clean(data.get('text')) or ""  # search results: `title` is empty, the name is in `text`
        self.subs = collect_subs(data, ('expressions', 'promoEpisode', 'items'))
        expressions = data.get('expressions')
        # old model: page numbers inside `expressions`; new model: `pagination.lastPage` on the concept
        # itself (already read by Item) and cursor-only `expressions` (next/prev)
        if isinstance(expressions, dict) and ('pageNumber' in expressions or 'lastPage' in expressions):
            number = expressions.get('pageNumber', 1)
            self.pages = (number, expressions.get('lastPage', number))

class Highlight(Item):
    def __init__(self, data, index, context = None):
        super().__init__(data, index, context)
        self.subs = collect_subs(data)
        if not self.title and len(self.subs) == 1:
            self.title = find_title(self.subs[0])

class HighlightElement(Item):
    def __init__(self, data, index, context = None):
        super().__init__(data, index, context)
        links = data.get('links')
        if isinstance(links, list) and 0 < len(links) and isinstance(links[0], dict):
            link = links[0]
            url = next((link[k] for k in ('path', 'url', 'href') if _clean(link.get(k))), None)
            if url is not None:
                local_link = station_prefix(data.get('context', self.context)) if link.get('type') == "path" else ""
                self.path = podcast_url(url, local_link)
        self.subs = collect_subs(data, ('contents', 'content'))
        main_image = get_key_src('mainImage', data)
        if main_image:
            self.image = main_image
        if not self.title and len(self.subs) == 1:
            self.title = find_title(self.subs[0])

class Brand(Item):
    """A live radio, keyed by the brand `id` (1 = France Inter, 2 = franceinfo, ...).

    `transistor/live/<id>` gives the stream and, through `liveApiRule`, the "now playing"
    feed. The stream is what matters: if "now playing" can't be read the radio is still
    listed under its own name, and if the stream lookup fails the lookup is redone when played.
    """
    def __init__(self, data, index, context = None):
        super().__init__(data, index, context)
        brand = _clean(data.get('brand')) or _clean(data.get('slug')) or ""
        brand_id = data.get('id')
        self.model = Model.BRAND
        self.station = self.title or brand
        self.title = self.station
        self.genre = ""
        self.duration = 0
        if brand_id is None:
            self.path = None  # nothing to resolve a stream from: not listed
            return

        self.path = live_url(brand_id)
        try:
            live = fetch_live(self.path)
            stream = live_stream_url(live)
        except Exception:
            self.lazy = True  # path stays the lookup url
            return
        self.path = stream
        self.station = _clean(_dig(live, 'metadata', 'firstLine')) or self.station
        self.title = self.station
        try:
            now = fetch_live(LIVEMETA_URL + live['liveApiRule'].lstrip("/"))['now']
            self.title = f"{now['firstLine']} ({self.station})"
            self.artists = _clean(now.get('secondLine')) or ""
            self.image = image_src({'id': now.get('cover')}) or self.image
        except Exception:
            pass

def live_url(brand_id):
    return f"{RADIOFRANCE_PAGE}{TRANSISTOR_PATH}{brand_id}"

def live_stream_url(live):
    return live['sources'][0]['url']

class Slug(Item):
    def __init__(self, data, index, context = None):
        super().__init__(data, index, context)
        self.model = Model.SLUG
        name = data['slug']
        self.path = podcast_url(name)
        self.title = data.get('brand', name)

class Expression(Item):
    """An episode.

    Old data model: `manifestations` list, each ManifestationAudio carrying the audio `url`.
    New data model: listings only carry a ManifestationAudio with a `duration`; the audio
    URL is only in the episode's own page, so the item is `lazy` (see find_audio_url).
    """
    def __init__(self, data, index, context = None):
        super().__init__(data, index, context)
        self.model = Model.EXPRESSION
        guests = [g.get('name') for g in (data.get('guest') or []) if isinstance(g, dict) and g.get('name')]
        # no guest list in the new model: use the show name (`concept.title`, or `text` when it links to the show)
        show = _clean(_dig(data, 'concept', 'title')) or (_clean(data.get('text')) if _clean(data.get('textHref')) else None)
        self.artists = ", ".join(guests) or show or ""
        # `publishedDate` is an epoch on some pages but a display string ("Lundi 16 novembre 2026") on others
        stamp = next((v for v in (data.get('publishedDate'), data.get('startDate')) if isinstance(v, (int, float))), None)
        self.release = format_release(stamp)
        self.duration = int(data.get('duration') or 0)

        manifestations = audio_manifestations(data)
        main = next((m for m in manifestations if m.get('principal') and _clean(m.get('url'))), None) \
            or next((m for m in manifestations if _clean(m.get('url'))), None)
        if main is not None:
            self.path = podcast_url(main['url'])
            self.duration = int(main.get('duration') or self.duration)
        else:
            if not self.duration and manifestations:
                self.duration = int(manifestations[0].get('duration') or 0)
            if self.path is not None:  # has an episode page, i.e. is published
                self.lazy = True
                if _clean(data.get('id')):
                    self.path = aod_url(data['id'])  # else: resolved from the page itself

def audio_manifestations(data):
    candidates = list(data.get('manifestations') or [])
    if isinstance(data.get('manifestation'), dict):
        candidates.append(data['manifestation'])
    return [m for m in candidates if isinstance(m, dict) and typename(m) == Model.MANIFESTATIONAUDIO.name]

def aod_url(expression_id):
    return f"{RADIOFRANCE_PAGE}{AOD_PATH}{expression_id}"

def aod_stream_url(aod):
    """Best audio file of a `transistor/aod/<id>` answer (it offers AAC 192 kbps and MP3 128 kbps)."""
    sources = [src for src in aod.get('sources') or [] if isinstance(src, dict) and _clean(src.get('url'))]
    if not sources:
        raise ValueError("no audio source")
    return max(sources, key=lambda src: _dig(src, 'preset', 'bitrate') or 0)['url']

AUDIO_EXTENSIONS = ('.mp3', '.m4a', '.aac', '.ogg', '.m3u8')

def find_audio_url(page):
    """Audio stream of an episode page (`<episode>/__data.json`, already expanded).

    The page's own `content` is asked first (principal manifestation, then any); only if
    that fails is the whole page scanned, so that a "related episodes" block can't win.
    """
    root = page.get('content', page) if isinstance(page, dict) else page

    def urls(node):
        for m in audio_manifestations(node) if isinstance(node, dict) else []:
            if _clean(m.get('url')):
                yield (not m.get('principal'), m['url'])

    if isinstance(root, dict):
        best = sorted(urls(root), key=lambda t: t[0])
        if best:
            return best[0][1]

    def walk(node):
        if isinstance(node, dict):
            for m in node.get('manifestations') or []:
                if isinstance(m, dict) and _clean(m.get('url')):
                    yield m['url']
            url = node.get('url')
            if _clean(url) and url.split('?')[0].lower().endswith(AUDIO_EXTENSIONS):
                yield url
            for v in node.values():
                yield from walk(v)
        elif isinstance(node, list):
            for v in node:
                yield from walk(v)

    return next(walk(root), None)

class Slider(Item):
    def __init__(self, data, index, context = None):
        super().__init__(data, index, context)
        self.model = Model.SLIDER
        self.subs = collect_subs(data, ('items',))

class Theme(Item):
    def __init__(self, data, index, context = None):
        super().__init__(data, index, context)
        self.subs = collect_subs(data, ('documents', 'items', 'highlights'))

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

def devalue_parse(parsed):
    """Decode a SvelteKit `devalue` payload: a flat array where every value of an object /
    array is the *index* of another entry. Shared entries are decoded once (and so are
    shared objects), negative integers are devalue's sentinels for undefined/NaN/...
    """
    done = {}

    def hydrate(i):
        if i < 0:
            return -0.0 if i == -6 else None
        if i in done:
            return done[i]
        value = parsed[i]
        if isinstance(value, list):
            if value and isinstance(value[0], str):
                result = special(value[0], value[1:])
                done[i] = result
                return result
            result = []
            done[i] = result
            result.extend(hydrate(v) for v in value)
            return result
        if isinstance(value, dict):
            result = {}
            done[i] = result
            for k, v in value.items():
                result[k] = hydrate(v)
            return result
        done[i] = value
        return value

    def special(tag, args):
        if tag == "Date" or tag == "BigInt":
            return args[0] if tag == "Date" else int(args[0])
        if tag == "Set":
            return [hydrate(a) for a in args]
        if tag == "Map":
            return [[hydrate(k), hydrate(v)] for k, v in zip(args[::2], args[1::2])]
        if tag == "null":
            return {k: hydrate(v) for k, v in zip(args[::2], args[1::2])}
        return None

    return hydrate(0)

def expand_json(data):
    """Turn a SvelteKit `__data.json` response (text or already parsed) into the page dict.

    The response is a list of `nodes` (layout, page, ...); nodes that failed or were
    skipped are `null`/`skip`. The page node is the last one carrying `content` (current
    model) or `metadata` (old model). `context.station` is added when the page has none.
    """
    payload = json.loads(data) if isinstance(data, (str, bytes)) else data
    layout = {}
    page = None
    for node in payload.get('nodes', []):
        if not isinstance(node, dict) or node.get('type', 'data') != 'data' or not node.get('data'):
            continue
        decoded = devalue_parse(node['data'])
        if not isinstance(decoded, dict):
            continue
        if 'content' in decoded or 'metadata' in decoded:
            page = decoded
        else:
            layout.update(decoded)

    if page is None:
        raise ValueError("No page content found in __data.json")

    page = dict(page)
    if 'context' not in page:
        station = page.get('station') or layout.get('station')
        name = station.get('name') if isinstance(station, dict) else station
        page['context'] = {'station': name if name and name != "radiofrance" else None}
    return page

def podcast_url(url, local=""):
    if url is None:
        return None
    return (RADIOFRANCE_PAGE \
            + local \
            + ("/" if 0 < len(url) and url[0] != "/" else "" ) \
            + url) \
            if url[:8] != "https://"  else url

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

    def repeat(item):
        while True:
            yield item

    def display(item):
        if len(item.subs) != 0 or (item.path is not None and item.path != ""):
            print(item)
            if len(item.subs) == 1:
                display(create_item(0, item.subs[0], context))

    def safe_create_item(index, data, context):
        try:
            return create_item(index, data, context)
        except ItemCreationError as e:
            print(f"Error : {e} on {json.dumps(e.data)}")
            return None

    if sys.argv[1:] == ["audio"]:
        # python utils.py audio < episode___data.json : the stream the plugin would play
        print(find_audio_url(data))
        sys.exit(0)

    item = create_item_from_page(data)
    context = data.get('context', {})
    subs = item.subs
    while 1 < len(sys.argv):
        index = int(sys.argv.pop())
        print(f"Using index: {index}")
        subs = create_item(0, subs[index], context).subs

    # print(json.dumps(subs))
    display(item)
    with ThreadPoolExecutor() as p:
        sub_items = list(p.map(safe_create_item, itertools.count(), iter(subs), repeat(context)))
    list(map(display, filter(None, sub_items)))
