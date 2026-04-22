class LoaderError(Exception):
    """
    Exceção base para erros no módulo de loader.
    """
    ...


class FileNotFoundLoaderError(LoaderError):
    """
    Arquivo de modelagem não encontrado.
    """
    def __init__(self, path: str) -> None:
        super().__init__(f"Modeling file not found: '{path}'")
        self.path = path


class UnsupportedFormatLoaderError(LoaderError):
    """
    Formato de arquivo não suportado.
    """
    def __init__(self, extension: str) -> None:
        super().__init__(
            f"Unsupported modeling file format: '{extension}'. "
            f"Supported formats: .json, .xml, .aasx"
        )
        self.extension = extension


class MalformedFileLoaderError(LoaderError):
    """
    Arquivo encontrado mas com conteúdo inválido ou malformado.
    """
    def __init__(self, path: str, reason: str) -> None:
        super().__init__(f"Malformed modeling file '{path}': {reason}")
        self.path = path
        self.reason = reason


class ValidationLoaderError(LoaderError):
    """
    Arquivo carregado mas com estrutura incompatível
    com o metamodelo AAS V3.
    """
    def __init__(self, path: str, reason: str) -> None:
        super().__init__(
            f"AAS V3 validation failed for '{path}': {reason}"
        )
        self.path = path
        self.reason = reason
