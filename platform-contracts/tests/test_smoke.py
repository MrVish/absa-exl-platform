import platform_contracts


def test_package_imports() -> None:
    assert platform_contracts.__name__ == "platform_contracts"
