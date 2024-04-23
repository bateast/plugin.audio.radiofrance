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
