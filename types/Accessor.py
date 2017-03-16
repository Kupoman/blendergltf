import struct, math

class Accessor:
	__slots__ = (
		"name",
		"buffer",
		"buffer_view",
		"byte_offset",
		"byte_stride",
		"component_type",
		"count",
		"min",
		"max",
		"data_type",
		"type_size",
		"_ctype",
		"_ctype_size",
		"_buffer_data",
		)

	def __init__(self,
				 name,
				 buffer,
				 buffer_view,
				 byte_offset,
				 byte_stride,
				 component_type,
				 count,
				 data_type):

		from .Buffer import Buffer

		self.name = name
		self.buffer = buffer
		self.buffer_view = buffer_view
		self.byte_offset = byte_offset
		self.byte_stride = byte_stride
		self.component_type = component_type
		self.count = count
		self.min = [math.inf for i in range(16)]
		self.max = [0 for i in range(16)]
		self.data_type = data_type

		if self.data_type == Buffer.MAT4:
			self.type_size = 16
		elif self.data_type == Buffer.VEC4:
			self.type_size = 4
		elif self.data_type == Buffer.VEC3:
			self.type_size = 3
		elif self.data_type == Buffer.VEC2:
			self.type_size = 2
		else:
			self.type_size = 1

		if component_type == Buffer.BYTE:
			self._ctype = '<b'
		elif component_type == Buffer.UNSIGNED_BYTE:
			self._ctype = '<B'
		elif component_type == Buffer.SHORT:
			self._ctype = '<h'
		elif component_type == Buffer.UNSIGNED_SHORT:
			self._ctype = '<H'
		elif component_type == Buffer.INT:
			self._ctype = '<i'
		elif component_type == Buffer.UNSIGNED_INT:
			self._ctype = '<I'
		elif component_type == Buffer.FLOAT:
			self._ctype = '<f'
		else:
			raise ValueError("Bad component type")

		self._ctype_size = struct.calcsize(self._ctype)
		self._buffer_data = self.buffer.get_buffer_data(self.buffer_view)

	def __len__(self):
		return self.count

	def __getitem__(self, idx):
		if not isinstance(idx, int):
			raise TypeError("Expected an integer index")

		ptr = (
			(
				(idx % self.type_size)
				* self._ctype_size + idx // self.type_size * self.byte_stride
			) + self.byte_offset
		)

		return struct.unpack_from(self._ctype, self._buffer_data, ptr)[0]

	def __setitem__(self, idx, value):
		if not isinstance(idx, int):
			raise TypeError("Expected an integer index")

		i = idx % self.type_size
		self.min[i] = value if value < self.min[i] else self.min[i]
		self.max[i] = value if value > self.max[i] else self.max[i]

		ptr = (
			(i * self._ctype_size + idx // self.type_size * self.byte_stride)
			+ self.byte_offset
		)

		struct.pack_into(self._ctype, self._buffer_data, ptr, value)
