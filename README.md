# Plugin for RadioFrance podcast

RadioFrance moved away from `rss` based podcast toward a proprietary application and web-based environment. Justification is protection of authors rights.

This add-on try to provide back accesses to those podcast on Kodi.

# Copyrights & Licence

- Copyrights (c): Baptiste Fouques 2024
- Licence: GPLv3 (see Licence.txt)
- Based for starter on https://github.com/zag2me/plugin.audio.example


    > This program is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version.
    >
    > This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.
    >
    > You should have received a copy of the GNU General Public License along with this program. If not, see <https://www.gnu.org/licenses/>.

# Source #

The first object is parsing the `__data.json` elements and expanding it in python usable dictionary.

Definition is done by expansion, hopefully python could leverage lazy expansion not to create huge in memory structures.

At the end of the expansion, an Item page ("Expression") is as follow
``` python
{'id': 'ee008874-7590-4eb0-a621-d11e3871cf7b',
 'title': "Le journal intime d'Édith Piaf 1/7 : Je suis née comme un moineau",
 'standFirst': 'La petite Edith aime bien imaginer qu’elle est tombée du nid,
 comme un petit oiseau… D’ailleurs son nid,
 elle ne sait pas trop où il est perché. Mais quand Édith rencontre Momone,
 c’est décidé,
 elle veut chanter\xa0! À elles les rues de Belleville\xa0!',
 'brandEnums': ['FRANCEMUSIQUE'],
 'isExpired': False,
 'model': 'Expression',
 'type': 'episode',
 'kind': 'web',
 'guest': [{'name': 'Josiane Balasko',
            'role': 'Comédienne,
 réalisatrice,
 metteur en scène et romancière',
            'path': 'personnes/josiane-balasko',
            'migrated': True}],
 'publishedDate': 1711408020,
 'startDate': 1712700420,
 'endDate': 1712700421,
 'path': 'francemusique/podcasts/le-journal-intime-de/le-journal-intime-d-edith-piaf-episode-1-je-suis-nee-comme-un-moineau-9579821',
 'migrated': True,
 'visual': {'model': 'EmbedImage',
            'src': 'https://www.radiofrance.fr/s3/cruiser-production-eu3/2024/04/dcfe0c1b-c884-43a7-bfe9-082d622dbf2f/300x300_sc_16-9-lejournalintimededithpiaf-1.jpg',
            'webpSrc': 'https://www.radiofrance.fr/s3/cruiser-production-eu3/2024/04/dcfe0c1b-c884-43a7-bfe9-082d622dbf2f/300x300_sc_16-9-lejournalintimededithpiaf-1.webp',
            'legend': 'Visuel du podcast "Le journal intime d\'Edith Piaf",
 épisode n°1',
            'copyright': 'Aucun(e)',
            'author': '©Radio France - Atelier graphique RF',
            'width': 300,
            'height': 300,
            'preview': '/9j/2wBDACgcHiMeGSgjISMtKygwPGRBPDc3PHtYXUlkkYCZlo+AjIqgtObDoKrarYqMyP/L2u71////m8H////6/+b9//j/2wBDASstLTw1PHZBQXb4pYyl+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj/wAARCAAqACoDASIAAhEBAxEB/8QAGAAAAwEBAAAAAAAAAAAAAAAAAAEDBAL/xAAaEAEBAQEBAQEAAAAAAAAAAAAAAQIDESEx/8QAGAEBAAMBAAAAAAAAAAAAAAAAAAECAwT/xAAWEQEBAQAAAAAAAAAAAAAAAAAAARH/2gAMAwEAAhEDEQA/AKg7Cq7otAIxXTAAvHWonpbbPuoY2j05Ubp1nQiVeH45wp4NJR1rJ001dmLqhindfXeNIX9U5g286uz8mkTr/9k=',
            'id': 'dcfe0c1b-c884-43a7-bfe9-082d622dbf2f',
            'type': 'image',
            'preset': '300x300'},
 'squaredVisual': {'model': 'EmbedImage',
                   'src': 'https://www.radiofrance.fr/s3/cruiser-production-eu3/2024/04/dcfe0c1b-c884-43a7-bfe9-082d622dbf2f/400x400_sc_16-9-lejournalintimededithpiaf-1.jpg',
                   'webpSrc': 'https://www.radiofrance.fr/s3/cruiser-production-eu3/2024/04/dcfe0c1b-c884-43a7-bfe9-082d622dbf2f/400x400_sc_16-9-lejournalintimededithpiaf-1.webp',
                   'legend': 'Visuel du podcast "Le journal intime d\'Edith Piaf",
 épisode n°1',
                   'copyright': 'Aucun(e)',
                   'author': '©Radio France - Atelier graphique RF',
                   'width': 400,
                   'height': 400,
                   'preview': '/9j/2wBDACgcHiMeGSgjISMtKygwPGRBPDc3PHtYXUlkkYCZlo+AjIqgtObDoKrarYqMyP/L2u71////m8H////6/+b9//j/2wBDASstLTw1PHZBQXb4pYyl+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj/wAARCAAqACoDASIAAhEBAxEB/8QAGAAAAwEBAAAAAAAAAAAAAAAAAAEDBAL/xAAaEAEBAQEBAQEAAAAAAAAAAAAAAQIDESEx/8QAGAEBAAMBAAAAAAAAAAAAAAAAAAECAwT/xAAWEQEBAQAAAAAAAAAAAAAAAAAAARH/2gAMAwEAAhEDEQA/AKg7Cq7otAIxXTAAvHWonpbbPuoY2j05Ubp1nQiVeH45wp4NJR1rJ001dmLqhindfXeNIX9U5g286uz8mkTr/9k=',
                   'id': 'dcfe0c1b-c884-43a7-bfe9-082d622dbf2f',
                   'type': 'image',
                   'preset': '400x400'},
 'serie': {'path': 'francemusique/podcasts/serie-le-journal-intime-d-edith-piaf',
           'relationMeta': {'episode_order': 0,
                            'episode_title': "Le journal intime d'Édith Piaf 1/7 : Je suis née comme un moineau",
                            'episode_number': 1}},
 'concept': {'id': '5c8b5647-1f5f-40fa-8c73-75af4d88e69b',
             'title': 'Le journal intime de...',
             'path': 'francemusique/podcasts/le-journal-intime-de',
             'visual': None,
             'squaredVisual': {'model': 'EmbedImage',
                               'src': 'https://www.radiofrance.fr/s3/cruiser-production/2023/06/244c6fcd-53f0-4d10-b7e2-a627fe6f0aae/400x400_sc_carre-le-journal-intime-de.jpg',
                               'webpSrc': 'https://www.radiofrance.fr/s3/cruiser-production/2023/06/244c6fcd-53f0-4d10-b7e2-a627fe6f0aae/400x400_sc_carre-le-journal-intime-de.webp',
                               'legend': 'Le journal intime de...',
                               'copyright': 'Radio France',
                               'author': None,
                               'width': 400,
                               'height': 400,
                               'preview': '/9j/2wBDACgcHiMeGSgjISMtKygwPGRBPDc3PHtYXUlkkYCZlo+AjIqgtObDoKrarYqMyP/L2u71////m8H////6/+b9//j/2wBDASstLTw1PHZBQXb4pYyl+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj/wAARCAAqACoDASIAAhEBAxEB/8QAGAAAAwEBAAAAAAAAAAAAAAAAAQIDAAT/xAAYEAEBAQEBAAAAAAAAAAAAAAAAAQISEf/EABgBAAMBAQAAAAAAAAAAAAAAAAABAgME/8QAFxEBAQEBAAAAAAAAAAAAAAAAAAEREv/aAAwDAQACEQMRAD8AtaHoUtU30bSaYKSpSWF5U8bkK10aynY6tYS1gObUPG8V4aYJUpJkeVJg3Bq6dWsp3C9LSYufgZhVoASYNweCD1//2Q==',
                               'id': '244c6fcd-53f0-4d10-b7e2-a627fe6f0aae',
                               'type': 'image',
                               'preset': '400x400'}},
 'mainResourceAudioAndVideo': None,
 'manifestations': [{'model': 'ManifestationAudio',
                     'id': '816a9449-0456-482c-b50b-25c8a52ffd0f',
                     'title': "Le journal intime d'Edith Piaf - Episode 1 : je suis née comme un moineau",
                     'url': 'https://media.radiofrance-podcast.net/podcast09/21815-10.04.2024-ITEMA_23689488-2024M42151E0001-25.m4a',
                     'created': 1712700420,
                     'duration': 596,
                     'shareable': False,
                     'principal': True,
                     'preset': {'id': '25',
                                'name': 'stereo',
                                'encoding': 'AAC',
                                'bitrate': 192,
                                'frequency': 48,
                                'level': '-16LUFS (stéréo)'}},
                    {'model': 'ManifestationAudio',
                     'id': '5b274c5e-4ee9-42e5-8d16-1e09e7d96c06',
                     'title': "Le journal intime d'Edith Piaf - Episode 1 : je suis née comme un moineau",
                     'url': 'https://media.radiofrance-podcast.net/podcast09/21815-10.04.2024-ITEMA_23689488-2024M42151E0001-21.mp3',
                     'created': 1712700420,
                     'duration': 596,
                     'shareable': False,
                     'principal': False,
                     'preset': {'id': '21',
                                'name': 'stereo',
                                'encoding': 'MP3',
                                'bitrate': 128,
                                'frequency': 44.1,
                                'level': '-15LUFS (stéréo)'}},
                    {'model': 'ManifestationAudio',
                     'id': 'b498d35a-666c-4d27-8dd3-8d666d076ef8',
                     'title': "Le journal intime d'Edith Piaf - Episode 1 : je suis née comme un moineau",
                     'url': 'https://media.radiofrance-podcast.net/podcast09/21815-10.04.2024-ITEMA_23689488-2024M42151E0001-26.mp3',
                     'created': 1712700420,
                     'duration': 594,
                     'shareable': False,
                     'principal': False,
                     'preset': {'id': '26',
                                'name': 'stereo',
                                'encoding': 'MP3',
                                'bitrate': 128,
                                'frequency': 44.1,
                                'level': '-16LUFS (stéréo + EQ Merlin)'}}]}
```

