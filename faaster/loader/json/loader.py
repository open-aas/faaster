from pathlib import Path
from typing import Tuple, List
from pydantic import ValidationError
from ..interfaces import ILoaderJson
from ..exceptions import (
    FileNotFoundLoaderError,
    MalformedFileLoaderError,
    ValidationLoaderError,
)
from faaster.aas_metamodel.models.environment import Environment
from faaster.log import get_logger

import json


logger = get_logger(__name__)


class JsonLoader(ILoaderJson):
    """
    Implementação concreta de ILoaderJson.

    Carrega um arquivo JSON, desserializa para dict
    e valida contra o metamodelo AAS V3 via pydantic.
    """

    async def load(self, path: Path) -> Environment:
        logger.info("loader.json.load.start", path=str(path))

        self._check_exists(path)
        raw = self._read(path)
        data = self._parse_json(path, raw)
        environment = self._validate(path, data)

        logger.info(
            "loader.json.load.done",
            path=str(path),
            aas=len(environment.asset_administration_shells),
            submodels=len(environment.submodels),
            concept_descriptions=len(environment.concept_descriptions),
        )

        return environment

    @staticmethod
    def _check_exists(path: Path) -> None:
        if not path.exists():
            raise FileNotFoundLoaderError(str(path))

    @staticmethod
    def _read(path: Path) -> bytes:
        try:
            return path.read_bytes()
        except OSError as e:
            raise MalformedFileLoaderError(str(path), str(e)) from e

    @staticmethod
    def _parse_json(path: Path, raw: bytes) -> dict:
        try:
            return json.loads(raw)

        except json.JSONDecodeError as e:

            raise MalformedFileLoaderError(
                str(path),
                f"Invalid JSON at line {e.lineno}, col {e.colno}: {e.msg}",
            ) from e

    @staticmethod
    def _validate(
            path: Path, data: dict) -> Environment:

        try:
            return Environment(
                asset_administration_shells=data['assetAdministrationShells'],
                submodels=data['submodels'],
                concept_descriptions=data['conceptDescriptions'],
            )

        except ValidationError as e:
            raise ValidationLoaderError(str(path), str(e)) from e
