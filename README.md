[![Build Status](https://travis-ci.org/Kupoman/blendergltf.svg?branch=master)](https://travis-ci.org/Kupoman/blendergltf)

# Blendergltf

## About

Blendergltf is an addon for Blender that adds the ability to export to the [glTF format](https://github.com/KhronosGroup/glTF).
This addon started its life as part of the [Blender Real TimeEngine addon](https://github.com/Kupoman/BlenderRealtimeEngineAddon)
in order to provide a convenient way of streaming scene data to real time  engines.
As interest has grown in glTF, the glTF exporting code of the Blender Real Time Engine addon was moved into this repository to be used as both a Python module and a Blender addon.

Versions 1.0 and 2.0 of the glTF format are supported. For currently supported extensions, check out the [extension settings](#extensions).

**NOTE**: Version 1.2.0 of blendergltf is deprecating support for glTF 1.0.
The next release of blendergltf will likely remove support for glTF 1.0 entirely.
See [issue #135](https://github.com/Kupoman/blendergltf/issues/135) for more information and discussion.

## Installation

1. Download the blendergltf ZIP file from GitHub:
[stable](https://github.com/Kupoman/blendergltf/archive/master.zip),
[testing](https://github.com/Kupoman/blendergltf/archive/develop.zip),
[releases](https://github.com/Kupoman/blendergltf/releases)

2. Launch Blender, click `File -> User Preferences...`, and click the `Add-ons` tab
at the top of the User Preferences dialog.  Then, click the `Install from file...`
button in the bottom margin of that dialog.  Select your ZIP file to complete
the install.

3. In the left margin there is a `Supported Level` selector, make sure the
`Community` level is selected.  To find the addon quicker, you may need
to enter `gltf` into the search box at the top of the left margin.

4. You should now see `Import-Export: glTF format` as a block in the body of the
preferences dialog.  Put a checkmark on this row to activate it.

5. Finally, click `Save User Settings` to keep the changes.  Note that any other
settings changes you have made to Blender may also be saved.

## Usage

Load a scene you wish to export to glTF, and click `File -> Export -> glTF (.gltf)`.
Some glTF export options will appear in the lower-left margin, and a file dialog
will ask for the location to save the exported file.

## Add-On Settings
### Axis Conversion
#### Up
Up axis of output coordinate system.
#### Forward
Forward axis of output coordinate system.

### Nodes
#### Export Hidden Objects
Export nodes that are not set to visible.
#### Selection Only
Only export nodes that are currently selected.

### Meshes
#### Apply Modifiers
Apply all modifiers to the output mesh data.
When this option is disabled, no modifier data is exported.
#### Interleave Vertex Data
Store data for each vertex contiguously instead of each vertex property (e.g. position) contiguously.
When vertex data is interleaved, all properties share one buffer.
Otherwise, each property is stored in a separate buffer.
This could give a slight performance improvement to vertex processing, but a lot of importers do not handle interleaved data well.
It is not recommended to use this setting unless you are looking for importer bugs.
#### Export Vertex Color Alpha
Export vertex colors with 4 channels instead of 3.
The fourth channel is always filled with a value of 1.0.
This option needs to be enabled when exporting for Facebook.

### Materials
#### Disable Material Export
Export minimum default materials. Useful when using material extensions. Additional maps are always exported when outputting glTF 2.0.
#### Embed Shader Data (glTF 1.0 only)
Embed shader data into the glTF file instead of as a separate file.

### Animations
#### Armatures
* **All Eligible** Export all actions that can be used by an armature
* **Active** Export the active action per armature
#### Objects
* **All Eligible** Export all actions that can be used by a non-armature object
* **Active** Export the active action per non-armature object
#### Shape Keys
* **All Eligible** Export all shape key actions that can be used by an object
* **Active** Export the active shape key action per object

### Images
#### Storage
* **Embed** Embed image data into the glTF file.
* **Reference** Use the same filepath that Blender uses for images.
* **Copy** Copy images to output directory and use a relative reference.
#### sRGB Texture Support (glTF 1.0 only)
Use sRGB texture formats for sRGB textures.
This option will produce invalid glTF since the specification currently does not allow for sRGB texture types.

### Buffers
#### Embed Buffer Data
Embed buffer data into the glTF file.
#### Combine Buffer Data
Combine all buffers into a single buffer.

### Extensions
#### BLENDER_physics (Draft)
Enable the [BLENDER_physics](https://github.com/Kupoman/blendergltf/tree/master/extensions/BLENDER_physics) extension to export rigid body physics data.
#### KHR_lights (Draft)
Enable the [KHR_lights](https://github.com/andreasplesch/glTF/blob/ec6f61d73bcd58d59d4a4ea9ac009f973c693c5f/extensions/Khronos/KHR_lights/README.md) extension to export light data.
#### KHR_materials_common (Draft)
Enable the [KHR_materials_common](https://github.com/KhronosGroup/glTF/tree/master/extensions/Khronos/KHR_materials_common) extension to export Blinn Phong materials.

#### KHR_materials_unlit (Draft)
Enable the [KHR_materials_unlit](https://github.com/KhronosGroup/glTF/pull/1163) extension to export simplified unlit materials.

### Output
#### Copyright
Copyright string to include in output file.
#### Version
The version of the glTF specification to output as.
#### Export as binary
Export to the binary glTF file format (.glb).
#### Profile (glTF 1.0 only)
* **Web** Target WebGL 1.0
* **Desktop** Target OpenGL and GLSL 1.30.
This profile is not explicitly supported by the glTF specification.
#### Pretty-print / indent JSON
Export JSON with indentation and a newline.
#### Prune Unused Resources
Do not export any data-blocks that have no users or references.

## How to Contribute
The most helpful way to contribute right now is to try and use the output of
Blendergltf, and report any issues you find. This will help us identify where work
is still needed, and it will help make the addon more robust. If you want to
 contribute code, there are likely some tasks floating around the issue tracker.
