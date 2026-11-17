"""
Tests unitaires de base sur utils.py.

Ces tests ne couvrent volontairement que la partie de utils.py qui ne
dépend pas des modules Kodi (xbmc, xbmcgui...), afin de pouvoir tourner
en dehors de tout environnement Kodi (CI, machine de développement).

Lancer avec :
    python -m pytest tests/
"""
import json

import pytest

import utils


def make_svelte_like_payload(parsed):
    """Construit un payload minimal imitant le format __data.json de Radio
    France (généré par SvelteKit) : une liste `nodes`, chacun pouvant
    porter une liste `data` où les entiers sont des indices de référence
    vers d'autres éléments de cette même liste.
    """
    return json.dumps({"nodes": [{"data": parsed}]})


def test_expand_json_resolves_references():
    # index: 0=racine, 1=content, 2=context, 3="OTHER", 4=titre,
    #        5=liste d'items, 6/7=items, 8="OTHER", 9/10=titres des items
    parsed = [
        {"content": 1, "context": 2},
        {"model": 3, "title": 4, "items": 5},
        {},
        "OTHER",
        "Ma page",
        [6, 7],
        {"model": 8, "title": 9},
        {"model": 8, "title": 10},
        "OTHER",
        "Item A",
        "Item B",
    ]

    expanded = utils.expand_json(make_svelte_like_payload(parsed))

    assert expanded["context"] == {}
    assert expanded["content"]["model"] == "OTHER"
    assert expanded["content"]["title"] == "Ma page"
    assert [i["title"] for i in expanded["content"]["items"]] == ["Item A", "Item B"]


def test_create_item_from_page_builds_item_with_subs():
    parsed = [
        {"content": 1, "context": 2},
        {"model": 3, "title": 4, "items": 5},
        {},
        "OTHER",
        "Ma page",
        [6, 7],
        {"model": 8, "title": 9},
        {"model": 8, "title": 10},
        "OTHER",
        "Item A",
        "Item B",
    ]
    data = utils.expand_json(make_svelte_like_payload(parsed))

    item = utils.create_item_from_page(data)

    assert item.title == "Ma page"
    assert item.model == utils.Model.OTHER
    assert len(item.subs) == 2
    assert {sub["title"] for sub in item.subs} == {"Item A", "Item B"}


def test_create_item_raises_item_creation_error_on_bad_data():
    # Un modèle dont les champs obligatoires manquent (StationPage lit
    # data['stationName']) déclenche un KeyError dans __init__.
    # (Un 'pagination' sans 'pageNumber' n'est plus une erreur : les pages
    # actuelles ne donnent que 'lastPage'.)
    bad_data = {"model": "StationPage"}

    with pytest.raises(utils.ItemCreationError) as exc_info:
        utils.create_item(0, bad_data)

    assert exc_info.value.data is bad_data
    assert isinstance(exc_info.value.original_exception, KeyError)


@pytest.mark.parametrize(
    "url,local,expected",
    [
        ("/podcasts/foo", "", "https://www.radiofrance.fr/podcasts/foo"),
        ("podcasts/foo", "", "https://www.radiofrance.fr/podcasts/foo"),
        ("https://example.com/stream.mp3", "", "https://example.com/stream.mp3"),
        ("/foo", "/franceinter", "https://www.radiofrance.fr/franceinter/foo"),
    ],
)
def test_podcast_url(url, local, expected):
    assert utils.podcast_url(url, local) == expected


def test_podcast_url_none_passthrough():
    assert utils.podcast_url(None) is None


# --- Régressions liées à la nouvelle page d'accueil de Radio France --------
#
# Depuis une évolution du site (schéma proche de GraphQL), radiofrance.fr
# renvoie parfois des `nodes` valant `null`, et des champs optionnels
# explicitement mis à `null` plutôt qu'omis (`"format": null`), ce qui
# faisait planter le code écrit en supposant que ces clés seraient soit
# absentes, soit toujours des chaînes non vides.

def test_expand_json_ignores_null_nodes():
    # Radio France insère désormais des nodes `null` en fin de tableau ;
    # ça ne doit pas faire planter expand_json (TypeError sur `'data' in None`).
    parsed = [
        {"content": 1},
        {"model": 2, "title": 3},
        "OTHER",
        "Page",
    ]
    payload = json.dumps({"nodes": [{"data": parsed}, None, None]})

    expanded = utils.expand_json(payload)

    assert expanded["content"]["title"] == "Page"


def test_create_item_does_not_misdetect_brand_object_as_brand_model():
    # Sur la nouvelle page d'accueil, le contenu top-level porte un champ
    # 'brand' qui est un objet de métadonnées (pas un slug de station comme
    # avant) : il ne doit pas déclencher le modèle Brand, qui tenterait un
    # appel réseau et plantait sur `brand.split("_")`.
    data = {
        "__typename": "PageTemplate",
        "title": "Aujourd'hui",
        "brand": {"name": "radiofrance", "title": "Radio France"},
        "highlights": [],
    }

    item = utils.create_item(0, data)

    # reconnu par son __typename, et surtout pas pris pour une station
    assert item.model == utils.Model.PAGETEMPLATE
    assert item.model != utils.Model.BRAND


def test_untyped_object_with_brand_object_is_not_a_brand():
    # même chose sans __typename : l'heuristique "brand" n'est valable que
    # si 'brand' est un slug (chaîne), pas un objet de métadonnées
    data = {"title": "Aujourd'hui", "brand": {"name": "radiofrance"}, "highlights": []}

    assert utils.create_item(0, data).model == utils.Model.OTHER


def test_other_falls_back_to_highlights_when_no_items():
    # Nouveau nom de champ utilisé par Radio France pour lister le contenu
    # d'une page de type "home" : 'highlights' au lieu de 'items'.
    data = {"highlights": [{"title": "Bloc 1"}, {"title": "Bloc 2"}]}

    item = utils.create_item(0, data)

    assert [s["title"] for s in item.subs] == ["Bloc 1", "Bloc 2"]


def test_other_handles_null_items_without_crashing():
    # 'items' présent mais explicitement `null` : ne doit pas propager
    # `None` comme `subs` (ce qui ferait planter tout code appelant `len()`
    # ou itérant dessus par la suite).
    data = {"items": None}

    item = utils.create_item(0, data)

    assert item.subs == []


def test_create_item_handles_explicit_null_model_and_format():
    # Radio France peut désormais renvoyer "model": null ou "format": null
    # au lieu d'omettre la clé, ce qui faisait planter `.upper()` sur None.
    data = {"model": None, "format": None, "title": "Bloc sans type"}

    item = utils.create_item(0, data)

    assert item.model == utils.Model.OTHER
    assert item.title == "Bloc sans type"


def test_parent_item_survives_broken_singleton_sub_item():
    # Un item n'ayant qu'un seul sous-élément (pas de 'path') tente de se
    # "déplier" via remove_singletons(). Si ce sous-élément unique est
    # corrompu, la construction de l'item parent ne doit pas échouer pour
    # autant : un seul élément en erreur ne doit jamais bloquer tout le
    # reste du listing.
    broken_sub = {"model": "other", "pagination": {}}  # déclenche un KeyError
    data = {"title": "Parent", "items": [broken_sub]}

    item = utils.create_item(0, data)

    assert item.title == "Parent"
    assert item.subs == [broken_sub]
