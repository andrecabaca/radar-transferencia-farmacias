"""Servidor local do Radar de Transferencia de Farmacias.

Serve a pasta onde este ficheiro esta na porta indicada pela variavel de
ambiente PORT. Sem PORT usa a 8777, que e a porta do "Abrir Radar.bat".

Ler a porta do ambiente e o que permite ter varias sessoes a correr o radar
ao mesmo tempo sem chocarem na mesma porta.
"""

import os
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

RAIZ = os.path.dirname(os.path.abspath(__file__))
PORTA = int(os.environ.get("PORT") or 8777)


class Handler(SimpleHTTPRequestHandler):
    def end_headers(self):
        # os JSON da pasta dados sao regenerados pelos scripts; sem isto o
        # navegador continua a servir a versao anterior depois de os correr
        self.send_header("Cache-Control", "no-store")
        SimpleHTTPRequestHandler.end_headers(self)


if __name__ == "__main__":
    servidor = ThreadingHTTPServer(
        ("127.0.0.1", PORTA), partial(Handler, directory=RAIZ)
    )
    print("Radar em http://127.0.0.1:%d" % PORTA, flush=True)
    servidor.serve_forever()
