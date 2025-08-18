"""
This module outlines a basic testing server for a SWD project. This is used so it doesn't need to be
fully packaged to be able to correctly route requests.
"""

import pathlib
import http.server as serv
import contextlib
import socket

import StaticWebDoc.modules as modules

# Needed here, because the router construct seems to delete the variable reference.
LOADER = modules.ModuleLoader()
REROUTE_PATH = pathlib.Path("/render")

class SWD_Router(serv.SimpleHTTPRequestHandler):
	def __init__(self, *args, directory=None, **kwargs):
		super().__init__(*args, directory=directory, **kwargs)

	def translate_path(self, path):
		if path.startswith("/@"):
			module, _, tfile = LOADER.load_module(path[1:])

			reroute = module.get_file_path(tfile)

			print(f"- Module received, rerouting: {path} -> {reroute}")

			return reroute
		else:
			p = pathlib.Path(path).relative_to("/")

			if p.is_relative_to("document") or p.is_relative_to("data"):
				path = (REROUTE_PATH/p).as_posix()

				return super().translate_path(path)
			else:
				return super().translate_path(path)

def main(directory):
	class SWD_Server(serv.ThreadingHTTPServer):
		def server_bind(self):
			# suppress exception when protocol is IPv4
			with contextlib.suppress(Exception):
				self.socket.setsockopt(
					socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
			return super().server_bind()

		def finish_request(self, request, client_address):
			self.RequestHandlerClass(request, client_address, self,
										directory=directory)

	serv.test(
		HandlerClass=SWD_Router,
		ServerClass=SWD_Server,
		port=8080)