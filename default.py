import json
import sys
import requests
from urllib.parse import parse_qs
from enum import Enum

# http://mirrors.kodi.tv/docs/python-docs/
# http://www.crummy.com/software/BeautifulSoup/bs4/doc/
from urllib.parse import urlencode, quote_plus
from ast import literal_eval
import xbmc
import xbmcgui
import xbmcplugin

from utils import *


DEFAULT_MANIFESTATION = 0
RADIOFRANCE_PAGE = "https://www.radiofrance.fr"


def build_lists(data, args, url):
    xbmc.log(str(args), xbmc.LOGINFO)

    def add_search():
        new_args = {k: v[0] for (k, v) in args.items()}
        new_args["mode"] = "search"
        li = xbmcgui.ListItem(label="? Search term")
        li.setIsFolder(True)
        new_url = build_url(new_args)
        highlight_list.append((new_url, li, True))

    def add_pages(item):
        new_args = {k: v[0] for (k, v) in args.items()}
        pages = item.pages
        if 1 < pages["pageNumber"]:
            new_args["page"] = pages["pageNumber"] - 1
            li = xbmcgui.ListItem(label="<< Previous page")
            li.setIsFolder(True)
            new_url = build_url(new_args)
            highlight_list.append((new_url, li, True))
        if pages["pageNumber"] < pages["lastPage"]:
            new_args["page"] = pages["pageNumber"] + 1
            li = xbmcgui.ListItem(label=">> Next page")
            li.setIsFolder(True)
            new_url = build_url(new_args)
            highlight_list.append((new_url, li, True))

    highlight_list = []
    song_list = []

    mode = args.get("mode", [None])[0]
    if mode is None:
        add_search()

    item = create_item(data)
    if mode == "index":
        element_index = int(args.get("index", [None])[0])
        list = Item(item.subs[element_index]).elements
    else:
        list = item.subs
        xbmc.log( str(mode), xbmc.LOGINFO)

    index = 0
    for data in list:
        sub_item = Item(data)
        while (
            sub_item.is_folder() and len(sub_item.subs) == 1 and sub_item.path is None
        ):
            sub_item = Item(sub_item.subs[0])

        # Create kodi element
        if sub_item.is_folder():
            if sub_item.path is not None:
                li = xbmcgui.ListItem(label="🗁 " + sub_item.title)
                li.setArt({"thumb": sub_item.image, "icon": sub_item.icon})
                li.setIsFolder(True)
                new_args = {"title": "🗁 " + sub_item.title}
                new_args["url"] = sub_item.path if sub_item.model == Model["Brand"] else RADIOFRANCE_PAGE + "/" + sub_item.path
                new_args["mode"] = "brand" if sub_item.model == Model["Brand"] else "url"
                builded_url = build_url(new_args)
                highlight_list.append((builded_url, li, True))
            if 0 < len(sub_item.elements) :
                li = xbmcgui.ListItem(label="⭐ " + sub_item.title)
                li.setArt({"thumb": sub_item.image, "icon": sub_item.icon})
                li.setIsFolder(True)
                new_args = {"title": "⭐ " + sub_item.title}
                new_args["url"] = url
                new_args["index"] = index
                new_args["mode"] = "index"
                builded_url = build_url(new_args)
                highlight_list.append((builded_url, li, True))
        else:
            # Playable element
            li = xbmcgui.ListItem(label=sub_item.title)
            li.setArt({"thumb": sub_item.image, "icon": sub_item.icon})
            new_args = {"title": sub_item.title}
            li.setIsFolder(False)
            tag = li.getMusicInfoTag(offscreen=True)
            tag.setMediaType("audio")
            tag.setTitle(sub_item.title)
            # tag.setComment(sub_item.standFirst if "standFirst" in sub_item else None)
            tag.setURL(sub_item.path)
            tag.setGenres(["podcast"])
            tag.setArtist(sub_item.artists)
            tag.setDuration(sub_item.duration)
            tag.setReleaseDate(sub_item.release)
            li.setProperty("IsPlayable", "true")
            if sub_item.path is not None:
                new_args["url"] = sub_item.path
                new_args["mode"] = "stream"
            builded_url = build_url(new_args)
            song_list.append((builded_url, li, False))

        xbmc.log(
            str(new_args) + str(sub_item),
            xbmc.LOGINFO,
        )
        index += 1

    xbmcplugin.addDirectoryItems(addon_handle, highlight_list, len(highlight_list))
    xbmcplugin.addDirectoryItems(addon_handle, song_list, len(song_list))
    xbmcplugin.endOfDirectory(addon_handle)

def brand(args):
    name = args.get("url", [""])[0]
    url = RADIOFRANCE_PAGE + "/" + name.split("_")[0] + "/api/live/webradios/" + name

    xbmc.log("[Brand]: " + url, xbmc.LOGINFO)

    data = requests.get(url).text
    item = Brand(data)

    li = xbmcgui.ListItem(label=item.title)
    li.setArt({"thumb": item.image, "icon": item.icon})
    li.setIsFolder(False)
    tag = li.getMusicInfoTag(offscreen=True)
    tag.setMediaType("audio")
    tag.setTitle(item.title)
    tag.setURL(item.url)
    tag.setGenres(["radio"])
    # tag.setArtist(item.artists)
    # tag.setDuration(item.duration)
    # tag.setReleaseDate(sub_item.release)
    li.setProperty("IsPlayable", "true")
    
    xbmc.Player().play(item.url, li)
    play (item.url)

def play(url):
    play_item = xbmcgui.ListItem(path=url)
    xbmcplugin.setResolvedUrl(addon_handle, True, listitem=play_item)


def search(args):
    def GUIEditExportName(name):
        kb = xbmc.Keyboard("Odyssées", "Search title")
        kb.doModal()
        if not kb.isConfirmed():
            return None
        query = kb.getText()
        return query

    new_args = {k: v[0] for (k, v) in args.items()}
    new_args["mode"] = "page"
    value = GUIEditExportName("Odyssées")
    if value is None:
        return

    new_args["url"] = RADIOFRANCE_PAGE + "/recherche"
    new_args = {k: [v] for (k, v) in new_args.items()}
    build_url(new_args)
    get_and_build_lists(new_args, url_args="?term=" + value + "&")


def get_and_build_lists(args, url_args="?"):
    xbmc.log(
        "".join(["Get and build: " + str(args) + "(url args: " + url_args + ")"]),
        xbmc.LOGINFO,
    )
    url = args.get("url", [RADIOFRANCE_PAGE])[0]
    page = requests.get(url + "/__data.json" + url_args).text
    content = expand_json(page)

    build_lists(content, args, url)


def main():
    args = parse_qs(sys.argv[2][1:])
    mode = args.get("mode", None)

    xbmc.log(
        "".join(
            ["mode: ", str("" if mode is None else mode[0]), ", args: ", str(args)]
        ),
        xbmc.LOGINFO,
    )

    # initial launch of add-on
    url = RADIOFRANCE_PAGE
    url_args = "?"
    url_args += "recent=false&"
    if "page" in args and 1 < int(arg.get("page", "1")):
        url_args += "p=" + str(args.get("page", "1"))
    if mode is not None and mode[0] == "stream":
        play(args("url"))
    elif mode is not None and mode[0] == "search":
        search(args)
    elif mode is not None and mode[0] == "brand":
        brand(args)
    else:
        if mode is None:
            url = url + "/podcasts"
            args["url"] = []
            args["url"].append(url)
        # New page
        get_and_build_lists(args, url_args)

if __name__ == "__main__":
    addon_handle = int(sys.argv[1])
    main()
