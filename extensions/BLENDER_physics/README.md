# BLENDER\_physics

## Contributors

* Mitchell Stokes, Blender, <mailto:mogurijin@gmail.com>
* Daniel Stokes, Blender, <mailto:kupomail@gmail.com>
* Steven Vergenz, AltspaceVR, <mailto:steven@altvr.com>

## Status

Draft

## Dependencies

Written against the glTF 1.0 and 2.0 draftspec.
The only difference for this extension for 1.0 vs 2.0 is the `mesh-id`.

## Overview

This extension extends nodes to include information necessary to construct rigid body objects for a physics engine (e.g., [Bullet](https://bulletphysics.org/)).

## glTF Schema Updates

A `BLENDER_physics` object is added to the extensions list of any `node` that should participate in the physics simulation.
The properties available are listed in the table below.

**Properties**

|   |Type|Description|Required|
|---|----|-----------|--------|
|**collisionShape**|`string`|The shape a physics simulation should use to represent the node|No, default: `BOX`|
|**mass**|`number`|The 'weight', irrespective of gravity, of the node|No, default: `1.0`|
|**static**|`boolean`|Specifies if the Node should not be moved by physics simulations|No, default: `false`|
|**dimensions**|`array`|The bounding box dimensions of the node (x, y, z)|Yes|
|**mesh**|`glTF id`|The ID of the mesh to use for `CONVEX_HULL` and `MESH` collision shapes|No, default: `node's mesh` if it exists, otherwise use `BOX` shape|

**Collision Shapes**

Below are the allowed values for `collisionShape` along with examples of how to extract shape information from the dimensions (assuming Z-Up).

* `BOX` - use dimensions as supplied
* `SPHERE` - radius is `max(dimensions) / 2.0`
* `CAPSULE` - radius is `max(dimensions[0], dimensions[1]) / 2.0`, height is `dimensions[2] - 2.0 * radius`
* `CYLINDER` - radius is `max(dimensions[0], dimensions[1]) / 2.0`, height is `dimensions[2]`
* `CONE` - radius is `max(dimensions[0], dimensions[1]) / 2.0`, height is `dimensions[2]`
* `CONVEX_HULL` - use mesh
* `MESH` - use mesh

**Example**

Below is an example `node` with physics information defined.
Replace `<glTF id>` with the value appropriate for the spec version.

```javascript
{
    "children": [],
    "extensions": {
        "BLENDER_physics": {
            "collisionShape": "MESH",
            "dimensions": [
                2.0000009536743164,
                2.0000009536743164,
                2.0
            ],
            "mass": 1.0,
            "mesh": <glTF id>,
            "static": false
        }
    },
    "matrix": [
        1.0,
        0.0,
        0.0,
        0.0,
        0.0,
        1.0,
        0.0,
        0.0,
        0.0,
        0.0,
        1.0,
        0.0,
        0.0,
        0.0,
        0.0,
        1.0
    ],
    "meshes": [
        <glTF id>
    ],
    "name": "Cube"
}
```


### JSON Schema

* [node.BLENDER_physics.schema.json](https://github.com/Kupoman/blendergltf/blob/master/extensions/BLENDER_physics/schema/node.BLENDER_physics.schema.json)

## Known Implementations

### Exporters

* blendergltf  ([code](https://github.com/Kupoman/blendergltf/blob/master/blendergltf.py))

### Consumers

* BlenderPanda ([code](https://github.com/Moguri/BlenderPanda/blob/master/converter.py))

## Resources

None yet
