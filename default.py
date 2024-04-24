# https://docs.python.org/2.7/
import json
import sys
import requests
from urllib.parse import parse_qs
# http://mirrors.kodi.tv/docs/python-docs/
# http://www.crummy.com/software/BeautifulSoup/bs4/doc/
from urllib.parse import urlencode, quote_plus
from ast import literal_eval
import xbmc
import xbmcgui
import xbmcplugin


DEFAULT_MANIFESTATION = 0
RADIOFRANCE_PAGE = "https://www.radiofrance.fr"


def build_url(query):
    base_url = sys.argv[0]
    url = base_url + '?' + urlencode(query, quote_via=quote_plus)
    return url


def parse_json(data):
    parsed = json.loads(data)["nodes"][-1]["data"]

    def get_or_add(m, k):
        if k not in m:
            m[k] = parsed[k]
        return m[k]

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


def build_lists(data, args):
    xbmc.log(str(args), xbmc.LOGINFO)

    highlight_list = []
    song_list = []

    def add_search():
        new_args = {k: v[0] for (k, v) in args.items()}
        new_args['mode'] = "search"
        li = xbmcgui.ListItem(label="? Search term")
        li.setIsFolder(True)
        url = build_url(new_args)
        highlight_list.append((url, li, True))

    def add_pages(pages):
        new_args = {k: v[0] for (k, v) in args.items()}
        if 1 < pages['pageNumber']:
            new_args['page'] = pages['pageNumber'] - 1
            li = xbmcgui.ListItem(label="<< Previous page")
            li.setIsFolder(True)
            url = build_url(new_args)
            highlight_list.append((url, li, True))
        if pages['pageNumber'] < pages['lastPage']:
            new_args['page'] = pages['pageNumber'] + 1
            li = xbmcgui.ListItem(label=">> Next page")
            li.setIsFolder(True)
            url = build_url(new_args)
            highlight_list.append((url, li, True))

    def setArt(li, item):
        if 'visual' in item and\
           item['visual'] is not None and\
           'src' in item['visual']:
            thumb = item['visual']['src']
        elif 'mainImage' in item and\
           item['mainImage'] is not None and\
           'src' in item['mainImage']:
            thumb = item['mainImage']['src']
        else:
            thumb = None
        if 'squaredVisual' in item and\
           item['squaredVisual'] is not None and\
           'src' in item['squaredVisual']:
            icon = item['squaredVisual']['src']
        else:
            icon = None
        li.setArt({'thumb': thumb,
                   'icon': icon})

    def getPath(li, item, args, index=0):
        if 'path' in item and item['path'] is not None:
            return build_url({'mode': 'page', 'title': item['title'],
                             'url': RADIOFRANCE_PAGE + "/" + item['path']})
        elif 'links' in item and item['links'] is not None \
             and 0 < len([l for l in item['links'] if l['type'] == "path"]):
            # Warning, Links elements seems relative to current brand url
            link = [l for l in item['links'] if l['type'] == "path"][0]
            brand = item['brand'] if 'brand' in item and not "" else ""
            return build_url({'mode': 'page', 'title': item['title'],
                             'url': RADIOFRANCE_PAGE + "/" + brand + "/" + link['path']})

        else:
            # Add element for further development
            return build_url({'mode': 'highlight',
                              'title': item['title'],
                              'url': args['url'][0] if 'url' in args
                              else RADIOFRANCE_PAGE + "/podcasts",
                              'index': index})

    def add_item(item, index=0):
        xbmc.log(str(item['title']) + " - " + str(item['model']), xbmc.LOGINFO)

        def match_folder():
            li = xbmcgui.ListItem(label=item['title'])
            li.setIsFolder(True)
            setArt(li, item)
            url = getPath(li, item, args, index)
            highlight_list.append((url, li, True))

        def match_song():
            from time import strftime, localtime
            li = xbmcgui.ListItem(label=item['title'])
            tag = li.getMusicInfoTag(offscreen=True)
            tag.setMediaType("audio")
            tag.setTitle(item['title'])
            tag.setComment(item['standFirst'] if 'standFirst' in item else None)
            tag.setURL(item['manifestations'][DEFAULT_MANIFESTATION]['url'])
            tag.setGenres(["podcast"])
            if 'guest' in item:
                tag.setArtist(", ".join([g['name'] for g in item['guest']]))
            tag.setDuration(
                item['manifestations'][DEFAULT_MANIFESTATION]['duration'])
            tag.setReleaseDate(
                strftime('%d-%m.%y', localtime(item['publishedDate'])) if 'publishedDate' in item else None)
            setArt(li, item)
            li.setProperty('IsPlayable', 'true')
            out_url = item['manifestations'][DEFAULT_MANIFESTATION]['url']
            url = build_url({'mode': 'stream',
                             'url': out_url,
                             'title': item['title']})
            song_list.append((url, li, False))

        if item['model'] in ["Highlight", "Concept", "Tag",
                             "Theme", "PageTemplate", 'HighlightElement']:
            # If element is a singleton, derictly develop it
            if 'elements' in item and len(item['elements']) == 1 \
               and 'contents' in item['elements'][0] and len(item['elements'][0]['contents']) == 1:
                add_item(item['elements'][0]['contents'][0], index)
            elif 'elements' in item and len(item['elements']) == 1 \
                 and 'contents' in item['elements'][0] and len(item['elements'][0]['contents']) == 0:
                add_item(item['elements'][0], index)
            else:
                match_folder()
        elif item['model'] in ["Expression"] and 0 < len(item['manifestations']):
            match_song()

    mode = args.get('mode', None)
    if mode is None:
        add_search()

    index = literal_eval(args['index'][0]) if 'index' in args else []
    if 'podcastsData' in data:
        data = data['podcastsData']
        if 'pagination' in data:
            data = data['pagination']
        if 'pageNumber' in data and 'lastPage' in data\
           and 1 < data['lastPage']:
            add_pages(data)
        if 'items' in data:
            items = data['items']
            for item in items:
                add_item(item, index)

    elif 'content' in data and 'layout' in data['content']:
        items = data['content']['layout']
        for (i, j) in index:
            items = items['elements'][i]['contents'][j]
        i = 0
        for element in items['elements']:
            j = 0
            for content in element['contents']:
                add_item(content, index=index + [(i, j)])
                j += 1
            i += 1
    elif 'content' in data and 'expressions' in data['content']:
        data = data['content']['expressions']
        if 'pageNumber' in data and 'lastPage' in data\
           and 1 < data['lastPage']:
            add_pages(data)
        if 'items' in data:
            items = data['items']
            for item in items:
                add_item(item, index)
    elif 'pagination' in data:
        pagination = data['pagination']
        if 'pageNumber' in pagination and 'lastPage' in pagination\
           and 1 < pagination['lastPage']:
            add_pages(pagination)
        if 'items' in data:
            items = data['items']
            for (k, v) in items.items():
                if k in ["concepts", "expressions_articles"]:
                    for item in v['contents']:
                        add_item(item, index)
    else:
        None

    xbmcplugin.addDirectoryItems(
        addon_handle, highlight_list, len(highlight_list))
    xbmcplugin.addDirectoryItems(addon_handle, song_list, len(song_list))
    xbmcplugin.endOfDirectory(addon_handle)


