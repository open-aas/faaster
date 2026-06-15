"""
GDS Registration Manager — OPC 10000-12 §6.4, Figura 11.

Implementa o Application Registration Workflow completo:

    1. FindApplications(applicationUri)
       ├─ 0 resultados  → RegisterApplication  (novo registro)
       ├─ 1 resultado   → UpdateApplication    (já registrado)
       └─ > 1 resultado → RuntimeError         (intervenção manual necessária)

    2. Persiste o applicationId retornado.
    3. Executa re-registro periódico via UpdateApplication.
    4. Chama UnregisterApplication no encerramento.
"""
from __future__ import annotations

import asyncio

from asyncua.ua import NodeId

from faaster.log import get_logger

from .client import GDSClient
from .models import ApplicationRecord

logger = get_logger(__name__)


class GDSRegistrationManager:
    """
    Gerencia o ciclo de vida completo do registro no GDS.

    Uso básico (integrado com o servidor):

        manager = GDSRegistrationManager(client, record, renew_interval=3600)
        asyncio.create_task(manager.run(stop_event))
    """

    def __init__(
        self,
        client: GDSClient,
        record: ApplicationRecord,
        renew_interval: int = 3600,
    ) -> None:
        self._client = client
        self._record = record
        self._renew_interval = renew_interval
        self._application_id: NodeId | None = None

    @property
    def application_id(self) -> NodeId | None:
        return self._application_id

    # ------------------------------------------------------------------
    # Workflow de registro (OPC 10000-12 §6.4, Figura 11)
    # ------------------------------------------------------------------

    async def register(self) -> NodeId:
        """
        Executa o workflow de registro contra o GDS.

        Retorna o applicationId persistente que deve ser armazenado pela
        aplicação para re-uso em ciclos futuros (GDS persistence, Figura 11).
        """
        async with self._client:
            existing = await self._client.find_applications(self._record.application_uri)

            if len(existing) == 0:
                logger.info(
                    "gds_manager.new_registration",
                    uri=self._record.application_uri,
                )
                self._application_id = await self._client.register_application(self._record)
                self._record.application_id = self._application_id

            elif len(existing) == 1:
                logger.info(
                    "gds_manager.update_existing",
                    uri=self._record.application_uri,
                    application_id=str(existing[0].application_id),
                )
                self._record.application_id = existing[0].application_id
                self._application_id = existing[0].application_id
                await self._client.update_application(self._record)

            else:
                # Spec §6.4: mais de um resultado indica erro fatal —
                # requer intervenção manual de um DiscoveryAdmin.
                raise RuntimeError(
                    f"GDS retornou {len(existing)} registros para "
                    f"'{self._record.application_uri}'. "
                    "Intervenção manual de um DiscoveryAdmin é necessária."
                )

        logger.info(
            "gds_manager.registered",
            application_id=str(self._application_id),
        )
        return self._application_id

    async def unregister(self) -> None:
        """Remove o registro do GDS no encerramento do servidor."""
        if self._application_id is None:
            return

        async with self._client:
            await self._client.unregister_application(self._application_id)

        logger.info(
            "gds_manager.unregistered",
            application_id=str(self._application_id),
        )
        self._application_id = None

    # ------------------------------------------------------------------
    # Loop de re-registro periódico
    # ------------------------------------------------------------------

    async def run(self, stop_event: asyncio.Event) -> None:
        """
        Tarefa assíncrona de longa duração.

        Executa o registro inicial e renova via UpdateApplication a cada
        renew_interval segundos, conforme recomendado pelo §6.3 da spec
        (ciclos de PullManagement devem iniciar com atraso aleatório entre
        1× e 1.1× o período).

        Ao receber o sinal de parada (stop_event), chama UnregisterApplication.
        """
        try:
            await self.register()
        except Exception as e:
            logger.error("gds_manager.register_failed", error=str(e))
            return

        while not stop_event.is_set():
            try:
                await asyncio.wait_for(
                    stop_event.wait(),
                    timeout=self._renew_interval,
                )
            except asyncio.TimeoutError:
                await self._renew()

        await self.unregister()

    async def _renew(self) -> None:
        try:
            async with self._client:
                await self._client.update_application(self._record)
            logger.info(
                "gds_manager.renewed",
                application_id=str(self._application_id),
            )
        except Exception as e:
            logger.warning("gds_manager.renew_failed", error=str(e))
