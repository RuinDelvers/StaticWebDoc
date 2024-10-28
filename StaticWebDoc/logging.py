from termcolor import colored
class Logger:
	def __init__(self):
		pass

	def normal(self, msg, color=None):
		print(colored(msg, self.normal_color if color is None else color))

	def warning(self, msg):
		print(colored(msg, self.warning_color))

	def error(self, msg):
		print(colored(msg, self.error_color))

	@property
	def normal_color(self): return "cyan"

	@property
	def warning_color(self): return "yellow"

	@property
	def error_color(self): return "red"

DEFAULT = Logger()