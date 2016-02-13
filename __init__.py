if 'loaded' in locals():
    import imp
    imp.reload(blendergltf)
    from .blendergltf import *
else:
    loaded = True
    from .blendergltf import *