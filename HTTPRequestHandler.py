from __future__ import print_function
import cgi
import sys

if sys.version.startswith("3"):
    from http.server import BaseHTTPRequestHandler
else:
    from BaseHTTPServer import BaseHTTPRequestHandler


def makeHTTPRequestHandler(get_callback=None, post_callback=None, callback_args={}):
    """
    Factory method to create HTTPRequestHandler class with custom GET and POST callbacks.

    Usage:

    extra_args = {"random_num": 123}
    http_server = HTTPServer(("", args.http_port), makeHTTPRequestHandler(handle_get_request, handle_post_request, extra_args))
    http_server.serve_forever()

    def handle_get_request(http_request_handler, get_vars, **kwargs):
        with open("index.html","rb") as f:
            http_request_handler.wfile.write(f.read())

    def handle_post_request(http_request_handler, post_vars, **kwargs):
        for key, val in post_vars.items():
            print("%s: %s" % (key, val))
            print(kwargs["random_num"])
    """

    class HTTPRequestHandler(BaseHTTPRequestHandler):

        def __init__(self, request, client_address, server):
            BaseHTTPRequestHandler.__init__(self, request, client_address, server)

        def set_headers(self):
            """
            Return OK message.
            """
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()

        def do_GET(self):
            """
            Parse GET request and call get_callback(HTTPRequestHandler, get_vars, **callback_args).
            """
            self.set_headers()

            # TODO: parse get content
            if get_callback is not None:
                get_callback(self, None, **callback_args)

        def do_POST(self):
            """
            Parse POST request and call post_callback(HTTPRequestHandler, post_vars, **callback_args)
            """

            self.set_headers()

            # Parse post content
            content_type, parse_dict = cgi.parse_header(self.headers["Content-Type"])
            if content_type == "multipart/form-data":
                post_vars = cgi.parse_multipart(self.rfile, parse_dict)
            elif content_type == "application/x-www-form-urlencoded":
                content_length = int(self.headers["Content-Length"])
                post_vars = cgi.parse_qs(self.rfile.read(content_length), keep_blank_values=1)
            else:
                post_vars = {}

            if post_callback is not None:
                post_callback(self, post_vars, **callback_args)

    return HTTPRequestHandler
