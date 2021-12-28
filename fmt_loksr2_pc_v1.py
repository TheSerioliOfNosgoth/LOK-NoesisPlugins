# ================================================================================
# Legacy of Kain: Soul Reaver 2 (PC)
# .DRM model viewer
# Noesis script by AesirHod, 2021 - last updated: 3 August 2021
# Thanks to Dave, Raq, Gh0stblade, akderebur, Joschka for providing valuable information for this script
# ================================================================================

# Use with .drm files

from inc_noesis import *

def registerNoesisTypes():
	handle = noesis.register("Legacy of Kain: Soul Reaver 2 (PC)", ".drm")
	noesis.setHandlerTypeCheck(handle, bcCheckType)
	noesis.setHandlerLoadModel(handle, bcLoadModel)
	return 1

def bcCheckType(data):
	modelFileName = rapi.getInputName();
	textureFileName = os.path.splitext(modelFileName)[0] + ".vrm";

	bs = NoeBitStream(data)
	file_id = bs.readUInt()

	if file_id != 0x00000008:
		print("Invalid file: " + "\"" + modelFileName + "\"")
		return 0

	if rapi.checkFileExists(textureFileName) == 0:
		print("Missing file: " + "\"" + textureFileName + "\"")

	return 1

def relocate(indexAndOffset, header_list):
	headerIndex = indexAndOffset >> 0x16;
	headerOffset = indexAndOffset & 0x003FFFFF;
	return header_list[headerIndex] + headerOffset

def unpackHalfFloat(half):
	signCheck = (half & 0x00008000) >> 15
	exponant = (half & 0x00007F80) >> 7
	significand = (half & 0x0000007F)

	fraction = 1.0
	for c in range(7):
		current = (((significand << (c + 1)) & 0x000000FF) >> 7)
		fraction += current * (2.0 ** (0 - (c + 1)))

	single = fraction * (2.0 ** (exponant - 127))
	if (signCheck != 0):
		single *= -1.0

	return single

# Read the model data

def bcLoadModel(data, mdlList):
	# noesis.logPopup()

	tex_list = ReadTextures()

	bs = NoeBitStream(data)
	header_list = []

	# Read DRM files

	bs.seek(4)
	entries = bs.readUInt()
	data_start = (entries * 0x0C) + 8
	# 16 byte align
	data_start = (data_start + 0x0000000F) & 0xFFFFFFF0;
	flag = 0

	for a in range(entries):
		# Read the section
		bs.seek(a * 0x0C + 8)
		size1 = bs.readUInt()
		entry_type = bs.readUInt()
		entry_id = bs.readUInt()
        # Not sure what the types are in Soul Reaver 2. Assuming they're all the same.
		entry_type = 0
		# Read the relocations
		bs.seek(data_start)
		numPointers = bs.readUInt()
		header2 = data_start + (numPointers * 4) + 4
		# 16 byte align
		header2 = (header2 + 0x0000000F) & 0xFFFFFFF0;
		# Read the data
		header_list.append(header2)
		data_start = size1 + header2
		# 16 byte align
		data_start = (data_start + 0x0000000F) & 0xFFFFFFF0;
	
	# Soul Reaver 2 doesn't use a gnc_id, but it's always the first one.
	DrawModel(bs, header_list[0], header_list, tex_list, mdlList)
	flag = 1

	if flag == 0:
		print("No meshes found")
		return 0

	return 1

def ReadTextures():
	modelFileName = rapi.getInputName();
	textureFileName = os.path.splitext(modelFileName)[0] + ".vrm";
	data = rapi.loadIntoByteArray(textureFileName)
	bs = NoeBitStream(data)

	tex_list = []

	header_size = 0x20
	num_textures = bs.readUShort()
	data_start = header_size
	
	for a in range(num_textures):
		bs.seek(data_start)
		
		flags1 = bs.readUShort()
		type1 = bs.readUShort()
		width = bs.readUShort()
		height = bs.readUShort()
		size = bs.readUInt()
		flags2 = bs.readUInt()

		 # print("Texture ID = " + hex(flags1))

		data_start += size + 0x10
		
		raw_data = bs.readBytes(size)

		if type1 == 3:
			texture = NoeTexture("Texture_" + str(flags1) + ".dds", width, height, raw_data, noesis.NOESISTEX_RGBA32)
		if type1 == 5:
			texture = NoeTexture("Texture_" + str(flags1) + ".dds", width, height, raw_data, noesis.NOESISTEX_DXT1)
		if type1 == 9:
			texture = NoeTexture("Texture_" + str(flags1) + ".dds", width, height, raw_data, noesis.NOESISTEX_DXT5)

		tex_list.append(texture)

	return tex_list

# Draw one complete model

