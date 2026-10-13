from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
class Handler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith('/ids_jmk/'):
            self.path='/custom_components/ids_jmk/www/'+self.path[len('/ids_jmk/'):]
        return super().do_GET()
ThreadingHTTPServer(('127.0.0.1',18765),Handler).serve_forever()
