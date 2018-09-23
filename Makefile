test-ci: test-style test-unit

test-style:
	pylint -r n blendergltf
	pycodestyle blendergltf --max-line-length=100

test-unit:
	python -m pytest tests/unit

test-integration:
	python -m pytest -v tests/integration

test-integration-update:
	python -m pytest -v --update tests/integration

test-blender-mesh-utils:
	blender \
		tests/integration/sources/meshes.blend \
		--background \
		-noaudio  \
		--python tests/blender/test_mesh_utils.py \
		-- \
		--verbose

test-blender-mesh-utils-normals:
	blender \
		tests/integration/sources/normals.blend \
		--background \
		-noaudio  \
		--python tests/blender/test_mesh_utils_normals.py \
		-- \
		--verbose

test-blender: test-blender-mesh-utils
.PHONY: test-style test-unit test-integration test-integration-update test-blender test-ci
.DEFAULT: test-ci
