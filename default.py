# https://docs.python.org/2.7/
import json
import sys
import urllib
from urllib.parse import parse_qs
# http://mirrors.kodi.tv/docs/python-docs/
# import xbmcaddon
# import xbmcgui
#import xbmcplugin
# http://docs.python-requests.org/en/latest/
import requests
# http://www.crummy.com/software/BeautifulSoup/bs4/doc/
from bs4 import BeautifulSoup


DEFAULT_MANIFESTATION=0

def build_url(query):
    base_url = sys.argv[0]
    return base_url + '?' + urllib.urlencode(query)

def parse_json(data):
    parsed = json.loads(data)["nodes"][2]["data"];

    def get_or_add (m, k):
        if not k in m:
            m[k] = parsed[k]
        return m[k]


    def expand_element(e):
        import builtins
        match type(e) :
                case builtins.dict :
                    return expand_dict(e)
                case builtins.tuple :
                    return expand_tuple(e)
                case builtins.list :
                    return expand_tuple(e)
                case builtins.int if e < len(parsed) and not isinstance(parsed[e], int):
                    return expand_element(parsed[e])
                case _:
                    return e

    def expand_tuple(element):
        return [expand_element(v) for v in element]

    def expand_dict(element):
        return {k: expand_element(v) for k,v in element.items()}

    models={}
    elements=[]

    for e in parsed:
        if isinstance(e, dict) and "model" in e and get_or_add(models, e["model"]) == "Expression" :
            elements += [expand_element(e)]
    return elements

def build_song_list(content):
    from time import strftime, localtime

    song_list = []
    # iterate over the contents of the dictionary songs to build the list
    for item in [e for e in content if e["model"] == "Expression"]:
        # create a list item using the song filename for the label
        li = xbmcgui.ListItem(label=item['title'], thumbnailImage=item['visual']['src'])
        li.setProperty('inputstream', item['manifestations'][DEFAULT_MANIFESTATION]['url'])
        li.setInfo('music', {'duration': item['manifestations'][DEFAULT_MANIFESTATION]['duration'],
                             'date': strftime('%d.%m.%y', localtime(item['publishedDate']))
                             })
        li.setProperty('IsPlayable', 'true')
        # build the plugin url for Kodi
        # Example: plugin://plugin.audio.example/?url=http%3A%2F%2Fwww.theaudiodb.com%2Ftestfiles%2F01-pablo_perez-your_ad_here.mp3&mode=stream&title=01-pablo_perez-your_ad_here.mp3
        url = build_url({'mode': 'stream', 'url': item['manifestations'][DEFAULT_MANIFESTATION]['url'], 'title': item['title']})
        # add the current list item to a list
        song_list.append((url, li, False)) # False if not a folder
    # add list to Kodi per Martijn
    # http://forum.kodi.tv/showthread.php?tid=209948&pid=2094170#pid2094170
    xbmcplugin.addDirectoryItems(addon_handle, song_list, len(song_list))
    # set the content of the directory
    xbmcplugin.endOfDirectory(addon_handle)

def play_song(url):
    # set the path of the song to a list item
    play_item = xbmcgui.ListItem(path=url)
    # the list item is ready to be played by Kodi
    xbmcplugin.setResolvedUrl(addon_handle, True, listitem=play_item)

def main():
    radiofrance_page = "https://www.radiofrance.fr/podcasts/__data.json"

    args = parse_qs(sys.argv[2][1:])
    mode = args.get('mode', None)

    # initial launch of add-on
    if mode is None:
        # get the HTML for http://www.theaudiodb.com/testfiles/
        page = requests.get(radiofrance_page).text
        # get the content needed from the page
        content = parse_json(page)
        print (content)

        # display the list of songs in Kodi
        build_song_list(content)
    # a song from the list has been selected
    elif mode[0] == 'stream':
        # pass the url of the song to play_song
        play_song(args['url'][0])

if __name__ == '__main__':
    addon_handle = int(sys.argv[1])
    main()

