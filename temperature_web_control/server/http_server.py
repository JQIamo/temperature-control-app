import os
from logging import Logger
from socketserver import TCPServer
from http.server import SimpleHTTPRequestHandler

DIRECTORY = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../web/public/")

get_request_handler = {}

class HTTPRequestHandler(SimpleHTTPRequestHandler):
    def __init__(self, request, client_address, server):
        super().__init__(request, client_address, server, DIRECTORY)

    def do_GET(self):
        request_path = self.path
        if request_path in get_request_handler:
            resp_code, type, resp = get_request_handler[request_path](self)
            self.send_response(resp_code)
            # self.send_header('content-type', 'application/json')
            self.send_header('content-type', type)
            self.end_headers()
            self.wfile.write(resp)
        else:
            super().do_GET()

def serve_http(bind_addr, port, get_handler, logger: Logger):
    global get_request_handler

    if get_handler:
        get_request_handler = get_request_handler
    with TCPServer((bind_addr, port), HTTPRequestHandler) as httpd:
        logger.info(f"Start HTTP server at {bind_addr:port}.")
        httpd.serve_forever()
