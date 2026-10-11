"""
Invocação de Operations — InvokeOperation (síncrona), InvokeOperationAsync,
GetOperationAsyncStatus e GetOperationAsyncResult (IDTA-01002-3-2), nas
formas normal e ValueOnly.

A Operation roda pelo Call service do servidor OPC UA, exatamente como numa
chamada de um cliente OPC UA: o método do nó delega para o handler que a
extensão do submodelo vinculou via MethodBinder.

Erros reconhecíveis antes da execução (argumento desconhecido, valor
inválido, Operation sem implementação) respondem direto com 400/405/501.
Erros durante a execução viram um OperationResult com executionState
Failed (ou Timeout), como manda a spec.
"""
import asyncio
import copy
import re
import uuid
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from faaster.interfaces import IAddressSpace
from faaster.interfaces.types import FaasterVariantType
from faaster.log import get_logger
from faaster.parser.creators.base import resolve_variant_type
from faaster.parser.node_registry import NodeRegistry, OperationEntry

from .errors import BadRequestError, MethodNotAllowedError, NotFoundError, NotImplementedApiError, message
from .modifiers import typed_value
from .serializer import format_xs_value
from .writer import parse_value, to_node_value


logger = get_logger(__name__)


# xs:duration — mesmo padrão do schema clientTimeoutDuration
_DURATION = re.compile(
    r"^(?P<sign>-?)P(?=.)(?:(?P<years>\d+)Y)?(?:(?P<months>\d+)M)?(?:(?P<days>\d+)D)?"
    r"(?:T(?=.)(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d*(?:\.\d+)?)S)?)?$"
)
_SECONDS = {
    "years": 365 * 86400,   # aproximação: o timeout é só uma sugestão do cliente
    "months": 30 * 86400,
    "days": 86400,
    "hours": 3600,
    "minutes": 60,
    "seconds": 1,
}

# resultados assíncronos mantidos em memória (os mais antigos são descartados)
MAX_ASYNC_RESULTS = 1000


def parse_duration(value: Any) -> float:
    """clientTimeoutDuration (xs:duration, ex.: PT30S) → segundos."""
    match = _DURATION.match(value) if isinstance(value, str) else None
    if match is None:
        raise BadRequestError(f"Invalid clientTimeoutDuration {value!r}: expected an xs:duration like 'PT30S'")
    if match.group("sign"):
        raise BadRequestError("clientTimeoutDuration must not be negative")
    return sum(
        float(match.group(unit)) * factor
        for unit, factor in _SECONDS.items()
        if match.group(unit)
    )


def _variables(operation: Dict[str, Any], key: str) -> List[Dict[str, Any]]:
    """SubmodelElements de inputVariables/outputVariables, como o OperationCreator os vê."""
    return [var["value"] for var in operation.get(key) or [] if var.get("value")]


@dataclass
class PreparedCall:
    entry: OperationEntry
    inputs: List[Tuple[Any, FaasterVariantType]]
    outputs: List[Dict[str, Any]]
    timeout: Optional[float]


@dataclass
class Outcome:
    execution_state: str
    success: bool
    outputs: List[Tuple[Dict[str, Any], Any]] = field(default_factory=list)
    messages: List[Dict[str, Any]] = field(default_factory=list)

    def render(self, value_only: bool) -> Dict[str, Any]:
        """OperationResult ou OperationResultValueOnly."""
        result: Dict[str, Any] = {"executionState": self.execution_state, "success": self.success}
        if self.messages:
            result["messages"] = self.messages

        if value_only:
            result["outputArguments"] = {
                variable.get("idShort"): typed_value(format_xs_value(value), variable.get("valueType"))
                for variable, value in self.outputs
            }
        else:
            result["outputArguments"] = [
                {"value": self._output_variable(variable, value)} for variable, value in self.outputs
            ]
        return result

    @staticmethod
    def _output_variable(variable: Dict[str, Any], value: Any) -> Dict[str, Any]:
        rendered = copy.deepcopy(variable)
        lexical = format_xs_value(value)
        if lexical is None:
            rendered.pop("value", None)
        else:
            rendered["value"] = lexical
        return rendered


@dataclass
class AsyncInvocation:
    submodel_id: str
    path: str
    value_only: bool
    task: Optional[asyncio.Task] = None
    outcome: Optional[Outcome] = None