def DrawModel(bs, header2, header_list, tex_list, mdlList):
	ctx = rapi.rpgCreateContext()

	# For now, just get the first model in the array.
	# Array of offsets
	bs.seek(header2 + 0x0C)
	model_array = relocate(bs.readUInt(), header_list)

	# The first model
	bs.seek(model_array)
	model_data = relocate(bs.readUInt(), header_list)

	bs.seek(model_data + 0x04)
	
	bone_count1 = bs.readUInt()
	bone_count2 = bs.readUInt()
	bone_data = relocate(bs.readUInt(), header_list)
	scaleX = bs.readFloat()
	scaleY = bs.readFloat()
	scaleZ = bs.readFloat()

	# Read skeleton data

	bones = []

	for a in range(bone_count1):
		bs.seek(bone_data + (a * 0x20))

		pos = NoeVec3.fromBytes(bs.readBytes(12))
		bs.seek(12, NOESEEK_REL)
		parent_id = bs.readShort()
		matrix = NoeQuat([0, 0, 0, 1]).toMat43()
		matrix[3] = pos
		if not a:
			matrix *= NoeAngles([90,0,0]).toMat43()

		bones.append(NoeBone(a, "Bone_" + str(a), matrix, None, parent_id))

	bones = rapi.multiplyBones(bones)

	# Read vertex data

	bs.seek(model_data + 0x20)
	vert_count = bs.readUInt()
	vert_start = relocate(bs.readUInt(), header_list)

	bs.seek(model_data + 0x58)
	face_info = relocate(bs.readUInt(), header_list);

	vertices = bytearray(vert_count * 12)
	uvs = bytearray(vert_count * 8)
	normals = bytearray(vert_count * 12)
	bone_idx = bytearray(vert_count * 4)
	weights = bytearray(vert_count * 8)

	bs.seek(vert_start)

	for v in range(vert_count):
		bs.seek(vert_start + (v * 0x10))
		vx = bs.readShort() * scaleX
		vy = bs.readShort() * scaleY
		vz = bs.readShort() * scaleZ

		nx = bs.readByte() / 127
		ny = bs.readByte() / 127
		nz = bs.readByte() / 127
		bs.readByte()								# padding byte

		bone_id = bs.readUShort()
		
		# Convert to correct float value
		uvx = unpackHalfFloat(bs.readUShort())
		uvy = unpackHalfFloat(bs.readUShort())

		if bone_id > (bone_count1-1):
			bs.seek(bone_data + (bone_id * 0x20) + 0x18)
			bone_id = bs.readUShort()
			bone_id2 = bs.readUShort()
			weight1 = bs.readFloat()
			weight2 = 1 - weight1
			struct.pack_into("<HH", bone_idx, v * 4, bone_id, bone_id2)
			struct.pack_into("<ff", weights, v * 8, weight2, weight1)
		else:
			struct.pack_into("<HH", bone_idx, v * 4, bone_id, 0)
			struct.pack_into("<ff", weights, v * 8, 1, 0)

		# Transform vertices to bone position without using rpgSkinPreconstructedVertsToBones

		vertpos = bones[bone_id].getMatrix().transformPoint([vx, vy, vz])
		vx = vertpos[0]
		vy = vertpos[1]
		vz = vertpos[2]
		
		norm = bones[bone_id].getMatrix().transformNormal([nx, ny, nz])
		nx = norm[0]
		ny = norm[1]
		nz = norm[2]

		struct.pack_into("<fff", vertices, v * 12, vx, vy, vz)
		struct.pack_into("<ff", uvs, v*8, uvx, uvy)
		struct.pack_into("<fff", normals, v*12, nx, ny, nz)

	flag = 0
	current_mesh = face_info
	mesh_num = 0

	rapi.rpgBindPositionBuffer(vertices, noesis.RPGEODATA_FLOAT, 12)
	rapi.rpgBindNormalBuffer(normals, noesis.RPGEODATA_FLOAT, 12)
	rapi.rpgBindUV1Buffer(uvs, noesis.RPGEODATA_FLOAT, 8)
	rapi.rpgBindBoneIndexBuffer(bone_idx, noesis.RPGEODATA_USHORT, 4, 2)
	rapi.rpgBindBoneWeightBuffer(weights, noesis.RPGEODATA_FLOAT, 8, 2)

	mat_list = []

	while flag == 0:
		bs.seek(current_mesh)

		face_count = bs.readUShort()
		if face_count == 0:										# no more sub-meshes
			break
		
		misc1 = bs.readUShort()
		tex_id = bs.readUShort() & 0x1FFF						# bits 0-12
		misc3 = bs.readUShort()
		misc4 = bs.readUShort()
		misc5 = bs.readUShort()

		current_mesh = relocate(bs.readUInt(), header_list)		# next face section

		if (misc3 & 0x0800) != 0:
			continue
		
		faces = bs.readBytes(face_count * 2)

		material = NoeMaterial("Material_" + str(mesh_num), "")
		material.setTexture("Texture_" + str(tex_id))
		mat_list.append(material)

		rapi.rpgSetMaterial("Material_" + str(mesh_num))
		rapi.rpgSetName("Mesh_" + str(mesh_num))
		rapi.rpgCommitTriangles(faces, noesis.RPGEODATA_USHORT, face_count, noesis.RPGEO_TRIANGLE)
		mesh_num += 1

	try:
		mdl = rapi.rpgConstructModel()
	except:
		mdl = NoeModel()

	mdl.setModelMaterials(NoeModelMaterials(tex_list, mat_list))
	mdl.setBones(bones)
	mdlList.append(mdl)

	return 1
