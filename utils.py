#!/bin/python3

from urllib.parse import urlencode, quote_plus
import json
import sys
from enum import Enum
from time import localtime, strftime


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


class Item:
    def __init__(self, data):
        # Model
        self.model = Model[data["model"]] if "model" in data else Model["Other"]
        # Path
        self.path = (
            data["manifestations"][0]["url"]
            if self.model == Model["Expression"] and "manifestations" in data and data["manifestations"] != []
            else data["path"]
            if "path" in data and data["path"] is not None and data["path"] != ""
            else data["links"][0]["path"]
            if "links" in data and data["links"] != []
            else data["slug"] if self.model == Model["Brand"]
            else None
        )
        if not self.is_folder():
            # Guests
            self.artists = ", ".join([g["name"] for g in data["guest"]]) if "guest" in data else ""
            # Duration
            self.duration = int(data["manifestations"][0]["duration"]) if "manifestations" in data and data["manifestations"] != [] else 0
            # Release
            self.release = strftime("%d-%m.%y", localtime(data["publishedDate"])) if "publishedDate" in data else None
        # Sub elements
        if self.model == Model["Highlight"]:
            self.subs = data["elements"]
        elif "layout" in data:
            self.subs = data["layout"]["elements"]
        elif "elements" in data:
            self.subs = data["elements"]
        elif "contents" in data and 0 < len(data["contents"]):
            self.subs = data["contents"]
        elif "content" in data and "layout" in data["content"]:
            self.subs = data["content"]["layout"]
        elif "content" in data and "expressions" in data["content"]:
            self.subs = data["content"]["expressions"]
        elif "expressions" in data:
            self.subs = data["expressions"]["items"]
        elif "pagination" in data:
            self.subs = data["pagination"]["items"]
        else:
            self.subs = []
        # Remove singletons
        self.elements = self.subs
        while len(self.elements) == 1:
            self.elements = Item(self.elements[0]).subs

        # Image
        self.image = None
        for key in ["mainImage", "visual"]:
            if key in data and data[key] is not None and "src" in data[key]:
                self.image = data[key]["src"]
        self.icon = None
        for key in ["squaredVisual"]:
            if key in data and data[key] is not None and "src" in data[key]:
                self.icon = data[key]["src"]
        # Other pages (tuple (x,n): current page x over n)
        self.pages = (1, 1)
        if "pageNumber" in data and "lastPage" in data:
            self.pages = (data["pageNumber"], data["lastPage"])
        elif "pagination" in data:
            self.pages = (
                data["pagination"]["pageNumber"],
                data["pagination"]["lastPage"],
            )

        # Title
        self.title = (
            str(data["title"])
            if "title" in data and data["title"] is not None
            else self.subs[0]["title"]
            if len(self.subs) == 1
            else data["shortTitle"]
            if "shortTitle" in data
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


class Brand:

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
    # print(json.dumps(expanded))

    item = Item(data["podcastsData"] if "podcastsData" in data else data["content"] if "content" in data else data["layout"] if "layout" in data else data)
    print(str(item))

    if 1 < len(sys.argv):
        index = int(sys.argv[1])
        subs = Item(item.subs[index]).elements
    else:
        subs = item.subs

    for data in subs:
        sub_item = Item(data)
        while sub_item.is_folder() and len(sub_item.subs) == 1 and sub_item.path is None:
            sub_item = Item(sub_item.subs[0])
        print(str(sub_item))

