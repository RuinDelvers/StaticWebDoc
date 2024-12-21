import jinja2
import orjson

import StaticWebDoc as SWD
import dataclasses
import typing
import pathlib

from jinja2 import nodes

class DataExtensionObject:
	"""
	This is used as a marker type for extension data to determine whether or not it needs to be written to the
	data section of a render.
	"""
	def write(self, data_path):
		pass

class HasCallables:
	def get_callables(self):
		callables = {}
		for a in dir(self):
			obj = getattr(self, a)
			if hasattr(obj, "is_project_callable") and obj.is_project_callable:
				callables[obj.callable_name] = obj

		return callables


def callable(fn):
	"""
	This decorated is used by extensions to be automatically detected as callable for the HasCallables marker class.
	"""
	if isinstance(fn, str):
		name = fn
		def inner(fn):
			fn.is_project_callable = True
			fn.callable_name = name
			return fn
		return inner
	else:
		fn.is_project_callable = True
		fn.callable_name = fn.__name__
		return fn

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

class SimpleCache(JSON, DataExtensionObject):
	def __init__(self, env):
		self.__env = env
		self.__cache = {}

	@property
	def env(self):
		return self.__env

	def has_path(self, *args):
		d = self.__cache
		for a in args:
			if a in d:
				d = d[a]
			else:
				return False

		return True

	@property
	def cache(self):
		return self.__cache

	def __str__(self):
		return f"{self.__class__.__name__}({str(self.__cache)})"

	def __contains__(self, template):
		return template in self.__cache

	def __getitem__(self, template):
		if isinstance(template, str):
			return self.__cache[template]
		else:
			return self.__cache[template[0]][template[1]]

	def __setitem__(self, template, data):
		if template[0] not in self.__cache:
			self.__cache[template[0]] = {}

		self.__cache[template[0]][template[1]] = data

	def json(self):
		return self.__cache

class FragmentCache(SimpleCache, HasCallables):
	"""
	A Cache of HTML strings that can be referenced by other templates when rendering.
	"""

	def write(self, data_path):
		with open(data_path/"fields.json", 'wb') as output:
			value = orjson.dumps(self.cache, option=orjson.OPT_INDENT_2)
			output.write(value)


	@callable
	def link_to(self, template_name, display=None):
		inpath = pathlib.Path(template_name)

		if inpath.suffix != SWD.TEMPLATE_EXTENSION:
			template_name += SWD.TEMPLATE_EXTENSION

		if display is None:
			display = self.get_field(template_name, "name")

		path = self.env.project.template_to_outpath(template_name)

		return jinja2.filters.Markup(f"<a href={path}>{display}</a>")

	@callable
	def get_field(self, template, key):

		checkpath = pathlib.Path(template)

		if checkpath.suffix != SWD.TEMPLATE_EXTENSION:
			template += SWD.TEMPLATE_EXTENSION

		if template not in self.cache:
			self.env.project.request_render(template)

		if template not in self.cache:
			raise ValueError(f"Template '{template}' does not have key '{key}'")

		if key in self[template]:
			return self[template, key].strip()
		else:
			raise ValueError(f"Template '{template}' does not have key '{key}'")

class FragmentCacheExtension(jinja2.ext.Extension):
	tags = {"fieldblock"}

	def __init__(self, environment):
		super().__init__(environment)

		environment.extend(fragment_cache_prefix="", fragment_cache=FragmentCache(self.environment))

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
		self.environment.fragment_cache[filename, name] = rv
		return ""

class EmbeddedData(SimpleCache):
	"""
	A Cache of python objects that are can be both used by templates and serialized to JSON for use in the main
	rendered page.
	"""

	def __init__(self, env):
		super().__init__(env)
		self.__current_env = None

	@property
	def data_env(self):
		if self.__current_env is None:
			raise ValueError("Attempted to embed data in a null data environment.")

		return self.__current_env


	@data_env.setter
	def data_env(self, value):
		self.__current_env = value

	def __setitem__(self, template, data):
		if self.data_env is None:
			raise ValueError(f"Attempted to add data to a null data environment: {template}")

		if template[0] not in self.cache:
			self.cache[template[0]] = {
				self.data_env: {}
			}

		self.cache[template[0]][self.data_env][template[1]] = data

	def write(self, data_path):
		for (template, data) in self.cache.items():
			path = (data_path/template).with_suffix(".json")
			path.parent.mkdir(parents=True, exist_ok=True)

			with open(path, 'wb') as output:
				encoder = JSONEncoder()
				value = orjson.dumps(
					data,
					option=self.env.project.json_flags,
					default=encoder)
				output.write(value)

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

		self.environment.embedded_data[template_name, key] = value
		return ""



class EmbeddedDataSectionExtension(jinja2.ext.Extension):

	tags = {"datasection"}

	def __init__(self, environment):
		super().__init__(environment)

		environment.extend(embedded_data_prefix="", embedded_data=EmbeddedData(self.environment))

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
		self.environment.embedded_data.data_env = name
		filename = SWD.template_to_name(filename)

		self.environment.embedded_data[filename, name] = {}
		rv = caller()

		self.environment.embedded_data.data_env = None

		return rv