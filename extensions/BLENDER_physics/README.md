# BLENDER\_physics

## Contributors

* Mitchell Stokes, Blender, <mailto:mogurijin@gmail.com>
* Daniel Stokes, Blender, <mailto:kupomail@gmail.com>
* Steven Vergenz, AltspaceVR, <mailto:steven@altvr.com>

## Status

Draft

## Dependencies

Written against glTF 1.0 and 2.0 specs.
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
|**bounding_box**|`array`|The bounding box dimensions of the node (x, y, z). Note: this is a local bounding box and does not take the node's transform into account.|Yes|
|**radius**|`number`|Radius to use for calculating the physics shape. This is based on the dimensions of the bounding box. Note: not all shapes (e.g., `BOX`) make use of this field.|No, default: `0.0`|
|**height**|`number`|Height to use for calculating the physics shape. This is based on the dimensions of the bounding box. Note: not all shapes (e.g., `BOX`) make use of this field.|No, default: `0.0`|
|**height_axis**|`number`|Specifies which index of the bounding box (i.e., which axis) is the height (assuming the shape has a height)|No, default: `1`|
|**mesh**|`glTF id`|The ID of the mesh to use for `CONVEX_HULL` and `MESH` collision shapes|No, default: `node's mesh` if it exists, otherwise use `BOX` shape|
|**offset_matrix**|`array`|A 4x4 transform matrix applied to the physics shape in addition to the node's transform|No, default: `[ 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0 ]`|
|**offset_rotation**|`array`|A rotation offset (as a quaternion) applied to the physics shape in addition to the node's rotation|No, default: `[0.0, 0.0, 0.0, 1.0]`|
|**offset_scale**|`array`|A non-uniform scale offset applied to the physics shape in addition to the node's scale|No, default: `[1.0, 1.0, 1.0]`|
|**offset_translation**|`array`|A translation offset applied to the physics shape in addition to the node's translation|No, default: `[0.0, 0.0, 0.0]`|

**Collision Shapes**

Below are the allowed values for `collisionShape`:

* `BOX`
* `SPHERE`
* `CAPSULE`
* `CYLINDER`
* `CONE`
* `CONVEX_HULL`
* `MESH`

**Example**

Below are two example nodes with physics information defined.
The first has a `CAPSULE` shape, and the second has a `MESH` shape.
Replace `<glTF id>` with the value appropriate for the spec version.

```javascript
{
    "extensions": {
        "BLENDER_physics": {
            "bounding_box": [
                2.0000009536743164,
                2.0000009536743164,
                4.323975563049316
            ],
            "collisionShape": "CAPSULE",
            "height": 4.323975563049316,
            "height_axis": 2,
            "mass": 1.0,
            "radius": 1.0000004768371582,
            "static": false
        }
    },
    "mesh": 0,
    "name": "Cube",
    "rotation": [
        0.0,
        0.0,
        0.0,
        1.0
    ],
    "scale": [
        1.0,
        1.0,
        1.0
    ],
    "translation": [
        -3.725290298461914e-08,
        -2.9802322387695312e-08,
        1.1619879007339478
    ]
}
```

```javascript
{
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

An optional, scalar gravity value (in m/s/s) can be supplied as part of a `scene`.
If a value is not supplied, the importer should assume -9.8m/s/s.

```javascript
{
    "extensions" {
        "BLENDER_physics": {
            "gravity": -9.8
        }
    },
    "name": "Scene",
    "nodes": [
        ...
    ]
}
```


### JSON Schema

* [node.BLENDER_physics.schema.json](https://github.com/Kupoman/blendergltf/blob/master/extensions/BLENDER_physics/schema/node.BLENDER_physics.schema.json)
* [scene.BLENDER_physics.schema.json](https://github.com/Kupoman/blendergltf/blob/master/extensions/BLENDER_physics/schema/scene.BLENDER_physics.schema.json)

## Known Implementations

### Exporters

* blendergltf  ([code](https://github.com/Kupoman/blendergltf/blob/master/blendergltf.py))

### Consumers

* BlenderPanda ([code](https://github.com/Moguri/BlenderPanda/blob/master/converter.py))

## Resources

None yet
