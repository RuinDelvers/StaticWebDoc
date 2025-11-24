import jinja2
import pathlib
import shutil
import orjson
import os
import dataclasses
import htmlmin

import jinja2.ext
import jinja2.filters

import StaticWebDoc.extensions as extensions
import StaticWebDoc.filters as filters
import StaticWebDoc.logging as logging
import StaticWebDoc.loader as loader
import StaticWebDoc.utils as utils

from StaticWebDoc.environment import CustomEnvironment
from StaticWebDoc.exceptions import RenderError
from termcolor import colored
from bs4 import BeautifulSoup as bs

TEMPLATE_EXTENSION = ".jinja"
OUTPUT_EXTENSION = ".html"
CLASS_EXTENSION = ".class"

DEFAULT_TEMPLATE_DIR = "template"
DEFAULT_RENDER_DIR = "render"
DEFAULT_MODULE_DIR = "modules"
DOCUMENT_DIR = "document"
STYLE_DIR = "style"
SCRIPT_DIR = "scripts"
DATA_DIR = "data"
IMAGE_DIR = "images"
DEFAULT_BUILD_DIR = "build"
CACHE_FILE = "fields.json"
OBJECT_FILE = "objects.json"

# Global types/functions that have been added to be made available for use.
GLOBAL_PROJECT_TYPES = []
GLOBAL_FUNCTIONS = []
GLOBAL_FILTERS = []

class Markupable:
	""" Marker class to determine whether or not to call markup on when rendering."""

	def markup(self):
		raise NotImplementedError(f"markup() not implemented for {type(self).__name__}")

	def __str__(self):
		return self.markup()


def _link(location, display_text, class_type=""):
	path_check = pathlib.Path(location)
	if path_check.suffix != OUTPUT_EXTENSION:
		location += OUTPUT_EXTENSION

	return jinja2.filters.Markup(f'<a href="/document/{location}" class="{class_type}"> {display_text} </a>')

def template_to_name(template_name, root=None, base_only=False):
	p = pathlib.Path(template_name)

	if root is None:
		if base_only:
			return p.with_suffix("").name
		else:
			return p.with_suffix("").as_posix()
	else:
		if base_only:
			return p.relative_to(root).with_suffix("").name
		else:
			return p.relative_to(root).with_suffix("").as_posix()

def _get_markup(value):
	if isinstance(value, Markupable):
		return jinja2.filters.Markup(value.markup())
	else:
		return jinja2.filters.Markup(value)

def proj_fn(name):
	if type(name) == str:
		def inner(fn):
			GLOBAL_FUNCTIONS.append((name, fn))
			return fn
		return inner
	else:
		GLOBAL_FUNCTIONS.append(name)
		return name

def proj_filter(name):
	if type(name) == str:
		def inner(fn):
			GLOBAL_FILTERS.append((name, fn))
			return fn
		return inner
	else:
		GLOBAL_FILTERS.append(name)
		return name

def proj_type(value):
	value.is_project_defined_type = True

	GLOBAL_PROJECT_TYPES.append(value)

	return value

def project_template_path():
	return pathlib.Path(__file__).parent/"template"

def initialize_project(path):
	shutil.copytree(project_template_path(), path)

@dataclasses.dataclass(frozen=True)
class BuildFlags:
	beautify: bool = True

