test-all: test-style test-unit
	
test-style:
	pylint -r n blendergltf
	pycodestyle blendergltf __init__.py --max-line-length=100

test-unit:
	python -m pytest tests/unit

test-blender-%: tests/blender/%.py
	blender --background -noaudio --python $^ -- --verbose

test-blender: $(addprefix test-blender-,$(basename $(notdir $(wildcard tests/blender/*.py))))

.PHONY: test-style test-unit test-blender test-all
.DEFAULT: test-all
