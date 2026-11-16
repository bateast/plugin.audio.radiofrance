"""Offline tests of the RadioFrance data-model handling (no Kodi, no network).

    python -m unittest discover -s tests

Set RF_DATA_JSON=/path/to/__data.json to also run a smoke test on a real home page dump.
"""
import json
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import utils
from utils import Item, create_item, create_item_from_page, expand_json, find_audio_url


def expression(title="Episode", **extra):
    return {"__typename": "Expression", "id": title, "title": title,
            "href": f"/franceinter/podcasts/show/{title}", "duration": 120,
            "publishedDate": 1794813730,
            "manifestation": {"__typename": "ManifestationAudio", "duration": 120}, **extra}


class Devalue(unittest.TestCase):
    def test_shared_refs_sentinels_and_nulls(self):
        parsed = [{"title": 1, "missing": -1, "nothing": 2, "a": 3, "b": 3}, "Hello", None, {"x": 4}, 42]
        out = utils.devalue_parse(parsed)
        self.assertEqual(out["title"], "Hello")
        self.assertIsNone(out["missing"])   # old code read parsed[-1] here
        self.assertIsNone(out["nothing"])
        self.assertEqual(out["a"], {"x": 42})
        self.assertIs(out["a"], out["b"])   # decoded once

    def test_page_node_is_found_among_null_and_skipped_nodes(self):
        payload = {"type": "data", "nodes": [
            {"type": "data", "data": [{"station": 1}, {"name": 2}, "franceinter"]},
            None,   # crashed the old expand_json
            {"type": "data", "data": [{"content": 1}, {"__typename": 2, "id": 3, "title": 4, "highlights": 5},
                                      "PageTemplate", "p1", "Home", []]},
            {"type": "skip"}]}
        page = expand_json(json.dumps(payload))
        self.assertEqual(page["content"]["title"], "Home")
        self.assertEqual(page["context"], {"station": "franceinter"})

    def test_no_page_raises(self):
        with self.assertRaises(ValueError):
            expand_json({"nodes": [None]})


