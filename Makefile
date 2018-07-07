test-style:
	pylint -r n blendergltf
	pycodestyle blendergltf __init__.py

test-unit:
	python -m pytest tests/unit

test-all: test-style test-unit

.PHONY: test-style test-unit test-all
