#!/bin/python3

from urllib.parse import urlencode, quote_plus
import json
import sys
from enum import Enum
from time import localtime, strftime

RADIOFRANCE_PAGE = "https://www.radiofrance.fr/"
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


def create_item(data):
    # item = Item(data["podcastsData"] if "podcastsData" in data else data["content"] if "content" in data else data["layout"] if "layout" in data else data)

    if "model" not in data:
        if  "content" in data:
            data = data["content"]
        elif "layout" in data:
            data = data["layout"]
        elif "podcastsData" in data:
            data = data["podcastsData"]
        else:
            return None

    match data["model"]:
        case Model.Brand.name:
            item = Brand(data)
        case Model.Theme.name:
            item = Theme(data)
        case Model.Concept.name:
            item = Concept(data)
        case Model.Highlight.name:
            item = Highlight(data)
        case Model.HighlightElement.name:
            item = HighlightElement(data)
        case Model.Expression.name:
            item = Expression(data)
        case Model.ManifestationAudio.name:
            item = ManifestationAudio(data)
        case Model.EmbedImage.name:
            item = EmbedImage(data)
        case Model.PageTemplate.name:
            item = PageTemplate(data)
        case _:
            return None

    # Remove singletons
    item.elements = item.subs
    while len(item.elements) == 1 and item.elements[0] is not None:
        item.elements = item.elements[0].elements
    return item


class Item:
    def __init__(self, data):
        self.id = data["id"]

        # Model
        self.model = Model[data["model"]] if "model" in data else Model["Other"]
        # Path
        self.path = data["path"] if "path" in data else None

        # Sub elements
        self.subs = []
        self.elements = []

        # Image
        self.image = data["visual"]["src"] if "visual" in data and data["visual"] is not None else None
        self.icon = data["squaredVisual"]["src"]if "squaredVisual" in data and data["squaredVisual"] is not None else None

        # Other pages (tuple (x,n): current page x over n)
        self.pages = (1, 1)
        if "pagination" in data:
            self.pages = (
                data["pagination"]["pageNumber"],
                data["pagination"]["lastPage"],
            )

        # Title
        self.title = str(data["title"]) if "title" in data and data["title"] is not None else None

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
            + str(self.id)
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

class PageTemplate(Item):
    def __init__(self, data):
        super().__init__(data)
        if data["model"] == Model.PageTemplate.name:
            self.subs = [create_item(i) for i in [data["layout"]]]
        else:
            self = None

class ManifestationAudio(Item):
    def __init__(self, data):
        super().__init__(data)
        if data["model"] == Model.ManifestationAudio.name:
            self.path = data["url"]
            self.duration = int(data["duration"])

class Highlight(Item):
    def __init__(self, data):
        super().__init__(data)
        if data["model"] == Model.Highlight.name:
            self.subs = [create_item(i) for i in data["elements"]]

class Concept(Item):
    def __init__(self, data):
        super().__init__(data)
        if data["model"] == Model.Concept.name:
            if "expressions" in data:
                self.subs = [create_item(i) for i in data["expressions"]["items"]]
                self.pages = (data["expressions"]["pageNumber"], data["expressions"]["lastPage"])
            elif "promoEpisode" in data:
                self.subs = [create_item(i) for i in data["promoEpisode"]["items"]]

class Highlight(Item):
    def __init__(self, data):
        super().__init__(data)
        if data["model"] == Model.Highlight.name:
            self.subs = [create_item(i) for i in data["elements"]]

            # Update title if necessary
            if self.title is None and len(self.subs) == 1 :
                self.title = self.subs[0].title

class HighlightElement(Item):
    def __init__(self, data):
        super().__init__(data)
        if data["model"] == Model.HighlightElement.name:
            if 0 < len(data["links"]):
                self.path = RADIOFRANCE_PAGE + data["links"][0]["path"]
            self.subs = [create_item(i) for i in data["contents"]]
            self.image = data["mainImage"]["src"] if data["mainImage"] is not None else None

class Brand(Item):
    def __init__(self, data):
        super().__init__(data)
        if data["model"] == Model.Brand.name:
            name = data["slug"]
            self.path = RADIOFRANCE_PAGE + name.split("_")[0] + BRAND_EXTENSION + name
            self.title = data["shortTitle"]

class Expression(Item):
    None

class Brand_page:

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


def build_url(query):
    base_url = sys.argv[0]
    url = base_url + "?" + urlencode(query, quote_via=quote_plus)
    return url


if __name__ == "__main__":
    data = sys.stdin.read()
    data = expand_json(data)
    # print(json.dumps(data))

    item = create_item(data)
    print(str(item))

    if 1 < len(sys.argv):
        index = int(sys.argv[1])
        subs = Item(item.subs[index]).elements
    else:
        subs = item.subs

    for data in subs:
        sub_item = data
        while sub_item.is_folder() and len(sub_item.subs) == 1 and sub_item.path is None:
            sub_item = sub_item.subs[0]
        print(str(sub_item))

