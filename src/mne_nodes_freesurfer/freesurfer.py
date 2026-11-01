"""FreeSurfer-dependent Python callables exposed to MNE-Nodes.

Use the original MNE callable so subprocess execution imports mne.bem directly
and does not require this GUI plugin to be installed inside WSL.
"""

from mne.bem import make_watershed_bem as watershed_bem

make_watershed_bem = watershed_bem

__all__ = ["make_watershed_bem"]
__all__ += ['watershed_bem']