# Technical elements and research #

RadioFrance podcaste page based on *svelte*. All page have a `__data.json` child with **lot of** interesting data.

Streams files are of the form: *https://media.radiofrance-podcast.net/…/xxx-date-ITEMA-xxx.[mp3|m4a]*

Podcast data Url: `https://www.radiofrance.fr[/radio]/podcasts/__data.json` with an optionnal argument 'p' (the page, so `__data.json?p=2` for example).

## Page element classes ##

Svelte classes:
- cardCategory : Podcast category entry
  - cardCategory-image
  - cardCategory-link (<a> element holding the text)
- CardPodcast : Single podcast entry
    - CardPodcast-details (<a> element with 'label' attribute)
    - CardVisual
        - CardVisual-overlay
            - HoverDetails
                - HoverDetails-description (text)
                - HoverDetails-buttons
- CardWebRadio
    - CardWebRadio-details
        - CardWebRadio-details-parentStation
        - CardWebRadio-details-name (<a> element holding the text)
    - CardWebRadio-visual
- CardMedia
    - CardMedia-visual
    - CardTitle (<a> toward dedicated page, hodling the text)

## __data.json structures ##

Data are in `.nodes|.[2]`

where numbers are entries index in `.nodes|.[2].data` (here title is `.nodes|.[2].data.[14880]` )

