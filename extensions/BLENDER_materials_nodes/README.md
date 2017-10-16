# BLENDER\_materials\_nodes

## Contributors

* Mitchell Stokes, Blender, <mailto:mogurijin@gmail.com>
* Daniel Stokes, Blender, <mailto:kupomail@gmail.com>
* Juan Linietsky, Godot

## Status

Draft

## Dependencies

Written against glTF 2.0 spec

## Overview

This extension extends materials to include material nodes that match Blender's material nodes.

## glTF Schema Updates

A `BLENDER_materials_nodes` object can be added to the extensions list of a `material`.
This extension object has the following properties:

|   |Type|Description|Required|
|---|----|-----------|--------|
|**nodes**|`array`|A list of `material_node` objects|Yes|

Each `material_node` has a type, input sockets, and output sockets.
The consuming application will need to know how to implement the `material_node` `type`.


**material_node Properties**

|   |Type|Description|Required|
|---|----|-----------|--------|
|**type**|`string`|The Blender type for this node (e.g., `MATERIAL`, `OUTPUT`)|Yes|
|**inputs**|`array`|A list of indices into the inputs array on the extension object|Yes|
|**outputs**|`array`|A list of indices into the outputs array on the extension object|Yes|

Supported material node types:

* TODO (this list is long)

**material_node_socket Properties**

|   |Type|Description|Required|
|---|----|-----------|--------|
|**type**|`string`|The data type of the socket|Yes|
|**name**|`string`|Name for the socket|Yes|
|**value**||Value of the socket which depends on `type` (e.g., `array` of numbers for `RGBA`, node_id for `NODE`)|Yes|

Supported socket types:

* `VALUE` - a scalar value
* `COLOR` - an RGBA color vector
* `NODE` - index to another `material_node`

### JSON Schema

* [material.BLENDER_materials_nodes.schema.json](https://github.com/Kupoman/blendergltf/blob/material_nodes/extensions/BLENDER_materials_nodes/schema/material.BLENDER_materials_nodes.schema.json) (TODO)

## Known Implementations

### Exporters

* blendergltf  ([code](https://github.com/Kupoman/blendergltf/blob/master/blendergltf.py))

### Consumers

* None

## Resources

* [Blender manual page on material nodes](https://docs.blender.org/manual/en/dev/render/blender_render/materials/nodes/introduction.html)
