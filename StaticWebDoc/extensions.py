import jinja2
import pathlib
import enum

import StaticWebDoc as SWD
import dataclasses
import typing

from jinja2 import nodes

@dataclasses.dataclass
class JSONValue:
	value: typing.Any


class JSON:
	def json(self):
		serial = { "type": type(self).__name__ }

		for attr in dir(self):
			obj = getattr(self, attr)
			if isinstance(obj, JSONValue):
				serial[attr] = obj.value

		return serial

class ObjectAsArray:
	"""
	Mark class used to update object data and store it in an array even when set as a singular object.
	"""
	pass

class JSONEnumValue(JSON):
	def __init__(self, name, value):
		self.name = name
		self.value = value

	def json(self):
		return { "type": "enum", "name": self.name, "value": self.value}

class JSONEncoder:
	def __call__(self, obj):
		if isinstance(obj, JSON):
			return obj.json()
		else:
			raise TypeError



class FragmentCacheExtension(jinja2.ext.Extension):

	tags = {"fieldblock"}

	def __init__(self, environment):
		super().__init__(environment)

	def parse(self, parser):
		lineno = next(parser.stream).lineno
		blockname = parser.parse_expression()
		filename = parser.name

		args = [nodes.Const(filename), nodes.Const(blockname.name)]
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

		if not self.environment.has_cache(filename, name):
			self.environment.add_cache(filename, name, rv)

		return ""

class EmbeddedDataExtension(jinja2.ext.Extension):

	tags = {"data"}

	def parse(self, parser):
		lineno = next(parser.stream).lineno

		args = [nodes.Const(parser.name)]

		key = parser.parse_expression()
		args.append(nodes.Const(key.name))

		if parser.stream.skip_if("assign"):
			args.append(parser.parse_expression())
		else:
			parser.fail("Failed data parsing")

		return nodes.CallBlock(
			self.call_method("handle", args), [], [], [nodes.Const(None)]
		).set_lineno(lineno)

	def handle(self, template_name, key, value, caller):
		template_name = SWD.template_to_name(template_name)
		if isinstance(value, jinja2.Undefined):
			raise ValueError(f"[{template_name}] Attempted to set value to undefined for key={key}")
		if isinstance(value, ObjectAsArray):
			value = [value]

		self.environment.get_data()[template_name][self.environment.data_env][key] = value
		return ""



class EmbeddedDataSectionExtension(jinja2.ext.Extension):

	tags = {"datasection"}

	def parse(self, parser):
		lineno = next(parser.stream).lineno
		blockname = parser.parse_expression()
		filename = parser.name

		args = [nodes.Const(filename), nodes.Const(blockname.name)]
		body = parser.parse_statements(["name:enddatasection"], drop_needle=True)

		return nodes.CallBlock(
			self.call_method("_data_section_support", args), [], [], body
		).set_lineno(lineno)


	def _data_section_support(self, filename, name, caller):
		self.environment.set_data_env(name)
		filename = SWD.template_to_name(filename)

		if not self.environment.has_data(filename, name):
			self.environment.add_data(filename, name, {})

		rv = caller()

		self.environment.clear_env()

		return rv