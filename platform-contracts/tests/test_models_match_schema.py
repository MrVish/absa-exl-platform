import pytest
from platform_contracts import models
from platform_contracts.loader import load_schema

CASES = [
    ("model-config", "ModelConfig"),
    ("registry-record", "RegistryRecord"),
    ("manifest-envelope", "ManifestEnvelope"),
    ("pipeline-manifest-payload", "PipelineManifestPayload"),
    ("package-manifest-payload", "PackageManifestPayload"),
    ("pir-mapping", "PirMapping"),
]


@pytest.mark.parametrize(("schema_name", "model_name"), CASES)
def test_model_covers_all_schema_properties(schema_name: str, model_name: str) -> None:
    schema = load_schema(schema_name)
    model = getattr(models, model_name)
    assert set(schema["properties"]).issubset(set(model.model_fields))
