import jinja2

from jinja2.ext import Extension
from jinja2 import nodes

class FragmentCacheExtension(jinja2.ext.Extension):

	tags = {"fieldblock"}

	def __init__(self, environment):
		super().__init__(environment)

	def parse(self, parser):
		lineno = next(parser.stream).lineno
		blockname = parser.parse_expression()
		args = [nodes.Const(parser.name), nodes.Const(blockname.name)]
		body = parser.parse_statements(["name:endfieldblock"], drop_needle=True)

		# Create a block of the same name so that it can be overwritten in child classes.
		block = nodes.Block(lineno=lineno)
		block.name = blockname.name
		block.scoped = True
		block.required = False
		block.body = body

		return nodes.CallBlock(
			self.call_method("_cache_support", args), [], [], [block]
		).set_lineno(lineno)

	def _cache_support(self, filename, name, caller):		
		rv = caller()
		self.environment.add_data(filename, name, rv)

		return ""