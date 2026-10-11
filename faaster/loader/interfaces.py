from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Optional, Tuple

from faaster.aas_metamodel.models.environment import Environment


class ILoader(ABC):
    """
    Interface base para carregamento de arquivos de modelagem AAS.

    Independente do formato de entrada (.json, .xml, .aasx),
    o resultado final é sempre um Environment pydantic validado
    contra o metamodelo AAS V3.
    """

    @abstractmethod
    async def load(self, path: Path) -> Environment:
        """
        Carrega o arquivo de modelagem e retorna o Environment
        com o metamodelo AAS V3 validado.

        Raises:
            FileNotFoundLoaderError: arquivo não encontrado.
            MalformedFileLoaderError: conteúdo inválido ou malformado.
            ValidationLoaderError: estrutura incompatível com AAS V3.
        """
        ...

    @property
    def document(self) -> Optional[dict]:
        """
        Documento AAS V3 original (serialização JSON da Part 1) do último
        load(), sem a normalização do pydantic. É a fonte usada pela
        API HTTP/REST para responder fielmente ao modelo de entrada.
        """
        return None


class ILoaderJson(ILoader, ABC):
    """
    Interface para carregamento de arquivos JSON.
    """
    ...


class ILoaderXml(ILoader, ABC):
    """
    Interface para carregamento de arquivos XML.
    """
    ...


class ILoaderAasx(ILoader, ABC):
    """
    Interface para carregamento de arquivos AASX.

    O AASX é um ZIP que contém um arquivo JSON ou XML internamente.
    A implementação deve extrair o conteúdo e delegar para
    ILoaderJson ou ILoaderXml.
    """

    @abstractmethod
    async def extract(self, path: Path) -> Path:
        """
        Extrai o conteúdo do AASX e retorna o path
        do arquivo JSON ou XML extraído.
        """
        ...
