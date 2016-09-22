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
extensions as well as no documentation on the user interface.

