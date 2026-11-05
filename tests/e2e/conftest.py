"""Fixtures communes des tests navigateur."""
import pytest

# Jeux en 3D (WebGL : L'île, Braquage) : sans carte graphique, Chromium sans fenêtre dessine la 3D par logiciel
# (SwiftShader). Sur un petit processeur (Mac mini i3), une image prend alors plus d'une seconde : le fil principal
# est bloqué, chaque requête du jeu dépasse son délai (1,8 s) et la partie affiche « Connexion perdue » sans jamais
# démarrer — ce que ne vit aucun téléphone. Ces tests demandent donc la carte graphique quand elle existe (Metal sur
# Mac ; options ignorées ailleurs, où l'on retombe sur le rendu logiciel).
GPU_ARGS = ['--enable-gpu', '--ignore-gpu-blocklist', '--use-angle=metal']


@pytest.fixture(scope='module')
def gpu_browser(browser_type, browser_type_launch_args):
    args = [*browser_type_launch_args.get('args', []), *GPU_ARGS]
    browser = browser_type.launch(**{**browser_type_launch_args, 'args': args})
    yield browser
    browser.close()