class NewModel(unittest.TestCase):
    def test_highlight_subtypes_and_children(self):
        for tn in ("Highlight_SLIDER_EPISODE", "Highlight_BLOC_MEDIA_1_6", "Highlight"):
            item = create_item(0, {"__typename": tn, "title": " T ", "items": [expression("a"), expression("b"), expression("c")]})
            self.assertIsInstance(item, Item, tn)
            self.assertEqual(item.model, utils.Model.HIGHLIGHT)
            self.assertEqual((item.title, len(item.subs)), ("T", 3))

    def test_page_template_uses_highlights(self):
        page = {"content": {"__typename": "PageTemplate", "title": "Home", "path": "home",
                            "highlights": [{"__typename": "Highlight_X", "title": "h", "items": [expression("a"), expression("b")]},
                                           {"__typename": "Highlight_X", "title": "h2", "items": [expression("c"), expression("d")]}]}}
        item = create_item_from_page(page)
        self.assertEqual([s["title"] for s in item.subs], ["h", "h2"])

    def test_children_keys_are_not_duplicated(self):
        main, others = expression("m"), [expression("o1"), expression("o2")]
        h = {"__typename": "Highlight_BLOC_MEDIA_1_3", "items": [main] + others,
             "mainItem": {"contents": main}, "secondaryItems": [{"contents": o} for o in others]}
        self.assertEqual(len(create_item(0, h).subs), 3)

    def test_images_from_id_or_src(self):
        self.assertEqual(utils.image_src({"id": "abc"}), "https://www.radiofrance.fr/pikapi/images/abc")
        self.assertEqual(utils.image_src({"id": "abc", "src": "https://x/y"}), "https://x/y")
        item = create_item(0, expression(square={"id": "sq"}, visual={}))
        self.assertTrue(item.icon.endswith("/sq"))

    def test_titleprops_and_missing_title(self):
        art = create_item(0, {"__typename": "Article", "id": "1", "titleProps": {"title": "Art", "href": "/info/x"}})
        self.assertEqual((art.title, art.path), ("Art", "https://www.radiofrance.fr/info/x"))
        self.assertEqual(create_item(0, {"__typename": "Theme", "id": "1", "title": None}).title, "")  # not "None"

    def test_promo_elements_are_not_items(self):
        newsletter = {"__typename": "HighlightElement", "kind": "newsletter_subscription", "title": "NL"}
        ebu = {"__typename": "HighlightElement", "kind": "ebu", "title": "AI", "titleProps": {"href": "https://x/explorer"}}
        h = create_item(0, {"__typename": "Highlight", "title": "t", "items": [newsletter, ebu, expression("a"), expression("b")]})
        self.assertEqual(len(h.subs), 2)

    def test_highlight_element_link_without_type(self):
        el = create_item(0, {"__typename": "HighlightElement", "links": [{"path": "/x"}], "mainImage": {"model": "EmbedImage", "id": "i"}})
        self.assertIsInstance(el, Item)  # old code: KeyError 'type' / 'src'
        self.assertEqual(el.path, "https://www.radiofrance.fr/x")

    def test_article_video_is_playable_from_main_resource(self):
        v = create_item(0, {"__typename": "ArticleVideo", "id": "v", "title": "Vid", "href": "", "duration": 9,
                            "mainResource": {"__typename": "EmbedVideo", "url": "https://www.radiofrance.fr/s3/a.mp4"}})
        self.assertFalse(v.is_folder())
        self.assertEqual((v.path, v.duration, v.lazy), ("https://www.radiofrance.fr/s3/a.mp4", 9, False))

    def test_unknown_typename_does_not_fail(self):
        self.assertIsInstance(create_item(0, {"__typename": "SomethingNew", "id": "1", "items": [expression("a")]}), Item)

    def test_tag_and_theme_new_shape(self):
        for tn in ("Tag", "Theme"):
            self.assertEqual(create_item(0, {"__typename": tn, "id": "1", "title": "t", "href": "/sujets/t"}).path,
                             "https://www.radiofrance.fr/sujets/t")  # old Tag: KeyError 'path'


class Structure(unittest.TestCase):
    def test_leaf_is_never_swallowed(self):
        # old remove_singletons dropped the only child of a linked container
        linked = create_item(0, {"__typename": "Highlight", "link": {"href": "/promo"}, "items": [expression("only")]})
        self.assertEqual(len(linked.subs), 1)
        unlinked = create_item(0, {"__typename": "Highlight", "items": [expression("only")]})
        self.assertEqual(len(unlinked.subs), 1)

    def test_wrapper_chains_collapse(self):
        inner = {"__typename": "Highlight", "title": "in", "items": [expression("a"), expression("b")]}
        outer = create_item(0, {"__typename": "Highlight", "title": "out", "items": [inner]})
        self.assertEqual([s["title"] for s in outer.subs], ["a", "b"])

    def test_slider_and_is_image(self):
        self.assertIsInstance(create_item(0, {"format": "SLIDER_CHAINE", "items": [expression("a"), expression("b")]}), utils.Slider)
        self.assertFalse(create_item(0, expression()).is_image())


