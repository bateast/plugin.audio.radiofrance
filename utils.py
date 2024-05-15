#!/bin/python3

from urllib.parse import urlencode, quote_plus
import json
import sys
from enum import Enum
from time import localtime, strftime

RADIOFRANCE_PAGE = "https://www.radiofrance.fr/"
local_link = "podcasts/"
BRAND_EXTENSION = "/api/live/webradios/"


class Model(Enum):
    Other = 0
    Theme = 1
    Concept = 2
    Highlight = 3
    HighlightElement = 4
    Expression = 5
    ManifestationAudio = 6
    EmbedImage = 7
    PageTemplate = 8
    Brand = 9


def create_item_from_page(data):

    global local_link
    local_link = data['context']['station'] if 'context' in data else ""

    if "model" not in data:
        if "content" in data:
            data = data["content"]
        elif "layout" in data:
            data = data["layout"]
        elif "podcastsData" in data:
            data = data["podcastsData"]

    item = create_item(data)
    while len(item.subs) == 1:
        item = create_item(item.subs[0])
    return item


def create_item(data):
    match_list = {
        Model.Other.name: Other,
        Model.Brand.name: Brand,
        Model.Theme.name: Theme,
        Model.Concept.name: Concept,
        Model.Highlight.name: Highlight,
        Model.HighlightElement.name: HighlightElement,
        Model.Expression.name: Expression,
        Model.ManifestationAudio.name: ManifestationAudio,
        Model.EmbedImage.name: EmbedImage,
        Model.PageTemplate.name: PageTemplate,
    }

    item = match_list[data["model"] if "model" in data else "Other"](data)
    # Remove singletons
    if item.path is None and len(item.subs) == 1:
        item = create_item(item.subs[0])

    item.elements = item.subs
    while len(item.elements) == 1 and item.elements[0] is not None:
        item.elements = create_item(item.elements[0]).elements

    return item


class Item:
    def __init__(self, data):
        self.id = data["id"] if 'id' in data else "x" * 8

        # Model
        self.model = Model[data["model"]] if "model" in data else Model["Other"]
        # Path
        self.path = podcast_url(data["path"] if "path" in data else None)

        # Sub elements
        self.subs = []
        self.elements = []

        # Image
        self.image = (
            data["visual"]["src"]
            if "visual" in data
            and data["visual"] is not None
            and "src" in data["visual"]
            else None
        )
        self.icon = (
            data["squaredVisual"]["src"]
            if "squaredVisual" in data and data["squaredVisual"] is not None
            else None
        )

        # Other pages (tuple (x,n): current page x over n)
        self.pages = (1, 1)
        if "pagination" in data:
            self.pages = (
                data["pagination"]["pageNumber"],
                data["pagination"]["lastPage"] if "lastPage" in data["pagination"] else data["pagination"]["pageNumber"],
            )

        # Title
        self.title = (
            str(data["title"])
            if "title" in data and data["title"] is not None
            else None
        )

    def __str__(self):
        return (
            str(self.pages)
            if self.pages != (1, 1)
            else ""
            + str(self.title)
            + " ["
            + str(self.model)
            + "]"
            + " ["
            + str(len(self.elements))
            + "] ("
            + str(self.path)
            + ")"
            + " — "
            + str(self.id[:8])
        )

    def is_folder(self):
        return self.model in [
            Model["Theme"],
            Model["Concept"],
            Model["Highlight"],
            Model["HighlightElement"],
            Model["PageTemplate"],
            Model["Brand"],
        ]

    def is_image(self):
        return self.model in [Model["EmbedImage"]]

    def is_audio(self):
        return not self.is_folder() and not self.is_image()


class Other(Item):
    def __init__(self, data):
        super().__init__(data)

        self.subs = []
        if "items" in data:
            if isinstance(data['items'], dict):
                for k in ["concepts", "personalities", "expressions_articles"]:
                    if k in data['items']:
                        self.subs += data['items'][k]['contents']
            elif isinstance(data['items'], list):
                self.subs += data["items"]
            else:
                self.subs = data["items"] if "items" in data else []


