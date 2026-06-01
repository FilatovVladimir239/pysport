import base64
import os
import tempfile

import pytest
from openpyxl import load_workbook

try:
    from PIL import Image as PILImage  # noqa: F401

    HAS_PILLOW = True
except ImportError:
    HAS_PILLOW = False

from sportorg.common.signature_images import store_signature_image
from sportorg.models.memory import Race, new_event, race
from trailo_protocols.excel import save_trailo_protocol_excel
from fixtures_preo import setup_preo_group

_MIN_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


def test_race_data_stores_signature_paths():
    new_event([Race()])
    race().data.chief_referee_signature_path = r"C:\sig\chief.png"
    race().data.secretary_signature_path = r"C:\sig\sec.png"
    data = race().to_dict()["data"]
    assert data["chief_referee_signature_path"] == r"C:\sig\chief.png"
    assert data["secretary_signature_path"] == r"C:\sig\sec.png"


def test_store_signature_image_copies_file():
    with tempfile.TemporaryDirectory() as tmp:
        source = os.path.join(tmp, "sign.png")
        with open(source, "wb") as handle:
            handle.write(_MIN_PNG)
        saved = store_signature_image(source, "chief_referee")
        assert os.path.isfile(saved)
        assert saved != source


@pytest.mark.skipif(not HAS_PILLOW, reason="Pillow is required for Excel signature images")
def test_excel_protocol_embeds_signature_images():
    race_dict = setup_preo_group()
    with tempfile.TemporaryDirectory() as tmp:
        chief_path = os.path.join(tmp, "chief.png")
        secretary_path = os.path.join(tmp, "secretary.png")
        for path in (chief_path, secretary_path):
            with open(path, "wb") as handle:
                handle.write(_MIN_PNG)
        race_dict["data"]["chief_referee_signature_path"] = chief_path
        race_dict["data"]["secretary_signature_path"] = secretary_path
        out = os.path.join(tmp, "protocol.xlsx")
        save_trailo_protocol_excel(race_dict, out)
        wb = load_workbook(out)
        assert wb.active._images
