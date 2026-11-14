import pytest

from app.device import pick_device


def test_auto_uses_the_gpu_when_there_is_one() -> None:
    assert pick_device("auto", cuda_available=True) == "cuda"


def test_auto_falls_back_to_the_cpu_without_a_gpu() -> None:
    # The local CPU-only image has no CUDA: it must keep working as before.
    assert pick_device("auto", cuda_available=False) == "cpu"


def test_an_empty_setting_means_auto() -> None:
    assert pick_device("", cuda_available=True) == "cuda"
    assert pick_device("", cuda_available=False) == "cpu"


def test_cpu_can_be_forced_on_a_gpu_host() -> None:
    assert pick_device("cpu", cuda_available=True) == "cpu"


def test_setting_is_case_and_space_insensitive() -> None:
    assert pick_device(" CUDA ", cuda_available=True) == "cuda"


def test_forcing_cuda_without_a_gpu_is_an_error() -> None:
    # A GPU host whose container can't see the GPU should fail loudly at startup,
    # not quietly run on the CPU.
    with pytest.raises(ValueError):
        pick_device("cuda", cuda_available=False)


def test_an_unknown_setting_is_an_error() -> None:
    with pytest.raises(ValueError):
        pick_device("tpu", cuda_available=True)
