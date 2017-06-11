# Blendergltf

## About

Blendergltf is an addon for Blender that adds the ability to export to the
[glTF format](https://github.com/KhronosGroup/glTF). This addon started its life as part of the
[Blender Real TimeEngine addon](https://github.com/Kupoman/BlenderRealtimeEngineAddon)
in order to provide a convenient way of streaming scene data to real time  engines. As interest has
grown in glTF, the glTF exporting code of the Blender Real Time Engine addon was moved
into this repository to be used as both a Python module and a Blender addon. While
Blendergltf has support for most of the glTF 1.0 spec, it is not yet well tested with
the various engines and importers that can consume glTF.

## Installation

1. Download the [blendergltf ZIP file from GitHub](https://github.com/Kupoman/blendergltf/archive/master.zip).

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
Axis conversion is handled by adding a new root node with the appropriate transformation.
#### Forward
Forward axis of output coordinate system.
Axis conversion is handled by adding a new root node with the appropriate transformation.

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
This is an advanced option that can be useful for some importers.

### Shaders
#### Storage
* **None** Use the KHR_material_common extension instead of a shader.
* **External** Save shaders to the output directory.
* **Embed** Embed shader data into the glTF file.

### Images
#### Storage
* **Copy** Embed image data into the glTF file.
* **Reference** Use the same filepath that Blender uses for images.
* **Embed** Copy images to output directory and use a relative reference.
#### sRGB Texture Support
Use sRGB texture formats for sRGB textures.
This option will produce invalid glTF since the specification currently does not allow for sRGB texture types.

### Buffers
#### Embed Buffer Data
Embed buffer data into the glTF file.
#### Combine Buffer Data
Combine all buffers into a single buffer.

### Extensions
#### Export Physics Settings
Enable support for the [BLENDER_physics](https://github.com/Kupoman/blendergltf/tree/master/extensions/BLENDER_physics) extension.
This extension adds Bullet physics data to glTF nodes.

### Output
#### Profile
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
If writing documentation is more your thing, we have some undocumented glTF
extensions.

