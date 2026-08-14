"""main_gui.py 配置写入白名单与 API Key 打码测试。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from instance import BotInstance
from main_gui import _mask_api_key, _apply_config_fields, _EDITABLE_FIELDS


def _make_inst(tmp_path, api_key="sk-real-secret-1234"):
    folder = tmp_path / "inst"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / ".env").write_text(f"DEEPSEEK_API_KEY={api_key}\n", encoding="utf-8")
    inst = BotInstance(name="inst", folder=folder)
    inst.deepseek_api_key = api_key
    return inst


class TestMaskApiKey:
    def test_masks_real_key(self):
        assert _mask_api_key("sk-real-secret-1234") == "sk-****1234"

    def test_empty_key_stays_empty(self):
        assert _mask_api_key("") == ""

    def test_short_key_still_masked(self):
        assert _mask_api_key("abc123") == "sk-****c123"


class TestApplyConfigFields:
    def test_folder_and_name_rejected(self, tmp_path):
        inst = _make_inst(tmp_path)
        _apply_config_fields(inst, {"folder": "../../evil", "name": "hack"})
        assert inst.folder == tmp_path / "inst"
        assert inst.name == "inst"

    def test_unknown_fields_ignored(self, tmp_path):
        inst = _make_inst(tmp_path)
        _apply_config_fields(inst, {"__proto__": "x", "not_a_field": 1})
        assert not hasattr(inst, "not_a_field")

    def test_masked_key_not_overwritten(self, tmp_path):
        inst = _make_inst(tmp_path)
        _apply_config_fields(inst, {"deepseek_api_key": "sk-****1234"})
        assert inst.deepseek_api_key == "sk-real-secret-1234"

    def test_new_key_written(self, tmp_path):
        inst = _make_inst(tmp_path)
        _apply_config_fields(inst, {"deepseek_api_key": "sk-new-key-9999"})
        assert inst.deepseek_api_key == "sk-new-key-9999"

    def test_empty_key_clears(self, tmp_path):
        inst = _make_inst(tmp_path)
        _apply_config_fields(inst, {"deepseek_api_key": ""})
        assert inst.deepseek_api_key == ""

    def test_normal_fields_written(self, tmp_path):
        inst = _make_inst(tmp_path)
        _apply_config_fields(inst, {"log_dir": "logs", "cooldown_seconds": 7})
        assert inst.log_dir == "logs"
        assert inst.cooldown_seconds == 7

    def test_non_string_key_value_ignored(self, tmp_path):
        inst = _make_inst(tmp_path)
        _apply_config_fields(inst, {"deepseek_api_key": 12345})
        assert inst.deepseek_api_key == "sk-real-secret-1234"
