import os

class UndefinedDocument(Exception):
	def __init__(self, fname, position):
		super().__init__(
			f'Document undefined at line: {position[0]} @ {os.path.relpath(fname)}')

class RedefinedDocument(Exception):
	def __init__(self, fname, position):
		super().__init__(
			f"Document already defined. Ignoring redefinition. Line {position[0]} @ {os.path.relpath(fname)}")

class MismatchedTags(Exception):
	def __init__(self, stag, sname, spos, etag, ename, epos):
		super().__init__(f"""Mismatched tag ({etag}) at line {epos[0]} @ {os.path.relpath(ename)} with start tag ({stag}) at line {spos[0]} @ {os.path.relpath(sname)}""")
