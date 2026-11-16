"""Playable list items, with a minimal fake xbmcgui (no Kodi needed)."""
import os
import sys
import types
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class FakeTag:
    def __init__(self):
        self.calls = {}

    def __getattr__(self, name):
        if name.startswith("set"):
            return lambda *args: self.calls.__setitem__(name, args)
        raise AttributeError(name)


class FakeListItem:
    def __init__(self, label="", path=None):
        self.tag, self.props = FakeTag(), {}

    def setIsFolder(self, value): pass
    def setArt(self, art): pass
    def setProperty(self, key, value): self.props[key] = value
    def getMusicInfoTag(self, offscreen=False): return self.tag


sys.modules.setdefault("xbmcgui", types.SimpleNamespace(ListItem=FakeListItem))
sys.argv = sys.argv[:1] + ["1", ""] if len(sys.argv) < 3 else sys.argv
sys.argv[0] = "plugin://plugin.audio.radiofrance/"

import utils
from interface import Playable


def build(data):
    item = utils.create_item(0, data)
    url, li, is_folder = Playable(item, {}).construct()
    return url, li


class PlayableTag(unittest.TestCase):
    def test_lazy_episode_never_exposes_its_lookup_url_to_kodi(self):
        # Kodi opens the tag's URL itself and skips the plugin: it opened .../transistor/aod/<id> as an audio file
        url, li = build({"__typename": "Expression", "id": "e1", "title": "Ep", "href": "/p/ep",
                         "manifestation": {"__typename": "ManifestationAudio", "duration": 5}})
        self.assertNotIn("setURL", li.tag.calls)
        self.assertIn("mode=episode", url)
        self.assertEqual(li.props["IsPlayable"], "true")

    def test_lazy_station_never_exposes_its_lookup_url_to_kodi(self):
        from unittest import mock
        with mock.patch.object(utils, "fetch_data", side_effect=OSError("down")):
            url, li = build({"__typename": "Brand", "id": "1", "brand": "franceinter"})
        self.assertNotIn("setURL", li.tag.calls)
        self.assertIn("mode=brand", url)

    def test_direct_media_url_is_still_set(self):
        url, li = build({"model": "Expression", "title": "old", "href": "/p/old",
                         "manifestations": [{"model": "ManifestationAudio", "url": "https://cdn/a.mp3", "principal": True}]})
        self.assertEqual(li.tag.calls["setURL"], ("https://cdn/a.mp3",))
        self.assertIn("mode=stream", url)


if __name__ == "__main__":
    unittest.main()