class Playback(unittest.TestCase):
    def test_new_expression_is_lazy(self):
        e = create_item(0, expression("ep"))
        self.assertTrue(e.lazy)
        self.assertEqual((e.duration, e.release is not None), (120, True))
        self.assertEqual(e.path, "https://www.radiofrance.fr/transistor/aod/ep")  # keyed by the expression id

    def test_old_expression_keeps_direct_url(self):
        e = create_item(0, {"model": "Expression", "title": "old", "href": "/p/old", "guest": [{"name": "Ann"}],
                            "manifestations": [{"model": "ManifestationAudio", "url": "https://cdn/a.mp3", "duration": 7, "principal": True}]})
        self.assertEqual((e.path, e.lazy, e.duration, e.artists), ("https://cdn/a.mp3", False, 7, "Ann"))

    def test_show_name_as_artist(self):
        self.assertEqual(create_item(0, expression(concept={"id": "c", "title": "Show"})).artists, "Show")
        self.assertEqual(create_item(0, expression(text="Show2", textHref="/s")).artists, "Show2")
        self.assertEqual(create_item(0, expression(text="a description")).artists, "")

    def test_expression_without_page_is_not_playable(self):
        e = create_item(0, expression(href=""))
        self.assertIsNone(e.path)

    def test_find_audio_url_prefers_content_principal(self):
        page = {"content": {"__typename": "Expression", "manifestations": [
                    {"__typename": "ManifestationAudio", "url": "https://cdn/second.mp3", "principal": False},
                    {"__typename": "ManifestationAudio", "url": "https://cdn/main.mp3", "principal": True}]},
                "related": [{"manifestations": [{"__typename": "ManifestationAudio", "url": "https://cdn/other.mp3"}]}]}
        self.assertEqual(find_audio_url(page), "https://cdn/main.mp3")

    def test_find_audio_url_fallbacks(self):
        self.assertEqual(find_audio_url({"content": {"player": {"url": "https://cdn/x.mp3?t=1"}}}), "https://cdn/x.mp3?t=1")
        self.assertIsNone(find_audio_url({"content": {"manifestation": {"__typename": "ManifestationAudio", "duration": 3}}}))


class Brand(unittest.TestCase):
    STREAM = "https://stream.radiofrance.fr/franceinter/franceinter.m3u8?id=radiofrance"
    TRANSISTOR = {"metadata": {"firstLine": "France Inter"}, "sources": [{"url": STREAM, "isTimeshiftable": True}],
                  "liveApiRule": "live/1/transistor_inter_player"}
    LIVEMETA = {"now": {"firstLine": "La Terre au carr\u00e9", "secondLine": "Un \u00e9pisode", "cover": "abc"}}
    DATA = {"__typename": "Brand", "id": "1", "brand": "franceinter"}

    def setUp(self):
        utils._live_cache.clear()

    def feed(self, mapping):
        def fetch(url, headers=None):
            if url not in mapping:
                raise OSError("404 " + url)
            return mapping[url]
        return mock.patch.object(utils, "fetch_data", side_effect=fetch)

    def test_urls_come_from_the_brand_id(self):
        self.assertEqual(utils.live_url("1"), "https://www.radiofrance.fr/transistor/live/1")
        self.assertEqual(utils.live_url(1101), "https://www.radiofrance.fr/transistor/live/1101")

    def test_stream_and_now_playing(self):
        with self.feed({"https://www.radiofrance.fr/transistor/live/1": self.TRANSISTOR,
                        "https://api.radiofrance.fr/livemeta/live/1/transistor_inter_player": self.LIVEMETA}):
            b = create_item(0, self.DATA)
        self.assertEqual((b.path, b.lazy, b.title, b.artists), (self.STREAM, False, "La Terre au carr\u00e9 (France Inter)", "Un \u00e9pisode"))
        self.assertTrue(b.image.endswith("/pikapi/images/abc"))

    def test_now_playing_failure_still_gives_a_playable_station(self):
        with self.feed({"https://www.radiofrance.fr/transistor/live/1": self.TRANSISTOR}):
            b = create_item(0, self.DATA)
        self.assertEqual((b.path, b.lazy, b.title), (self.STREAM, False, "France Inter"))

    def test_unreachable_lookup_is_resolved_when_played(self):
        data = dict(self.DATA, titleProps={"title": "France Inter"})
        with self.feed({}):
            b = create_item(0, data)
        self.assertEqual((b.title, b.lazy, b.path), ("France Inter", True, utils.live_url("1")))

    def test_without_id_nothing_to_play(self):
        with self.feed({}):
            self.assertIsNone(create_item(0, {"__typename": "Brand", "brand": "x"}).path)

    def test_live_requests_carry_the_site_headers(self):
        with mock.patch.object(utils.requests, "get") as get:
            get.return_value.json.return_value = {}
            utils.fetch_live("https://www.radiofrance.fr/transistor/live/1")
        self.assertEqual(get.call_args.kwargs["headers"], utils.SITE_HEADERS)