class Project:
	current = None

	source: str = DEFAULT_TEMPLATE_DIR
	output: str = DEFAULT_RENDER_DIR
	build: str = DEFAULT_BUILD_DIR
	modules_dir: str = DEFAULT_MODULE_DIR
	script_dir: str = SCRIPT_DIR
	style_dir: str = STYLE_DIR
	image_dir: str = IMAGE_DIR
	data_dir: str = DATA_DIR
	document_dir: str = DOCUMENT_DIR
	env: jinja2.Environment | None = None
	exts = []
	global_vars = {}
	modules = []
	template_filters = [filters.LastModified]
	logger: logging.Logger = logging.DEFAULT
	json_flags: int = orjson.OPT_INDENT_2

	cache_file = CACHE_FILE
	object_file = OBJECT_FILE

	def __init__(self, root):
		if Project.current is not None:
			raise ValueError("Attempted to instantiate multiple projects at once.")

		Project.current = self
		root = pathlib.Path(root)

		self.__proj_root = root
		self.__input = root/self.source
		self.__output = root/self.output
		self.__modules = root/self.modules_dir
		self.__scripts = self.__proj_root/self.script_dir
		self.__images = root/self.image_dir
		self.__styles = root/self.style_dir
		self.__docroot = self.__output/self.document_dir
		self.__dataroot = self.__output/self.data_dir
		self.__build_dir = self.__proj_root/f"../{self.build}"
		self.__build_spec = None

		if self.env is None:
			env = CustomEnvironment()
			self.env = CustomEnvironment(
				loader=loader.CustomLoader([self.__input]),
				autoescape=jinja2.select_autoescape(),
				extensions=[
					extensions.FragmentCacheExtension,
					extensions.EmbeddedDataExtension,
					extensions.EmbeddedDataSectionExtension,
					extensions.ExternalModuleExtension]
					+ self.exts)

		self.env.undefined = jinja2.StrictUndefined
		self.env.extend(project_extension="", project=self)

		self.__filters = list(map(lambda x: x(self), self.template_filters))

		self.import_modules()
		self.__init_jinja_globals()

		self.__rendered_templates = set()
		self.__renderable_templates = []

		self.init()

		self.__context_data = {}
		self.__render_stack = []

	@property
	def proj_root(self):
		return self.__proj_root

	@property
	def template_dir(self):
		return self.__input

	def init(self):
		pass

	def add_global(self, key, item):
		if key in self.env.globals:
			raise ValueError(f"Globals key already in use: {key}")

		self.env.globals[key] = item

	def __init_jinja_globals(self):
		self.add_global("PROJECT", self)
		self.add_global("style_dir", self.style_dir)
		self.add_global("script_dir", self.script_dir)
		self.add_global("image_dir", self.image_dir)
		self.add_global("document_dir", self.document_dir)
		self.add_global("template_name", template_to_name)
		self.add_global("iter_template", self.iter_template)

		self.add_global("style", utils.style)
		self.add_global("script", utils.script)
		self.add_global("link", _link)
		self.add_global("imported_styles", self.__print_imported_styles)
		self.add_global("imported_scripts", self.__print_imported_scripts)
		self.add_global("markup", _get_markup)
		self.add_global(self.pop_context_data.__name__, self.pop_context_data)
		self.add_global(self.set_context_data.__name__, self.set_context_data)
		self.add_global(self.get_context_data.__name__, self.get_context_data)
		self.add_global(self.current_template.__name__, self.current_template)
		self.add_global(self.env_data.__name__, self.env_data)

		for key, value in self.global_vars.items():
			self.add_global(key, value)

		for gtype in GLOBAL_PROJECT_TYPES:
			gtype.project = property(lambda _: self)
			self.add_global(gtype.__name__, gtype)

		for fn in GLOBAL_FUNCTIONS:
			if isinstance(fn, tuple):
				name, bound = fn
				self.add_global(name, bound)
			else:
				self.__add_proj_fn(fn.__name__, fn)

		for obj in GLOBAL_FILTERS:
			if isinstance(obj, tuple):
				name, fn = obj
				self.env.filters[name] = fn
			else:
				self.env.filters[obj.__name__] = obj

		# After extensions have been applied, we search through extended objects to see if any of them
		# have callables. If so we add them as global callable functions.
		for v in dir(self.env):
			obj = getattr(self.env, v)
			if isinstance(obj, extensions.HasCallables):
				for name, call in obj.get_callables().items():
					self.add_global(name, call)

	def __print_imported_scripts(self):
		key = f"{extensions.ExternalModuleExtension.__module__}.{extensions.ExternalModuleExtension.__qualname__}"
		return self.env.extensions[key].print_scripts()

	def __print_imported_styles(self):
		key = f"{extensions.ExternalModuleExtension.__module__}.{extensions.ExternalModuleExtension.__qualname__}"
		return self.env.extensions[key].print_style()

	def __add_proj_fn(self, name, fn):
		self.add_global(name, lambda *args, **kwds: fn(self, *args, **kwds))

	def template_to_outpath(self, template_name):
		path = pathlib.Path(self.__docroot)/template_name
		path = path.with_suffix(OUTPUT_EXTENSION)

		# Need to make sure that this is considered from the root of the website.
		return f"/document/{path.relative_to(self.__docroot)}"

	def is_renderable_template(self, template):
		if type(template) == str:
			template = pathlib.Path(template)

		return template.suffixes == [TEMPLATE_EXTENSION] and not template.is_relative_to(self.__modules)

	def renderable_templates(self):
		if len(self.__renderable_templates) == 0:
			self.__renderable_templates = list(self.env.list_templates(filter_func=self.is_renderable_template))

		return self.__renderable_templates

	def iter_template(self, paths):
		if isinstance(paths, str):
			paths = [paths]

		for p in paths:
			for f in self.__input.rglob(p):
				t = pathlib.Path(f).relative_to(self.__input)
				if self.is_renderable_template(t):
					yield t.as_posix()

	def filtered_templates(self):
		for temp in self.renderable_templates():
			if all(map(lambda x: x(self.__input/temp, self.output_file(temp)), self.__filters)):
				yield temp

	def output_file(self, template_name):
		path = self.__docroot/template_name
		path = path.with_suffix(".html")

		return path

	def request_render(self, template_name):
		if template_name in self.__rendered_templates:
			return

		path = self.output_file(template_name)
		path.parent.mkdir(exist_ok=True, parents=True)

		with open(str(path), 'w') as output:
			self.logger.normal(f"[Render] {template_name}", "blue")

			try:
				template = self.env.get_template(template_name)
				self.__render_stack.append(template_name)
			except jinja2.TemplateNotFound as ex:
				raise RenderError(template_name, ex)

			try:
				rendered_data = template.render(**{'PARAMS': self.__build_spec})
			except (jinja2.TemplateAssertionError, jinja2.exceptions.UndefinedError) as ex:
				raise RenderError(template_name, ex)

			if self.__build_spec.beautify:
				soup = bs(rendered_data, features="html.parser")
				output.write(soup.prettify())
			else:
				soup = htmlmin.minify(rendered_data, remove_empty_space=True)
				output.write(soup)

			self.__rendered_templates.update({template_name})
			self.__render_stack.pop()

	def push_context_data(self, context_name, value):
		if context_name in self.__context_data:
			self.__context_data[context_name].append(value)
		else:
			self.__context_data[context_name] = [value]

	def pop_context_data(self, context_name):
		if context_name in self.__context_data:
			self.__context_data[context_name].pop()
		else:
			raise ValueError(f"Context data does not exist for key {context_name}")

	def set_context_data(self, context_name, value):
		if context_name in self.__context_data:
			self.__context_data[context_name][-1] = value
		else:
			self.__context_data[context_name] = [value]

	def get_context_data(self, context_name):
		if context_name in self.__context_data:
			return self.__context_data[context_name][-1]
		else:
			raise ValueError(f"Context data does not exist for key {context_name}")

	def current_template(self):
		return self.__render_stack[-1]

	def current_template_key(self):
		return self.__render_stack[-1][:-len(TEMPLATE_EXTENSION)]

	def env_data(self, env_key, key=None, default=None, template=None):
		data = self.env.embedded_data
		ctemp = template_to_name(self.current_template()) if template is None else template

		if ctemp in data:
			envs = data[ctemp]
			if env_key in envs:
				env_data = envs[env_key]
				if key is not None:
					if key in env_data:
						return env_data[key]
				else:
					return env_data

		return default

	@property
	def output_dir(self):
		return self.__output

	@property
	def input_dir(self):
		return self.__input

	def clean(self):
		if self.__docroot.exists():
			self.logger.normal(f'- Removing directory: {self.__docroot}')
			shutil.rmtree(self.__docroot)

		if self.__dataroot.exists():
			self.logger.normal(f'- Removing directory: {self.__dataroot}')
			shutil.rmtree(self.__dataroot)

	def __write_data(self):
		self.__dataroot.mkdir(exist_ok=True, parents=True)

		for v in dir(self.env):
			obj = getattr(self.env, v)
			if isinstance(obj, extensions.DataExtensionObject):
				obj.write(self.__dataroot)


	def pre_process(self):
		pass

	def post_process(self):
		pass

	def render(self, build_spec=None):
		if build_spec is None:
			self.__build_spec = self.default_build_flags
		else:
			if isinstance(build_spec, str):
				self.__build_spec = getattr(self, build_spec)
			elif isinstance(build_spec, BuildFlags):
				self.__build_spec = build_spec
			else:
				self.__build_spec = self.default_build_flags

		self.clean()
		self.pre_process()

		for template in self.renderable_templates():
			self.request_render(template)

		self.__rendered_templates = set()
		self.__renderable_templates = []

		self.__write_data()
		self.post_process()
		self.__build_spec = {}

	def package(self):
		shutil.rmtree(self.__build_dir, ignore_errors=True)

		shutil.copytree(self.__output, self.__build_dir, dirs_exist_ok=True)
		shutil.copytree(self.__scripts, self.__build_dir/SCRIPT_DIR, dirs_exist_ok=True)
		shutil.copytree(self.__styles, self.__build_dir/STYLE_DIR, dirs_exist_ok=True)
		shutil.copytree(self.__images, self.__build_dir/IMAGE_DIR, dirs_exist_ok=True)

	@property
	def default_build_flags(self):
		return BuildFlags()

	def import_modules(self):
		"""
		Override this function to import modules which depend upon the project.
		"""
		pass

@dataclasses.dataclass(frozen=True)
class TemplateObject:
	"""
	This generated class uses the current projects information to store information in extending classes.
	It is a frozen data class so general classes can extend it as well as non-frozen dataclasses.
	"""
	project_data: dict[object] = dataclasses.field(default_factory=dict)

	def __post_init__(self):
		self.project_data["template"] = os.path.splitext(Project.current.current_template())[0]

	@property
	def project(self_inner):
		return Project.current

	@property
	def template(self):
		return self.project_data["template"]

__all__ = [
	"Project",
	"proj_fn",
	"proj_type",
	"proj_filter",
	"Markupable",
	"BuildFlags",
	"TemplateObject"
]