class PageTemplate(Item):
    def __init__(self, data):
        global local_link
        super().__init__(data)
        if data["model"] == Model.PageTemplate.name:
            self.subs = [data["layout"]] if "layout" in data else []


class ManifestationAudio(Item):
    def __init__(self, data):
        super().__init__(data)
        if data["model"] == Model.ManifestationAudio.name:
            self.path = podcast_url(data["url"])
            self.duration = int(data["duration"])
            self.release = strftime("%d-%m.%y", localtime(data["created"]))


class Concept(Item):
    def __init__(self, data):
        super().__init__(data)
        if data["model"] == Model.Concept.name:
            if "expressions" in data:
                self.subs = data["expressions"]["items"]
                self.pages = (
                    data["expressions"]["pageNumber"],
                    data["expressions"]["lastPage"],
                )
            elif "promoEpisode" in data:
                self.subs = data["promoEpisode"]["items"]


class Highlight(Item):
    def __init__(self, data):
        super().__init__(data)
        if data["model"] == Model.Highlight.name:
            self.subs = data["elements"]

            # Update title if necessary
            if self.title is None and len(self.subs) == 1:
                self.title = self.subs[0]["title"]


class HighlightElement(Item):
    def __init__(self, data):
        super().__init__(data)
        if data["model"] == Model.HighlightElement.name:
            if 0 < len(data["links"]):
                url = data["links"][0]["path"]
                if data['links'][0]['type'] == "path":
                    self.path = podcast_url(url, local_link)
                else:
                    self.path = podcast_url(url)
            self.subs = data["contents"]
            self.image = (
                data["mainImage"]["src"] if data["mainImage"] is not None else None
            )

            # Update title if necessary
            if self.title is None and len(self.subs) == 1:
                self.title = self.subs[0]["title"]


class Brand(Item):
    def __init__(self, data):
        super().__init__(data)
        if data["model"] == Model.Brand.name:
            name = data["slug"]
            self.path = podcast_url(name.split("_")[0] + BRAND_EXTENSION + name)
            self.title = data["shortTitle"]


class Expression(Item):
    def __init__(self, data):
        super().__init__(data)
        if data["model"] == Model.Expression.name:
            self.artists = ", ".join([g["name"] for g in (data["guest"] if "guest" in data else [])])
            self.release = strftime("%d-%m.%y", localtime(data["publishedDate"])) if "publishedDate" in data else ""
            self.duration = 0
            if 0 < len(data["manifestations"]):
                manifestation = create_item(
                    next(filter(lambda d: d["principal"], data["manifestations"]), data["manifestations"][0])
                )
                self.duration = manifestation.duration
                self.path = podcast_url(manifestation.path)


class Theme(Item):
    None


class EmbedImage(Item):
    None


class BrandPage:
    def __init__(self, page):
        data = json.loads(page)
        self.title = data["stationName"]
        self.image = None
        for key in ["mainImage", "visual"]:
            if key in data and data[key] is not None and "src" in data[key]:
                self.image = data[key]["src"]
        self.icon = None
        for key in ["squaredVisual"]:
            if key in data and data[key] is not None and "src" in data[key]:
                self.icon = data[key]["src"]
        self.url = data["now"]["media"]["sources"][0]["url"]


def expand_json(data):
    parsed = json.loads(data)["nodes"][-1]["data"]

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
        return {k: expand_element(v) for k, v in element.items()}

    return expand_element(parsed[0])


def podcast_url(url, local=""):
    if url is None:
        return None
    return RADIOFRANCE_PAGE + local + "/" + url if url[:8] != "https://" else "" + url


def build_url(query):
    base_url = sys.argv[0]
    url = base_url + "?" + urlencode(query, quote_via=quote_plus)
    return url


if __name__ == "__main__":
    data = sys.stdin.read()
    data = expand_json(data)
    # print(json.dumps(data))
    # exit()

    item = create_item_from_page(data)
    print(str(item))

    if 1 < len(sys.argv):
        index = int(sys.argv[1])
        print("Using index: " + str(index))
        subs = create_item(item.subs[index]).elements
    else:
        subs = item.subs

    for data in subs:
        sub_item = create_item(data)
        print(str(sub_item))