class ConceptAndEpisodePages(unittest.TestCase):
    """Shapes taken from real podcast (concept) and episode pages."""

    def concept_page(self):
        item = {"__typename": "Expression", "id": "e", "titleProps": {"title": "Ep", "href": "/franceinter/podcasts/s/ep"},
                "concept": {"id": "c", "title": "Show"}, "duration": 90, "publishedDate": "Lundi 16 novembre 2026",
                "startDate": 1794813730, "manifestation": {"__typename": "ManifestationAudio", "duration": 90}}
        return {"content": {"__typename": "Concept", "id": "c", "title": "Show", "path": "franceinter/podcasts/s",
                            "expressions": {"next": "MjA=", "prev": None, "items": [dict(item, id=str(i)) for i in range(20)]},
                            "pagination": {"lastPage": 200}}, "context": {"station": "franceinter"}}

    def test_cursor_only_expressions_keep_last_page(self):
        top = create_item_from_page(self.concept_page())
        self.assertEqual((len(top.subs), top.pages), (20, (1, 200)))  # was (1, 1): no "next page" entry

    def test_episode_in_concept_list(self):
        top = create_item_from_page(self.concept_page())
        e = create_item(0, top.subs[0], {})
        self.assertEqual((e.title, e.path, e.lazy, e.artists, e.duration),
                         ("Ep", "https://www.radiofrance.fr/transistor/aod/0", True, "Show", 90))
        self.assertEqual(e.release, utils.format_release(1794813730))  # publishedDate is a display string here

    def test_old_model_page_numbers_still_read(self):
        c = create_item(0, {"model": "Concept", "title": "c", "path": "c",
                            "expressions": {"pageNumber": 2, "lastPage": 5, "items": [expression("a"), expression("b")]}})
        self.assertEqual(c.pages, (2, 5))

    def test_episode_page_singular_manifestation(self):
        page = {"content": {"__typename": "Expression", "id": "e",
                            "manifestation": {"__typename": "ManifestationAudio", "id": "m", "url": "https://media/x/main.m4a", "duration": 5},
                            # a related episode's audio embedded in the body must not win
                            "bodyJson": [{"data": {"manifestationUrl": "https://media/x/other.m4a"}}]}}
        self.assertEqual(find_audio_url(page), "https://media/x/main.m4a")
        self.assertFalse(create_item_from_page(page).lazy)


class PlayerEndpoint(unittest.TestCase):
    AOD = {"metadata": {"firstLine": "Journal"}, "sources": [
        {"url": "https://media/x.mp3", "preset": {"name": "stereo", "encoding": "MP3", "bitrate": 128}},
        {"url": "https://media/x.m4a", "preset": {"name": "stereo", "encoding": "AAC", "bitrate": 192}}]}

    def test_best_bitrate_wins(self):
        self.assertEqual(utils.aod_stream_url(self.AOD), "https://media/x.m4a")
        self.assertEqual(utils.aod_stream_url({"sources": [{"url": "https://media/only.mp3"}]}), "https://media/only.mp3")

    def test_no_source_is_an_error(self):
        for answer in ({}, {"sources": []}, {"sources": [{"preset": {}}]}):
            with self.assertRaises(ValueError):
                utils.aod_stream_url(answer)

    def test_episode_without_page_is_not_resolved_through_the_player(self):
        # no href: not published, nothing to play (the live "journal" of the day looks like this)
        self.assertIsNone(create_item(0, expression("x", href="")).path)

    def test_episode_without_id_falls_back_to_its_page(self):
        data = expression("x")
        del data["id"]
        e = create_item(0, data)
        self.assertEqual((e.lazy, e.path), (True, "https://www.radiofrance.fr/franceinter/podcasts/show/x"))


