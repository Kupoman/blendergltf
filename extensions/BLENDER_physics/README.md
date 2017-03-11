# BLENDER\_physics

## Contributors

* Mitchell Stokes, Blender, <mailto:mogurijin@gmail.com>
* Daniel Stokes, Blender, <mailto:kupomail@gmail.com>
* Steven Vergenz, AltspaceVR, <mailto:steven@altvr.com>

## Status

Draft

## Dependencies

Written against the glTF 2.0 spec.

## Overview

This extension describes a set of common physical attributes that can be assigned to glTF nodes for consumption by rigid body physics simulators. This includes intrinsic properties like mass, as well as some of the more common cheats, like primitive collision meshes.

## glTF Schema Updates

### Node physics properties

This extension adds an optional `BLENDER_physics` property to a glTF node's `extensions` object. This property is an object with some or all of the following properties:

| Name   | Type   | Default | Description      |
|--------|--------|---------|------------------|
| `mass` | number | `1` | The mass of the object, in kilograms.
| `static` | boolean | `true` | Whether or not an object is meant to be permanently stationary.
| `layers` | integer | `1` | A bit field describing membership in arbitrary physics "layers". Typically objects will only collide with other objects that share at least one layer, but ultimately the interpretation of layers is up to the consumer application. This extension defines 16 layers, each corresponding with a bit in a 16-bit integer, which are all `OR`'d together. A `1` in a position indicates membership. For example, if an object is a member of layers 0, 1, and 4, this field would contain the value `19` (`2^0 | 2^1 | 2^4 == 0x1 | 0x2 | 0x10 == 0x13 == 19`).
| `shape` | string | `"box"` | The shape approximation used for this object. Must be one of `box`, `sphere`, `capsule`, `cylinder`, or `mesh`.
| `dimensions` | array[3] | `[1,1,1]` | The width (x), height (y), and depth (z) of a collision box.
| `radius` | number | `1` | The radius of a collision sphere, cylinder, or capsule.
| `height` | number | `1` | The height of a collision cylinder or capsule. Cylinder and capsule colliders are oriented so their long axis is along the node's local Y axis.
| `mesh` | integer | `0` | The index of the mesh used for collision for this object.
| `convex` | boolean | `true` | Whether or not a collision mesh should be approximated to a convex hull, or used as-is.

**Example 1:** Adding rigid body physics properties to a node

```json
"nodes": [{
	"name": "lamp",
	"mesh": 0,
	"extensions": {
		"BLENDER_physics": {
			"mass": 4.65,
			"static": true,
			"layers": 1,
			"shape": "cylinder",
			"height": 1.8,
			"radius": 0.24
		}
	}
}]
```
### JSON Schema

TODO: Links to the JSON schema for the new extension properties.

## Known Implementations

* blendergltf

## Resources

* TODO: Resources, if any.
