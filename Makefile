test-all: test-style test-unit
	
test-style:
	pylint -r n blendergltf
	pycodestyle blendergltf __init__.py --max-line-length=100

test-unit:
	python -m pytest tests/unit

test-blender-mesh-utils:
	blender \
		tests/blender/meshes.blend \
		--background \
		-noaudio  \
		--python tests/blender/test_mesh_utils.py \
		-- \
		--verbose

test-blender: test-blender-mesh-utils
.PHONY: test-style test-unit test-blender test-all
.DEFAULT: test-all
