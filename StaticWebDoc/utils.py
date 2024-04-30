class ListGuard:
	def __init__(self, l: list):
		self.__v = l

	def __iter__(self):
		return iter(self.__v)

	def __getitem__(self, i):
		return self.__v[i]

	def __setitem__(self, i, _):
		raise ValueError("Cannot set item for List Object.")

	def __len__(self):
		return len(self.__v)

	def __str__(self):
		return str(f"Guarded{self.__v}")