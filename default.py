# https://docs.python.org/2.7/
import json
import sys
import urllib
import requests
from urllib.parse import parse_qs
# http://mirrors.kodi.tv/docs/python-docs/
# http://www.crummy.com/software/BeautifulSoup/bs4/doc/
from urllib.parse import urlencode, quote_plus
import xbmcaddon
import xbmcgui
import xbmcplugin


DEFAULT_MANIFESTATION=0
RADIOFRANCE_PAGE = "https://www.radiofrance.fr"

def build_url(query):
    base_url = sys.argv[0]
    return base_url + '?' + urlencode(query, quote_via=quote_plus)

def parse_json(data):
    parsed = json.loads(data)["nodes"][-1]["data"];

    def get_or_add (m, k):
        if not k in m:
            m[k] = parsed[k]
        return m[k]


    def expand_element(e):
        if isinstance(e,dict) :
            return expand_dict(e)
        elif isinstance(e,tuple) :
            return expand_tuple(e)
        elif isinstance(e,list) :
            return expand_tuple(e)
        a = parsed[e]
        if isinstance(a,dict) :
            return expand_dict(a)
        elif isinstance(a,tuple) :
            return expand_tuple(a)
        elif isinstance(a,list) :
            return expand_tuple(a)
        return a

    def expand_tuple(element):
        return [expand_element(v) for v in element]

    def expand_dict(element):
        return {k: expand_element(v) for k,v in element.items()}

    models={}
    elements=[]
    pagination=expand_element(parsed[1]['pagination'])
    # xbmc.log(str(pagination), xbmc.LOGINFO)
    pages = {'pageNumber': 1, 'lastPage': 1}
    if pagination is not None :
        if 'pageNumber' in pagination :
            pages['pageNumber'] = pagination['pageNumber']
        if 'lastPage' in pagination :
            pages['lastPage'] = pagination['lastPage']
        if 'items' in pagination :
            xbmc.log("Using pagination items", xbmc.LOGINFO)
            return {'pages' : pages, 'items' : pagination['items']}
    for e in parsed:
        if isinstance(e, dict) and "model" in e and get_or_add(models, e["model"]) in \
           ["Expression", "Highlight", "Tag", "Theme"] :
            elements += [expand_element(e)]
    return {'pages' : pages, 'items' : elements}

def build_lists(content, initial_url, highlight = None):
    from time import strftime, localtime

    highlight_list = []
    h_list = []
    raw_list = []
    if highlight == None:
        raw_list = [e for e in content['items'] if e["model"] == "Highlight"]
    else :
        h_list = [h for h in content['items'] if (h["model"] == "Highlight" and h['title'] == highlight) ]
        raw_list = [e['contents'][0] for e in h_list[0]['elements']] if len(h_list) > 0 else []
    # xbmc.log("".join(["h_list: ", str(h_list)]), xbmc.LOGINFO)
    # xbmc.log("".join(["rawlist: ", str(raw_list)]), xbmc.LOGINFO)
    for item in raw_list :
        li = xbmcgui.ListItem(label=item['title'])
        li.setIsFolder(True)
        li.setArt({'thumb': item['visual']['src'] if 'visual' in item and item['visual'] is not None and 'src' in item['visual']  else None,
                   'icon': item['squaredVisual']['src'] if 'squaredVisual' in item and item['squaredVisual'] is not None and 'src' in item['squaredVisual'] else None})
        if 'path' in item and item['path'] is not None:
            url = build_url({'mode': 'page', 'title': item['title'], 'url': RADIOFRANCE_PAGE + "/" + item['path']})
        else :
            url = build_url({'mode': 'highlight', 'title': item['title'], 'url': initial_url})
        highlight_list.append((url, li, True))
    # xbmc.log(str(highlight_list), xbmc.LOGINFO)
    xbmcplugin.addDirectoryItems(addon_handle, highlight_list, len(highlight_list))

    pages = content['pages']
    if pages['lastPage'] != 1 :
        args = content['args']
        if 1 < pages['pageNumber'] :
            li = xbmcgui.ListItem(label="<< Previous page")
            li.setIsFolder(True)
            url = build_url({'mode': args['mode'][0], 'title': args['title'][0], 'url': args['url'][0], 'page': pages['pageNumber'] - 1})
            highlight_list.append((url, li, True))
        if pages['pageNumber'] < pages['lastPage'] :
            li = xbmcgui.ListItem(label=">> Next page")
            li.setIsFolder(True)
            url = build_url({'mode': args['mode'][0], 'title': args['title'][0], 'url': args['url'][0], 'page': pages['pageNumber'] + 1})
            highlight_list.append((url, li, True))

    # xbmc.log(str(highlight_list), xbmc.LOGINFO)
    xbmcplugin.addDirectoryItems(addon_handle, highlight_list, len(highlight_list))


    song_list = []
    for item in [e for e in content['items'] if e["model"] == "Expression" and 0 < len(e['manifestations'])]:
        li = xbmcgui.ListItem(label=item['title'])

        tag = li.getMusicInfoTag(offscreen=True)
        tag.setMediaType("audio")
        tag.setTitle(item['title'])
        tag.setComment(item['standFirst'])
        tag.setURL(item['manifestations'][DEFAULT_MANIFESTATION]['url'])
        tag.setGenres(["podcast"])
        if 'guest' in item :
            tag.setArtist(", ".join([g['name'] for g in item['guest']]))
        tag.setDuration(item['manifestations'][DEFAULT_MANIFESTATION]['duration'])
        tag.setReleaseDate(strftime('%d-%m.%y', localtime(item['publishedDate'])))

        li.setArt({'thumb': item['visual']['src'] if item['visual'] is not None else None,
                   'icon': item['squaredVisual']['src'] if item['squaredVisual'] is not None else None})

        li.setProperty('IsPlayable', 'true')

        url = build_url({'mode': 'stream', 'url': item['manifestations'][DEFAULT_MANIFESTATION]['url'], 'title': item['title']})
        # add the current list item to a list
        song_list.append((url, li, False)) # False if not a folder

    xbmcplugin.addDirectoryItems(addon_handle, song_list, len(song_list))
    xbmcplugin.endOfDirectory(addon_handle)

def play_song(url):
    # set the path of the song to a list item
    play_item = xbmcgui.ListItem(path=url)
    # the list item is ready to be played by Kodi
    xbmcplugin.setResolvedUrl(addon_handle, True, listitem=play_item)

def main():
    args = parse_qs(sys.argv[2][1:])
    mode = args.get('mode', None)

    xbmc.log("".join(["mode: ", str("" if mode is None else mode[0]), ", args: ", str(args)]), xbmc.LOGINFO)

    # initial launch of add-on
    url = RADIOFRANCE_PAGE
    url_args = "?"
    if 'page' in args and 1 < int(args['page'][0]):
        url_args += "p=" + str(args['page'][0])
    if mode is None:
        url = url + "/podcasts"
        page = requests.get(url + "/__data.json" + url_args).text
        content = parse_json(page)
        content['args'] = args

        build_lists(content, url)
    elif mode[0] == "page" :
        url = args['url'][0]
        page = requests.get(url + "/__data.json" + url_args).text
        content = parse_json(page)
        content['args'] = args
        build_lists(content, url)
    elif mode[0] == 'highlight':
        url = args['url'][0]
        page = requests.get(url + "/__data.json" + url_args).text
        content = parse_json(page)
        content['args'] = args
        build_lists(content, url, highlight = args['title'][0])
    elif mode[0] == 'stream':
        play_song(args['url'][0])

if __name__ == '__main__':
    addon_handle = int(sys.argv[1])
    main()
