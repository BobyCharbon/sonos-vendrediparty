"""Démarre le serveur du banc (base de TEST, drapeaux de la prod) et le garde en marche ; écrit son adresse dans
state.json. Usage : BOTS_OUT=<dossier> .venv/bin/python -m tests.bots.serve <sources> <module construit>"""
import signal
import sys
import time
from pathlib import Path

from tests.bots.bench import OUT, prod_flags, save_state, start_server

if __name__ == "__main__":
    source, dist = Path(sys.argv[1]), Path(sys.argv[2])
    proc, url = start_server(source, dist, OUT / "server-data")
    save_state(origin=url, flags=prod_flags(), source=str(source), dist=str(dist))
    print(f"Serveur du banc : {url} (drapeaux de la prod : {prod_flags()})", flush=True)
    signal.signal(signal.SIGTERM, lambda *_: (proc.terminate(), sys.exit(0)))
    try:
        while proc.poll() is None:
            time.sleep(1)
    finally:
        proc.terminate()
