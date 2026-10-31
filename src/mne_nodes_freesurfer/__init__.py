"""FreeSurfer command and MNE function plugin registration."""

from pathlib import Path

PLUGIN_NAME = "freesurfer"
CONFIG_PATH = Path(__file__).parent / "freesurfer_config.json"
SCRIPT_PATH = Path(__file__).parent / "freesurfer.py"