- Model:
    - "Highlight" (35) aka category
    - "HighlightElement" (39) aka category element
    - "Concept" (70) aka podcast serie
    - "Expression" (105, 48) aka item page
    - "Tag" (264) aka… tag
    - "ManifestationAudio" (143, 289) item sound path (old the url audio path)
    - "Theme"
    - "PageTemplate"

Podcast serie (see `"model": 70`)description are:

``` json
{
    "model": 70,
    "id": 252,
    "title": 253,
    "path": 254,
    "standFirst": 255,
    "migrated": 15,
    "staff": 256,
    "producers": 269,
    "themes": 272,
    "mainImageUuid": 282,
    "visual": 283,
    "visualVerticalUuid": 290,
    "baseline": 291,
    "promoEpisode": 292,
    "manifestations": -1,
    "brand": 340,
    "isTimeshiftable": 29
}

```

Podcast item page (see `"model": 105`) are:
``` json
{
  "id": 14053,
  "title": 14054,
  "standFirst": 14055,
  "brandEnums": 14056,
  "isExpired": 29,
  "model": 105,
  "type": 106,
  "kind": 300,
  "guest": 14057,
  "publishedDate": 14068,
  "startDate": 14068,
  "endDate": 14069,
  "path": 14070,
  "migrated": 15,
  "visual": 14071,
  "squaredVisual": 14079,
  "serie": 14083,
  "concept": 14086,
  "mainResourceAudioAndVideo": 28,
  "manifestations": 14088
}
```

Podcast item sound (see `"model": 143`) descriptions are: `.nodes|.[2].data.[]|try if type == "object"  and .url then . else empty end`. It provides:
``` json
{
  "model": 143,
  "id": 14902,
  "title": 14880,
  "url": 14903,
  "created": 14898,
  "duration": 14904,
  "shareable": 29,
  "principal": 29,
  "preset": 14905
}
```
