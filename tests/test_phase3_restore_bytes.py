from pathlib import Path
import importlib.util
import pytest

spec = importlib.util.spec_from_file_location('phase3_restore_bytes', Path(__file__).resolve().parents[1]/'scripts/phase3_restore_bytes.py')
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)


def test_restore_exact_mixed_frozen_line_endings(tmp_path):
    (tmp_path/'a.py').write_bytes(b'x = 1\ny = 2\n')
    (tmp_path/'b.json').write_bytes(b'{}\r\n')
    expected = {'a.py': helper.digest(b'x = 1\r\ny = 2\r\n'), 'b.json': helper.digest(b'{}\n')}
    assert helper.restore(tmp_path, expected) == ['a.py', 'b.json']
    assert (tmp_path/'a.py').read_bytes() == b'x = 1\ny = 2\n'
    helper.restore(tmp_path, expected, apply=True)
    assert helper.restore(tmp_path, expected, apply=True) == []


def test_semantic_edit_aborts_entire_preflight(tmp_path):
    (tmp_path/'a.py').write_bytes(b'a\n')
    (tmp_path/'z.py').write_bytes(b'max_parameters=5\n')
    hashes = {'a.py': helper.digest(b'a\r\n'), 'z.py': helper.digest(b'max_parameters=2\n')}
    with pytest.raises(ValueError, match='No files written'):
        helper.restore(tmp_path, hashes, apply=True)
    assert (tmp_path/'a.py').read_bytes() == b'a\n'
    assert (tmp_path/'z.py').read_bytes() == b'max_parameters=5\n'


def test_reject_path_outside_repository(tmp_path):
    with pytest.raises(ValueError, match='escapes repository'):
        helper.restore(tmp_path, {'../escape': 'unused'}, apply=True)
