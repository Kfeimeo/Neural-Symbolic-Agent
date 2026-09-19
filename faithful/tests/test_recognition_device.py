import json
import pytest
import torch
from faithful.python.grid import grammar, REQUEST
from faithful.python.kernel import Kernel, abstraction, application, primitive, index
from faithful.python.recognition import Recognition


def frontier():
    return {'request': REQUEST, 'entries': [{'program': abstraction(application(primitive('invert'), index(0))), 'log_likelihood': 0.}]}


def test_automatic_device_and_cpu_features():
    model = Recognition(grammar())
    expected = 'cuda' if torch.cuda.is_available() else 'cpu'
    assert model.device.type == expected
    assert model(torch.zeros(40)).device.type == expected
    assert all(p.device == model.device for p in model.parameters())
    # The Haskell boundary must still receive ordinary JSON numbers.
    json.dumps(model.search_grammar(torch.zeros(40)))


def test_cpu_fallback_and_explicit_override(monkeypatch):
    monkeypatch.setattr(torch.cuda, 'is_available', lambda: False)
    assert Recognition(grammar()).device.type == 'cpu'
    assert Recognition(grammar(), device='cpu').device.type == 'cpu'


@pytest.mark.parametrize('objective', ['bias_optimal', 'kl'])
def test_training_on_selected_device(objective):
    previous = torch.are_deterministic_algorithms_enabled()
    torch.use_deterministic_algorithms(True)
    try:
        torch.manual_seed(135)
        model = Recognition(grammar())
        before = [p.detach().clone() for p in model.parameters()]
        with Kernel() as k:
            losses = model.fit_frontiers(k, [(torch.linspace(-1, 1, 40), frontier())], steps=3, seed=7, objective=objective)
        assert len(losses) == 3 and all(torch.isfinite(torch.tensor(losses)))
        assert any(not torch.equal(a, b) for a, b in zip(before, model.parameters()))
        assert all(p.grad is not None and p.grad.device == model.device for p in model.parameters())
    finally:
        torch.use_deterministic_algorithms(previous)


@pytest.mark.skipif(not torch.cuda.is_available(), reason='CUDA-specific portability test')
def test_cuda_cpu_equivalence_and_checkpoint_roundtrip(tmp_path):
    torch.manual_seed(271)
    cpu = Recognition(grammar(), device='cpu')
    gpu = Recognition(grammar(), device='cuda')
    x = torch.linspace(-.5, .5, 40)
    path = tmp_path/'recognition.pt'
    torch.save({'state_dict': cpu.state_dict()}, path)
    gpu.load_state_dict(torch.load(path, map_location=gpu.device, weights_only=True)['state_dict'])
    torch.testing.assert_close(cpu(x), gpu(x).cpu(), atol=2e-6, rtol=2e-5)
    previous = torch.are_deterministic_algorithms_enabled()
    torch.use_deterministic_algorithms(True)
    try:
        with Kernel() as k:
            a = cpu.fit_frontiers(k, [(x, frontier())], steps=3, seed=41)
            b = gpu.fit_frontiers(k, [(x, frontier())], steps=3, seed=41)
        assert a == pytest.approx(b, abs=1e-4, rel=1e-4)
    finally:
        torch.use_deterministic_algorithms(previous)
    torch.save({'state_dict': gpu.state_dict()}, path)
    cpu.load_state_dict(torch.load(path, map_location='cpu', weights_only=True)['state_dict'])
    assert cpu.device.type == 'cpu'
    torch.testing.assert_close(cpu(x), gpu(x).cpu(), atol=2e-6, rtol=2e-5)
    # Following .to() must remain supported; no stale stored device attribute.
    gpu.to('cpu')
    assert gpu.device.type == 'cpu' and gpu(x).device.type == 'cpu'


def test_runtime_variant_preserves_frozen_data(tmp_path):
    from faithful.python.controlled_run import OUT, fork_runtime, read, verify
    if not (OUT/'benchmark_manifest.json').exists(): pytest.skip('Requires frozen benchmark')
    target = tmp_path/'cuda_run'
    fork_runtime(OUT, target)
    parent = verify(OUT, check_current_core=False)
    child = verify(target)
    assert child['sha256'] == parent['sha256']
    assert child['runtime_parent_manifest_sha256']
    assert not (target/'runs').exists()  # Never mix prior training checkpoints.
    with pytest.raises(ValueError, match='new directory'):
        fork_runtime(OUT, target)
