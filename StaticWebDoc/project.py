from dataclasses import dataclass
from dataclasses import InitVar
import os
from pathlib import Path

DEFAULT_DOC_PATH = './doc'
DEFAULT_SCRIPTS_PATH = './scripts'
DEFAULT_STYLE_PATH = './style'
DEFAULT_BUILD_PATH = './build'

PROJECT = None

@dataclass(frozen=True)
class Project:
	doc: str | None = None
	scripts: str | None = None
	style: str | None  = None
	outdir: str | None = None
	doc_files: InitVar[[str]] = []
	scripts_files: InitVar[[str]] = []
	style_files: InitVar[[str]] = []

	def __post_init__(self, doc_files, scripts_files, style_files):
		if self.doc is None:
			object.__setattr__(self, "doc", os.path.abspath(DEFAULT_DOC_PATH))
		else:
			object.__setattr__(self, "doc", os.path.abspath(os.path.join(os.curdir, self.root)))

		if self.scripts is None:
			object.__setattr__(self, "scripts", os.path.abspath(DEFAULT_SCRIPTS_PATH))
		else:
			object.__setattr__(self, "scripts", os.path.abspath(os.path.join(os.curdir, self.scripts)))

		if self.style is None:
			object.__setattr__(self, "style", os.path.abspath(DEFAULT_STYLE_PATH))
		else:
			object.__setattr__(self, "style", os.path.abspath(os.path.join(os.curdir, self.style)))


		doc_path = Path(self.doc)
		scripts_path = Path(self.scripts)
		style_path = Path(self.style)

		for f in doc_path.glob("**/*.html"):
			doc_files.append(f)

		for f in scripts_path.glob("**/*.js"):
			scripts_files.append(f)

		for f in style_path.glob("**/*.css"):
			style_files.append(f)

		global PROJECT
		PROJECT = self

	def get_doc_path(self, fpath):
		return os.path.join(self.doc, fpath)


	def debug_print(self):
		print(f'{"-"*20} Project Specification {"-"*20}')
		print(f'doc: {os.path.relpath(self.doc)}')
		print(f'scripts: {os.path.relpath(self.scripts)}')
		print(f'styles: {os.path.relpath(self.style)}')

		print(f'{"-"*20} Document Files {"-"*20}')
		for f in self.doc_files:
			print(f'- {os.path.relpath(f)}')

		print(f'{"-"*20} Scripts Files {"-"*20}')
		for f in self.scripts_files:
			print(f'- {os.path.relpath(f)}')

		print(f'{"-"*20} Style Files {"-"*20}')
		for f in self.style_files:
			print(f'- {os.path.relpath(f)}')