class ThemePage(unittest.TestCase):
    def test_documents_are_the_listing_and_carry_the_paging(self):
        page = {"content": {"__typename": "Theme", "id": "t", "title": "Pouvoir d'achat", "path": "economie/x",
                            "highlights": [], "pagination": {"lastPage": 28},
                            "documents": {"items": [expression(str(i)) for i in range(20)], "next": "MjA=", "prev": None, "total": 543},
                            "children": {"items": []}, "relatedConcepts": [{"__typename": "Concept", "id": "c", "title": "c"}]}}
        top = create_item_from_page(page)
        self.assertEqual((len(top.subs), top.pages), (20, (1, 28)))

    def test_documents_win_over_editorial_highlights(self):
        theme = create_item(0, {"__typename": "Theme", "id": "t", "highlights": [{"__typename": "Highlight", "items": [expression("h1"), expression("h2")]}],
                                "documents": {"items": [expression("d1"), expression("d2"), expression("d3")]}})
        self.assertEqual([s["title"] for s in theme.subs], ["d1", "d2", "d3"])


class LiveCache(unittest.TestCase):
    def test_failures_are_cached_briefly(self):
        utils._live_cache.clear()
        with mock.patch.object(utils, "fetch_data", side_effect=OSError("404")) as fd:
            for _ in range(3):
                with self.assertRaises(OSError):
                    utils.fetch_live("https://x/live")
        self.assertEqual(fd.call_count, 1)


@unittest.skipUnless(os.environ.get("RF_DATA_JSON"), "set RF_DATA_JSON to a downloaded https://www.radiofrance.fr/__data.json")
class RealHomePage(unittest.TestCase):
    def test_every_block_and_child_builds(self):
        with open(os.environ["RF_DATA_JSON"]) as f:
            page = expand_json(f.read())
        ctx = page["context"]
        with mock.patch.object(utils, "fetch_live", side_effect=OSError("offline")):
            top = create_item_from_page(page)
            self.assertGreater(len(top.subs), 0)
            playable = 0
            for i, raw in enumerate(top.subs):
                block = create_item(i, raw, ctx)
                self.assertIsInstance(block, Item, block if not isinstance(block, Item) else "")
                for j, raw_sub in enumerate(block.subs):
                    sub = create_item(j, raw_sub, ctx)
                    self.assertIsInstance(sub, Item, sub if not isinstance(sub, Item) else "")
                    playable += (not sub.is_folder() and sub.path is not None)
            self.assertGreater(playable, 0)


@unittest.skipUnless(os.environ.get("RF_CONCEPT_JSON") and os.environ.get("RF_EPISODE_JSON"),
                     "set RF_CONCEPT_JSON and RF_EPISODE_JSON to downloaded <podcast>/__data.json and <episode>/__data.json")
class RealPodcastAndEpisode(unittest.TestCase):
    def test_podcast_lists_episodes_and_episode_resolves(self):
        with open(os.environ["RF_CONCEPT_JSON"]) as f:
            top = create_item_from_page(expand_json(f.read()))
        self.assertGreater(len(top.subs), 0)
        self.assertGreater(top.pages[1], 1)
        first = create_item(0, top.subs[0], {})
        self.assertTrue(first.lazy and first.path)
        with open(os.environ["RF_EPISODE_JSON"]) as f:
            url = find_audio_url(expand_json(f.read()))
        self.assertTrue(url and url.startswith("https://"), url)


if __name__ == "__main__":
    unittest.main()