class OperationInvoker:
    def __init__(
        self,
        registry: Optional[NodeRegistry] = None,
        address_space: Optional[IAddressSpace] = None,
    ) -> None:
        self._registry = registry
        self._address_space = address_space
        self._async: "OrderedDict[str, AsyncInvocation]" = OrderedDict()

    # -------------------------------------------------------------------------
    # Preparação (valida tudo antes de executar)
    # -------------------------------------------------------------------------

    def prepare(
        self,
        element: Dict[str, Any],
        submodel_id: str,
        path: str,
        body: Dict[str, Any],
        value_only: bool,
        require_timeout: bool = False,
    ) -> PreparedCall:
        if element.get("modelType") != "Operation":
            raise MethodNotAllowedError(
                f"'{path}' is a {element.get('modelType')}: invoke is only valid for Operation elements"
            )

        entry = self._registry.get_operation(submodel_id, path) if self._registry else None
        if entry is None or self._address_space is None:
            raise NotImplementedApiError(f"Operation '{path}' has no OPC UA method to invoke")
        if not entry.binder.is_bound:
            raise NotImplementedApiError(
                f"Operation '{path}' is not implemented: no submodel extension method is bound to it"
            )

        if _variables(element, "inoutputVariables"):
            raise NotImplementedApiError(
                f"Operation '{path}' declares inoutputVariables, which are not supported yet"
            )

        provided = self._arguments(body, "inputArguments", value_only)
        if self._arguments(body, "inoutputArguments", value_only):
            raise BadRequestError(f"Operation '{path}' has no inoutputVariables")

        timeout = body.get("clientTimeoutDuration")
        if timeout is None and require_timeout:
            raise BadRequestError("clientTimeoutDuration is required for asynchronous invocations")

        return PreparedCall(
            entry=entry,
            inputs=self._inputs(element, path, provided),
            outputs=_variables(element, "outputVariables"),
            timeout=parse_duration(timeout) if timeout is not None else None,
        )

    @staticmethod
    def _arguments(body: Dict[str, Any], key: str, value_only: bool) -> Dict[str, Any]:
        """Argumentos do corpo → {idShort: valor (léxico ou JSON tipado)}."""
        arguments = body.get(key)
        if arguments is None:
            return {}

        if value_only:
            if not isinstance(arguments, dict):
                raise BadRequestError(f"{key} must be a JSON object in the ValueOnly invocation")
            return arguments

        if not isinstance(arguments, list):
            raise BadRequestError(f"{key} must be a JSON array of OperationVariables")
        provided: Dict[str, Any] = {}
        for argument in arguments:
            variable = argument.get("value") if isinstance(argument, dict) else None
            if not isinstance(variable, dict) or not variable.get("idShort"):
                raise BadRequestError(f"Each item of {key} must be an OperationVariable with an idShort")
            provided[variable["idShort"]] = variable.get("value")
        return provided

    @staticmethod
    def _inputs(
        operation: Dict[str, Any],
        path: str,
        provided: Dict[str, Any],
    ) -> List[Tuple[Any, FaasterVariantType]]:
        variables = _variables(operation, "inputVariables")

        unknown = set(provided) - {v.get("idShort") for v in variables}
        if unknown:
            raise BadRequestError(f"Operation '{path}' has no input argument {sorted(unknown)}")

        # mesma ordem dos InputArguments do método OPC UA (OperationCreator)
        inputs: List[Tuple[Any, FaasterVariantType]] = []
        for variable in variables:
            id_short = variable.get("idShort")
            if variable.get("modelType") != "Property":
                raise NotImplementedApiError(
                    f"Input argument '{id_short}' is a {variable.get('modelType')}: "
                    f"only Property arguments are supported"
                )

            value = provided.get(id_short)
            if value is None:
                # sem valor no corpo, usa o valor padrão declarado no modelo
                value = variable.get("value")
            if value is None:
                raise BadRequestError(f"Missing input argument '{id_short}' of Operation '{path}'")

            label = f"inputArguments.{id_short}"
            variant_type = resolve_variant_type(variable.get("valueType"))
            parsed = parse_value(value, variable.get("valueType"), label)
            inputs.append((to_node_value(parsed, variant_type, label), variant_type))
        return inputs

    # -------------------------------------------------------------------------
    # Execução
    # -------------------------------------------------------------------------

    async def execute(self, call: PreparedCall, path: str) -> Outcome:
        try:
            result = await asyncio.wait_for(
                self._address_space.call_method(call.entry.method_node, call.inputs),
                timeout=call.timeout,
            )
        except asyncio.TimeoutError:
            return Outcome(
                execution_state="Timeout",
                success=False,
                messages=[message("Timeout", f"Operation '{path}' did not finish within clientTimeoutDuration")],
            )
        except Exception as e:
            logger.exception("api.operation.failed", id_short_path=path)
            return Outcome(
                execution_state="Failed",
                success=False,
                messages=[message("Exception", f"Operation '{path}' failed: {e}")],
            )

        if not result.is_good:
            logger.warning("api.operation.bad_status", id_short_path=path, status=result.status)
            return Outcome(
                execution_state="Failed",
                success=False,
                messages=[message(result.status, f"Operation '{path}' returned OPC UA status {result.status}")],
            )

        if len(result.outputs) != len(call.outputs):
            logger.warning(
                "api.operation.output_mismatch",
                id_short_path=path,
                declared=len(call.outputs),
                returned=len(result.outputs),
            )
        return Outcome(
            execution_state="Completed",
            success=True,
            outputs=list(zip(call.outputs, result.outputs)),
        )

    # -------------------------------------------------------------------------
    # Invocação assíncrona
    # -------------------------------------------------------------------------

    def start(self, call: PreparedCall, submodel_id: str, path: str, value_only: bool) -> str:
        handle_id = uuid.uuid4().hex
        invocation = AsyncInvocation(submodel_id=submodel_id, path=path, value_only=value_only)

        async def run() -> None:
            invocation.outcome = await self.execute(call, path)

        invocation.task = asyncio.create_task(run(), name=f"faaster.operation.{handle_id}")
        self._async[handle_id] = invocation
        self._evict()
        return handle_id

    def get(self, handle_id: str, submodel_id: str, path: str) -> AsyncInvocation:
        invocation = self._async.get(handle_id)
        if invocation is None or (invocation.submodel_id, invocation.path) != (submodel_id, path):
            raise NotFoundError(f"No asynchronous invocation '{handle_id}' for Operation '{path}'")
        return invocation

    def _evict(self) -> None:
        # descarta os resultados mais antigos já concluídos
        for handle_id in list(self._async):
            if len(self._async) <= MAX_ASYNC_RESULTS:
                return
            if self._async[handle_id].outcome is not None:
                del self._async[handle_id]

    def cancel_all(self) -> None:
        for invocation in self._async.values():
            if invocation.task is not None and not invocation.task.done():
                invocation.task.cancel()
