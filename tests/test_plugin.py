"""Plugin contracts that never execute FreeSurfer commands."""

import json
from copy import deepcopy
from importlib.metadata import distribution

import pytest
from mne_bids import BIDSPath, get_bids_path_from_fname
from mne_nodes.backend.code_generation import CodeGenerator
from mne_nodes.backend.controller import Controller, default_config
from mne_nodes.backend.execution import build_command
from mne_nodes.backend.settings import Settings
from mne_nodes.gui.node.function_node import CommandNode
from mne_nodes.gui.node.node_viewer import NodeViewer
from mne_nodes.gui.widget_registry import widget_registry
from qtpy.QtWidgets import QApplication

import mne_nodes_freesurfer as plugin


@pytest.fixture(params=["module", "path", "entry_point"])
def controller(tmp_path, monkeypatch, qtbot, request):
    widget_registry().unregister("viewer")
    monkeypatch.setattr("mne_nodes.backend.controller.get_plugin_entry_points", list)
    monkeypatch.setenv("MNENODES_SETTINGS_DIR", str(tmp_path / "settings"))
    settings = Settings()
    settings.set("first_start", False)
    bids_root = tmp_path / "bids"
    bids_root.mkdir()
    (bids_root / "dataset_description.json").write_text(
        json.dumps({"Name": "Plugin tests", "BIDSVersion": "1.9.0"}), encoding="utf-8"
    )
    settings.set("bids_root", bids_root)
    config_path = tmp_path / "pipeline.json"
    config_path.write_text(
        json.dumps({**deepcopy(default_config), "name": "Plugin tests"}),
        encoding="utf-8",
    )
    ct = Controller(config_path=config_path, settings=settings)
    if request.param == "module":
        ct.load_plugin_module(plugin)
    elif request.param == "path":
        ct.load_plugin_path(plugin.CONFIG_PATH)
    else:
        ct.load_plugin_entry_point("mne-nodes_freesurfer", "freesurfer")
    yield ct
    widget_registry().unregister("viewer")


def test_registration_and_packaged_resources():
    entry = next(
        entry
        for entry in distribution("mne-nodes_freesurfer").entry_points
        if entry.group == "mne_nodes.plugins" and entry.name == "freesurfer"
    )
    assert entry.load() is plugin
    assert plugin.SCRIPT_PATH.is_file()
    metadata = json.loads(plugin.CONFIG_PATH.read_text(encoding="utf-8"))
    assert set(metadata) == {"recon-all", "make_watershed_bem"}
    assert all(item["uses_freesurfer"] for item in metadata.values())
    assert build_command(
        metadata["recon-all"],
        {"subject": "sample", "anat": None, "all": True, "extra_args": []},
    ) == ["recon-all", "-s", "sample", "-all"]


def test_python_callable_requires_only_mne_in_child(controller):
    import mne

    assert controller.plugins["freesurfer"].make_watershed_bem is (
        mne.bem.make_watershed_bem
    )
    assert controller.get_function_meta("make_watershed_bem")["plugin"] == "freesurfer"


def test_command_node_persistence_and_generated_routing(qtbot, controller, monkeypatch):
    viewer = NodeViewer(controller)
    qtbot.addWidget(viewer)
    node = viewer.add_function_node("recon-all")
    assert isinstance(node, CommandNode)
    saved = viewer.to_dict()
    viewer.from_dict(saved)
    node = viewer.function_nodes["recon-all"]
    assert isinstance(node, CommandNode)
    controller.set("selected_inputs", {"anat": ["sub-01_T1w.nii.gz"]})
    monkeypatch.setattr(controller, "get_datatypes", lambda: ["anat"])
    monkeypatch.setattr(CodeGenerator, "_build_header", lambda *args: "")
    description, _ = node.get_description()
    description["inputs"] = {"anat": ["Input"]}
    code = CodeGenerator(controller, {"file": [description]}).code
    assert "ct.execute_external('recon-all'," in code
    compile(code, "<plugin-pipeline>", "exec")
    viewer.clear()
    QApplication.processEvents()


def test_anatomy_input_and_subject_output(qtbot, controller, monkeypatch):
    """A selected BIDS T1 image is sufficient to reconstruct a new subject."""
    anatomy = BIDSPath(
        root=controller.bids_root,
        subject="01",
        datatype="anat",
        suffix="T1w",
        extension=".nii.gz",
    )
    anatomy.directory.mkdir(parents=True)
    anatomy.fpath.touch()
    viewer = NodeViewer(controller)
    qtbot.addWidget(viewer)
    controller.input_selection_changed([anatomy.basename], "anat")
    assert controller.get_all_datatype_items()["anat"] == [anatomy.basename]
    tabs = viewer.input_node.input_widget.tab_widget
    assert "anat" in [tabs.tabText(index) for index in range(tabs.count())]
    assert controller.load_anat(anatomy) == anatomy.fpath
    assert controller.load_anat([anatomy]) == [anatomy.fpath]
    with pytest.raises(FileNotFoundError, match="Anatomy image is missing"):
        controller.load_anat(anatomy.copy().update(subject="missing"))

    node = viewer.add_function_node("recon-all")
    assert [port.name for port in node.inputs] == ["anat"]
    assert not node.input(port_name="anat").optional
    assert [port.name for port in node.outputs] == ["subject"]
    source = viewer.input_node.output(port_name="anat")
    target = node.input(port_name="anat")
    source.connect_to(target)
    assert source.connected(target)
    downstream = viewer.add_function_node("make_watershed_bem")
    output = node.output(port_name="subject")
    subject_input = downstream.input(port_name="subject")
    output.connect_to(subject_input)
    assert output.connected(subject_input)
    description, _ = node.get_description()
    monkeypatch.setattr(CodeGenerator, "_build_header", lambda *args: "")
    code = CodeGenerator(controller, {"file": [description]}).code
    assert "anat = ct.load_anat(bp)" in code
    assert "subject = ct.execute_external('recon-all'," in code
    assert "load_recording_subject" not in code
    commands = []
    monkeypatch.setattr(
        "mne_nodes.backend.controller.run_freesurfer_subprocess",
        lambda argv, *args, **kwargs: commands.append(argv),
    )
    monkeypatch.setattr(controller, "freesurfer_runtime", lambda: None)
    monkeypatch.setattr(
        controller, "ensure_subjects_dir", lambda **kwargs: anatomy.directory
    )
    namespace = {"ct": controller, "get_bids_path_from_fname": get_bids_path_from_fname}
    exec(compile(code, "<anatomy-pipeline>", "exec"), namespace)  # noqa: S102
    assert namespace["subject"] == "sub-01"
    assert commands == [["recon-all", "-s", "sub-01", "-i", str(anatomy.fpath), "-all"]]
    with pytest.raises(ValueError, match="requires 'anat'"):
        controller.execute_external("recon-all", subject="existing")
    with pytest.raises(ValueError, match="derives 'subject' from 'anat'"):
        controller.execute_external(
            "recon-all", anat=anatomy.fpath, subject="custom-subject"
        )
    with pytest.raises(ValueError, match="requires 'anat'"):
        controller.execute_external("recon-all")
    viewer.clear()
    QApplication.processEvents()


def test_plugin_registration_survives_reload(controller):
    controller.flush()
    reloaded = Controller(
        config_path=controller.config_path, settings=controller.settings
    )
    assert reloaded.get_function_meta("recon-all")["plugin"] == "freesurfer"
    assert reloaded.plugins["freesurfer"].make_watershed_bem.__module__ == "mne.bem"
