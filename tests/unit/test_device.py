from subforge.app.device import DeviceDetector, DeviceSpecs


def test_device_specs_dataclass() -> None:
    specs = DeviceSpecs(ram_gb=16.0, cpu_cores=8)
    assert specs.ram_gb == 16.0
    assert specs.cpu_cores == 8


def test_recommend_model_low_end() -> None:
    # Less than 6 GB RAM or <= 2 cores -> tiny
    assert DeviceDetector.recommend_model(DeviceSpecs(ram_gb=4.0, cpu_cores=2)) == "tiny"
    assert DeviceDetector.recommend_model(DeviceSpecs(ram_gb=5.5, cpu_cores=4)) == "tiny"


def test_recommend_model_budget() -> None:
    # 6 to 10 GB RAM -> base
    assert DeviceDetector.recommend_model(DeviceSpecs(ram_gb=8.0, cpu_cores=4)) == "base"
    assert DeviceDetector.recommend_model(DeviceSpecs(ram_gb=8.0, cpu_cores=2)) == "tiny"


def test_recommend_model_midrange() -> None:
    # 10 to 16 GB RAM with 4+ cores -> small
    assert DeviceDetector.recommend_model(DeviceSpecs(ram_gb=12.0, cpu_cores=6)) == "small"
    assert DeviceDetector.recommend_model(DeviceSpecs(ram_gb=16.0, cpu_cores=4)) == "small"


def test_recommend_model_highend() -> None:
    # >= 16 GB RAM with 6+ cores -> large-v3-turbo
    assert DeviceDetector.recommend_model(DeviceSpecs(ram_gb=16.0, cpu_cores=8)) == "large-v3-turbo"
    assert DeviceDetector.recommend_model(DeviceSpecs(ram_gb=32.0, cpu_cores=12)) == "large-v3-turbo"


def test_recommend_model_workstation() -> None:
    # > 32 GB RAM with >= 12 cores -> large-v3
    assert DeviceDetector.recommend_model(DeviceSpecs(ram_gb=64.0, cpu_cores=16)) == "large-v3"


def test_get_specs_returns_positive_numbers() -> None:
    specs = DeviceDetector.get_specs()
    assert specs.ram_gb > 0
    assert specs.cpu_cores > 0
    assert isinstance(specs.has_gpu, bool)
    assert specs.recommended_backend in ("cuda", "vulkan", "cpu")


def test_recommend_model_with_gpu() -> None:
    # If dedicated GPU is available, recommend large-v3-turbo even on budget RAM
    specs = DeviceSpecs(
        ram_gb=8.0,
        cpu_cores=4,
        has_gpu=True,
        gpu_name="NVIDIA GeForce RTX 4070",
        recommended_backend="cuda",
    )
    assert DeviceDetector.recommend_model(specs) == "large-v3-turbo"

