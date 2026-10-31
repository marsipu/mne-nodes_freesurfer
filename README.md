# FreeSurfer nodes for MNE-Nodes

This plugin owns the FreeSurfer node definitions:

- `recon-all`: an executable command node requiring a BIDS `anat` image and
  outputting the reconstructed `subject`.
- `make_watershed_bem`: the original `mne.bem.make_watershed_bem` callable,
  marked `uses_freesurfer` for isolated native/WSL execution.

Requires a version of MNE-Nodes supporting `command`, `command_args` and
`uses_freesurfer` metadata.

## Load the plugin

For editable development, in your MNE-Nodes environment:

```powershell
python -m pip install -e .
```

MNE-Nodes discovers and enables newly installed plugins at startup.
Use **Plugins > Manage Plugins** to refresh discovery or enable/disable `freesurfer`.
Alternatively, without installing, use **Plugins > Load Plugin from Path**
and select [freesurfer_config.json](src/mne_nodes_freesurfer/freesurfer_config.json).
Node registration is saved with the project; disabled plugins remain disabled.

## FreeSurfer setup

Use **BIDS > FreeSurfer setup...** in MNE-Nodes for installation instructions and
environment discovery. FreeSurfer is a separate system dependency and requires
its own license. On Windows it runs inside WSL. Python calls also require MNE
and nibabel inside WSL; this plugin need not be installed there.

The shared subprocess runner, automatic discovery and Windows path translation
belong to MNE-Nodes, not this plugin. Normally no executable paths are needed:
the WSL terminal environment is used first, with installation discovery as a
fallback.

Select a T1 image in the input widget's `anat` tab and connect the input node's
`anat` port to `recon-all`. The image path is passed to `-i`, and its BIDS label
determines the FreeSurfer subject name (`sub-01` for BIDS subject `01`).
No existing FreeSurfer subject is needed, and there is no `subject` input.
Connect the output `subject` to downstream
nodes such as `make_watershed_bem`.
`recon-all` modifies that subject and can take hours; do not use it as an
installation test. The former `t1` path parameter is replaced by the `anat` input.
Command definitions and argument mappings are edited in the plugin JSON.

## Tests

```powershell
python -m pytest tests
python -m build
```

Plugin tests verify registration, metadata, persistence and generated pipeline
routing without running a reconstruction or requiring FreeSurfer. MNE-Nodes'
runner tests cover subprocess behavior, with an opt-in real watershed test.
