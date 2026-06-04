from __future__ import annotations

import click


@click.group()
def main() -> None:
    """ABSA x EXL Pipeline Factory generator (validate | generate | register)."""


if __name__ == "__main__":  # pragma: no cover
    main()
