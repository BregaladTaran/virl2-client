#
# This file is part of CML 2
#
# Copyright 2021 Cisco Systems Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

"""Tests for importing and exporting topology files."""

import pytest
try:
    import yaml
except:
    pass

from virl2_client import ClientLibrary


TEST_TOPOLOGIES = ["mixed-0.0.1.yaml", "mixed-0.0.4.yaml", "mixed-0.0.5.yaml"]

TOPOLOGY_ID_KEYS = [
    "id",
    "lab_id",
    "node",
    "node_a",
    "node_b",
    "interface_a",
    "interface_b",
]


# TODO: also import .virl topology


@pytest.mark.integration
@pytest.mark.nomock
@pytest.mark.parametrize(argnames="topology", argvalues=TEST_TOPOLOGIES)
def test_import_export_yaml(
    client_library_session: ClientLibrary,
    topology,
    change_test_dir,
    cleanup_test_labs,
    tmpdir,
):
    """Use the API to import a topology from YAML file, export it,
    then import it back and compare with the initial import.
    """

    # Import lab from test data YAML file
    reimported_lab_title = "export_import_test.yaml"
    topology_file_path = f"test_data/{topology}"
    topology_lab_data = yaml.safe_load(open(topology_file_path))

    imported_lab = client_library_session.import_lab_from_path(topology_file_path)

    # Export the lab we just imported, save to YAML file
    exported_lab_yaml = imported_lab.download()
    exported_lab_data = yaml.safe_load(exported_lab_yaml)

    exported_file_path = tmpdir.mkdir("yaml").join(reimported_lab_title)
    exported_file_path.write(exported_lab_yaml)

    # Import the lab from the exported YAML file
    reimported_lab = client_library_session.import_lab_from_path(exported_file_path)

    # Get the topology data for each lab
    url = (
        client_library_session._context.base_url
        + f"labs/{imported_lab._lab_id}/topology"
    )
    response = client_library_session._context.session.get(url)
    response.raise_for_status()
    imported_lab_data = response.json()

    url = (
        client_library_session._context.base_url
        + f"labs/{reimported_lab._lab_id}/topology"
    )
    response = client_library_session._context.session.get(url)
    response.raise_for_status()
    reimported_lab_data = response.json()

    # Compare the initial import with the reimport
    for item in ["lab_description", "lab_owner"]:
        assert imported_lab_data[item] == reimported_lab_data[item]

    lab_notes = imported_lab_data["lab_notes"]
    if not lab_notes:
        # If the lab had no notes, the reimport should be empty as well.
        assert lab_notes == reimported_lab_data["lab_notes"]
    else:
        # Import warnings are appended to lab notes, if there are any the re-import should have them twice
        # We don't know if they're import warnings or actual notes, so do nothing
        pass

    compare_structures(imported_lab_data, reimported_lab_data, False)
    compare_structures(imported_lab_data, reimported_lab_data, True)

    if "0.0.1" in topology:
        return

    for lab in [imported_lab, reimported_lab]:
        node = lab.get_node_by_label("iosv-0")
        assert node.node_definition == "iosv"
        assert sorted(node.tags()) == ["core", "test_tag"]
        assert node.cpu_limit == 50
        assert node.ram == 2048
        # node definition disallows setting these; here
        # they are 0 instead of None as in the backend
        assert node.cpus == 0
        assert node.boot_disk_size == 0
        assert node.data_volume == 0

        node = lab.get_node_by_label("lxc-0")
        assert node.node_definition == "alpine"
        assert sorted(node.tags()) == ["test_tag"]
        assert node.cpu_limit == 80
        assert node.ram == 3072
        assert node.cpus == 6
        assert node.boot_disk_size == 30
        assert node.data_volume == 10


def compare_structures(original: dict, compared: dict, data: bool = False):
    # Match all IDs for consistency, they are autogenerated on import
    id_map = {}
    # Compare individual topology items
    for item in ["nodes", "interfaces", "links"]:
        # item order should be preserved
        for original_item, compared_item in zip(original[item], compared[item]):
            if data:
                original_data = original_item["data"]
                compared_data = compared_item["data"]
            else:
                original_data = original_item
                compared_data = compared_item
            for key in original_data:
                if key in TOPOLOGY_ID_KEYS:
                    if original_data[key] in id_map:
                        assert id_map[original_data[key]] == compared_data[key]
                    else:
                        id_map[original_data[key]] = compared_data[key]
                elif key == "configuration":
                    # config gets stripped at some point
                    assert original_data[key].strip() == compared_data[key]
                elif key != "data":
                    assert original_data[key] == compared_data[key]
