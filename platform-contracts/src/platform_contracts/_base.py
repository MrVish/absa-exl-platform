from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ContractBase(BaseModel):
    """Base for generated contract models.

    `protected_namespaces=()` silences Pydantic's warning about fields that begin
    with `model_` (e.g. `model_name`, `model_class`).
    """

    model_config = ConfigDict(protected_namespaces=())
