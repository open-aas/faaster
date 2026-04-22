from abc import ABC, abstractmethod
from .context import SubmodelContext


class ISubmodelExtension(ABC):
    """
    Interface base para extensões de submódulo do Faaster.

    Cada submódulo do AAS pode ter um script Python correspondente
    em extensions/{id_short}.py que implementa esta interface.

    Convenção de nomenclatura:
        - Arquivo: extensions/{submodel_id_short_snake_case}.py
        - Classe:  {SubmodelIdShortPascalCase}

    Exemplo:
        extensions/condition_monitoring.py
            class ConditionMonitoring(ISubmodelExtension): ...

    Ciclo de vida:
        1. ExtensionLoader instancia a classe
        2. ExtensionLoader chama init(context) — antes do server.run()
        3. ExtensionLoader chama stop() — no encerramento do servidor
    """

    @abstractmethod
    def __init__(self, context: SubmodelContext) -> None:
        pass

    @abstractmethod
    async def init(self) -> None:
        """
        Inicializa a extensão com o contexto do submódulo.

        Aqui o script deve:
            - armazenar o context para uso posterior
            - resolver os nós necessários via context.get_node()
            - iniciar tasks assíncronas de comunicação com o dispositivo
            - subscrever eventos se necessário
        """
        ...

    @abstractmethod
    async def stop(self) -> None:
        """
        Encerra a extensão graciosamente.

        Aqui o script deve:
            - cancelar tasks em background
            - fechar conexões com dispositivos
            - liberar recursos
        """
        ...
