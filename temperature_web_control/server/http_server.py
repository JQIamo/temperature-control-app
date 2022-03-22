from logging import Logger
from socketserver import TCPServer
from http.server import SimpleHTTPRequestHandler



def serve_http(bind_addr, port, _directory, get_handler, logger: Logger):
    get_request_handler = {}

    class HTTPRequestHandler(SimpleHTTPRequestHandler):
        def __init__(self, request, client_address, server):
            super().__init__(request, client_address, server, directory=_directory)

        def do_GET(self):
            request_path = self.path
            if request_path in get_request_handler:
                resp_code, type, resp = get_request_handler[request_path](self)
                self.send_response(resp_code)
                self.send_header('Content-type', type)
                self.end_headers()
                self.wfile.write(resp.encode("utf-8"))
            else:
                super().do_GET()

    if get_handler:
        get_request_handler = get_handler
    with TCPServer((bind_addr, port), HTTPRequestHandler) as httpd:
        logger.info(f"Start HTTP server at {bind_addr}:{port}.")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass
