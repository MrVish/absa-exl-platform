import pytest
from code_intake.errors import (
    CodeIntakeError,
    PackageConfigError,
    ValidationError,
)


def test_code_intake_error_is_exception():
    assert issubclass(CodeIntakeError, Exception)


def test_validation_error_is_code_intake_error():
    assert issubclass(ValidationError, CodeIntakeError)


def test_package_config_error_is_code_intake_error():
    assert issubclass(PackageConfigError, CodeIntakeError)


def test_raising_validation_error_carries_message():
    with pytest.raises(ValidationError, match="bad package"):
        raise ValidationError("bad package")
