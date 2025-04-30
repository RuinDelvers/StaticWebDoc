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

		if dataclasses.is_dataclass(self):
			value = dataclasses.asdict(self)
			serial = {**serial, **value}
		else:
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
	def json(self):
		return self.name

class JSONEncoder:
	def __call__(self, obj):
		if isinstance(obj, JSON):
			return obj.json()
		elif isinstance(obj, set):
			return list(obj)
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
	def data_prefix(self):
		return "cache"

	@property
	def cache(self):
		return self.__cache

	def __str__(self):
		return f"{self.__class__.__name__}({str(self.__cache)})"

	def __contains__(self, template):
		if type(template) == tuple and len(template) == 2:
			return template[0] in self.__cache and template[1] in self.__cache[template[0]]
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

	def set_field(self, template, data):
		self[template] = data

	def json(self):
		return self.__cache

	def write(self, data_path):
		#directories = {}
		structure = { "type": "dir", "files": {}}

		def add_file(file):
			# If it is a file
			section = structure
			parts = file.parts

			for i, p in enumerate(parts):
				if p not in section["files"]:
					if i == len(parts) - 1:
						section["files"][p] = { "type": "file", "name": p}
					else:
						section["files"][p] = { "type": "dir", "files": {}, "name": p}

				section = section["files"][p]



		data_path = data_path/self.data_prefix

		for (template, data) in self.cache.items():

			path = (data_path/template).with_suffix(".json")
			add_file(path.relative_to(data_path))
			path.parent.mkdir(parents=True, exist_ok=True)

			with open(path, 'wb') as output:
				encoder = JSONEncoder()
				value = orjson.dumps(
					data,
					option=self.env.project.json_flags,
					default=encoder)
				output.write(value)

		files = list(data_path.rglob("*"))
		files.append(data_path)

		"""
		for f in files:
			relf = f.relative_to(data_path)
			root = structure

			for p in relf.parts:
				if p not in root:
					root[p] = {}
				root = root[p]

			if f.is_dir():
				if f not in directories:
					directories[f] = []



				for child in files:
					if f == child.parent:
						directories[f].append(child.relative_to(f).as_posix())
		"""


		with open(data_path/"structure.json", 'wb') as output:
			output.write(orjson.dumps(structure, option=orjson.OPT_INDENT_2))

		"""
		for d, f in directories.items():
			with open(d/"files.json", 'wb') as output:
				output.write(orjson.dumps(f))
		"""



class FragmentCache(SimpleCache, HasCallables):
	"""
	A Cache of HTML strings that can be referenced by other templates when rendering.
	"""

	@property
	def data_prefix(self):
		return "fields"

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
	def data_prefix(self):
		return "objects"

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

	def set_field(self, template, data_env, key, data):
		self.cache[template][data_env][key] = data

	def get_field(self, template, data_env, key):
		return self.cache[template][data_env][key]

	def write(self, data_path):
		values = []
		for (template, data) in self.cache.items():
			try:
				encoder = JSONEncoder()
				value = orjson.dumps(
					data,
					option=self.env.project.json_flags,
					default=encoder)
				values.append(value)
			except Exception as ex:
				print(f"Failed serializing {template}")
				raise ex

		concat = b',\n'.join(values)
		with open(data_path/"embedded_data.json", 'wb') as output:
			output.write(b'[')
			output.write(concat)
			output.write(b']')


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

		#self.environment.embedded_data[filename, name] = {}
		rv = caller()

		self.environment.embedded_data.data_env = None

		return rv