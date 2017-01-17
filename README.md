# Blendergltf

## About

Blendergltf is an addon for Blender that adds the ability to export to the [glTF format]
(https://github.com/KhronosGroup/glTF). This addon started its life as part of the [Blender Real Time
Engine addon] (https://github.com/Kupoman/BlenderRealtimeEngineAddon) in order to provide a
convenient way of streaming scene data to real time  engines. As interest has 
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

3. In the left margin there is a `Supported Level` selector, click on the
`Testing` level.  If you have other testing addons installed, you may need
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
### Forward and Up
Together these settings define the axes convention of the glTF output. Conversion
from Blender's Z-up convention to the target convention is handled by inserting
an additional node with an appropriate transform matrix as the root node for a scene.
If no conversion is necessary, no nodes are added.
### Export Hidden Objects
If this setting is enabled, nodes that are not on an active layer in Blender are
excluded from the glTF output.
### Selection Only
If this setting is enabled, nodes that are not part of the current selection in 
Blender are excluded from the glTF output.
### Export Shaders
If this setting is enabled, the GLSL shader for a material will be exported. This
will be a version 130 shader if the profile setting is set to Desktop, and a version
100 shader appropriate for use with WebGL if the profile setting is set to Web.
If this setting is disabled, no shader information will be exported and the
KHR_materials_common extension will be used instead.
### Apply Modifiers
If this setting is enabled, any modifiers will be applied to the mesh data. If the
setting is disabled, no modifier information will be exported.
### Interleave Vertex Data
If this setting is enabled, all of the data for a single vertex will be contiguous
in a mesh's buffer. If it is disabled, all vertex properties of the same type will
be contiguous in a mesh's buffer (e.g. all positions, then all normals, then all
texture coordinates). Usually this setting can be left alone, but some glTF loaders
do not support interleaved vertex data.
### Embed Image Data
If this setting is enabled, image data is embedded into the glTF output as data
URIs with a PNG mime type. If this setting is disabled, the path that Blender
uses for the image is stored in the URI.
### Profile
This setting controls the profile in the asset's profile property in
the glTF output. It also affects if shaders are exported for OpenGL or WebGL.
### Export Physics Settings
If this setting is enabled, a custom extension (BLENDER_physics) is used to write
bullet physics data into the glTF output.
### Export Actions
If this setting is enabled, a custom extension (BLENDER_actions) is used to write
animation data as individual actions instead of writing animation data as one
block of data as described in the glTF specification. Currently, if this setting
is disabled, no animation data is included in the glTF output. Regardless of this
setting, skin data is included in the glTF output.
### Pretty-print / indent JSON
If this setting is enabled, tabs and newlines are inserted into the glTF output
to make it more human readable. This option is useful if you wish to read through
the glTF output. Otherwise, it should be disabled to make the glTF output smaller.

## Recommended Settings
### Three.js
Interleaved vertices support was added in version 83. If you are not using a recent version, you should disable the Interleave Vertex Data option.

## Roadmap

The current development goals, roughly in order of priority, are:
* Improve three.js support (including shaders)
* Improve Cessium support (including cleaning up extension usage)
* Improve BabylonJS support
* Implement an extendable extension system to more easily allow custom extensions
* Improve GUI and user experience of the addon (including documentation)

## How to Contribute
The most helpful way to contribute right now is to try and use the output of 
Blendergltf, and report any issues you find. This will help us identify where work 
is still needed, and it will help make the addon more robust. If you want to
 contribute code, there are likely some tasks floating around the issue tracker. 
If writing documentation is more your thing, we have some undocumented glTF 
extensions.

