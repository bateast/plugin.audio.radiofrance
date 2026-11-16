import os
import sys

# Permet d'importer utils.py (à la racine du dépôt) sans installation du
# paquet ni dépendance aux modules Kodi (xbmc, xbmcgui, ...), qui ne sont
# disponibles qu'à l'intérieur de Kodi. utils.py gère lui-même l'absence de
# `xbmc` via un import optionnel (voir `log_error` dans utils.py).
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