def play(url):
    play_item = xbmcgui.ListItem(path=url)
    xbmcplugin.setResolvedUrl(addon_handle, True, listitem=play_item)


def search(args):
    def GUIEditExportName(name):
        kb = xbmc.Keyboard('Odyssées', 'Search title')
        kb.doModal()
        if not kb.isConfirmed():
            return None
        query = kb.getText()
        return query

    new_args = {k: v[0] for (k, v) in args.items()}
    new_args['mode'] = "page"
    value = GUIEditExportName("Odyssées")
    if value is None:
        return

    new_args['url'] = RADIOFRANCE_PAGE + "/recherche"
    new_args = {k: [v] for (k, v) in new_args.items()}
    build_url(new_args)
    get_and_build_lists(new_args, url_args="?term=" + value + "&")


def get_and_build_lists(args, url_args="?"):
    xbmc.log("".join(["Get and build: " + str(args) + "(url args: " + url_args + ")"]), xbmc.LOGINFO)
    url = args['url'][0]
    url_args += "recent=false&"
    page = requests.get(url + "/__data.json" + url_args).text
    content = parse_json(page)

    build_lists(content, args)


def main():
    args = parse_qs(sys.argv[2][1:])
    mode = args.get('mode', None)

    xbmc.log("".join(["mode: ", str("" if mode is None else mode[0]), ", args: ", str(args)]), xbmc.LOGINFO)

    # initial launch of add-on
    url = RADIOFRANCE_PAGE
    url_args = "?"
    url_args += "recent=false&"
    if 'page' in args and 1 < int(args['page'][0]):
        url_args += "p=" + str(args['page'][0])
    if mode is None:
        url = url + "/podcasts"
        page = requests.get(url + "/__data.json" + url_args).text
        content = parse_json(page)
        build_lists(content, args)
    elif mode[0] == 'stream':
        play(args['url'][0])
    elif mode[0] == 'search':
        search(args)
    else:
        get_and_build_lists(args, url_args)

if __name__ == '__main__':
    addon_handle = int(sys.argv[1])
    main()
