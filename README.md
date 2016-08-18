# blendergltf

### Installation

In your Blender install folder, look for an existing subfolder with Blender's
version number.  Under that there should be a folder `scripts`, and under
that `addons`.  Create a new subfolder inside `addons` called `blendergltf`.

For example, for Blender version 2.77a, you would create this folder:

```
{blender install}/2.77/scripts/addons/blendergltf
```

Copy all of the files and folders from this repository, except for `.git` and
`.gitignore`, into this new `blendergltf` folder.  You may need to restart
Blender or click the button in User Preferences to refresh the list of addons.

Next, you will need to enable the new addon.  Skip ahead to `Enable blendergltf`.

### Non-administrative installation

If your account does not have permission to write new files into the Blender
installation folder itself, there is an alternate method you can use.  Create
a `blendergltf` folder in your own user folder.  Copy all of the files from
this repository, except for `.git` and `.gitignore`, into this new
`blendergltf` folder.  Then, create a ZIP file that includes `blendergltf` as
the top-level folder in the ZIP, with all the files under that.  Launch Blender,
click `File -> User Preferences...`, and click the `Install from file...`
button in the bottom margin of that dialog.  Select your ZIP file and install
it.  This will copy the files to a user-writable location.

Next, you will need to enable the new addon.

### Enable blendergltf

Launch Blender, and click `File -> User Preferences...` to bring up the preferences
dialog.  Click the `Add-ons` tab at the top of this dialog.  In the left margin
there is a `Supported Level` selector, click on the `Testing` level.  If you have
other testing addons installed, you may need to enter `gltf` into the search box
at the top of the left margin.

You should now see `Import-Export: glTF format` as a block in the body of the
preferences dialog.  Put a checkmark on this row to activate it.

Finally, click `Save User Settings` to keep the changes.  Note that any other
settings changes you have made to Blender may also be saved.

## Usage

Load a scene you wish to export to glTF, and click `File -> Export -> glTF (.gltf)`.
Some glTF export options will appear in the lower-left margin, and a file dialog
will ask for the location to save the exported file.

