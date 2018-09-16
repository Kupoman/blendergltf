import glob
import imp
import importlib
import os.path

FILES = [
    os.path.basename(f)[:-3]
    for f in glob.glob(os.path.dirname(__file__) + '/*.py')
    if os.path.isfile(f)
]
MODULES = [f for f in FILES if not f.startswith('_')]

__all__ = []
for module in MODULES:
    module = importlib.import_module('.'+module, __name__)
    if '_IMPORTED' in locals():
        imp.reload(module)
    for attr in [getattr(module, attr) for attr in dir(module)]:
        if hasattr(attr, 'ext_meta'):
            __all__.append(attr)

if '_IMPORTED' not in locals():
    _IMPORTED = True
