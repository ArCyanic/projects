"""Model sources and fixed experiment settings shared by CLI recipes."""

from pathlib import Path

MODELS = {
    "deepseek-v3": "DeepSeek-V3",
    "deepseek-v2-lite": "DeepSeek-V2-Lite",
    "qwen2-57b-a14b": "Qwen2-57B-A14B",
}


PROFILES = ("planar", "vertical")


FINAL_BUDGET_PERCENT = 20


def inputs_path(model):
    directories = {
        "deepseek-v3": "deepseek-v3-seed0",
        "deepseek-v2-lite": "deepseek-v2-lite-public",
        "qwen2-57b-a14b": "qwen2-57b-a14b-hd-moe",
    }
    return Path("artifacts/inputs") / directories[model]


def bandwidths(model):
    return (0.5, 2.0, 8.0) if model == "deepseek-v3" else (2.0,)


def endpoint_test_path(directory, bandwidth):
    if bandwidth == 2.0:
        return directory / "selected-20pct-test.json"
    return directory / f"{bandwidth:g}-endpoint-test.json"
