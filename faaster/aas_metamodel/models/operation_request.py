"""The operation request object."""

from typing import List, Optional
from faaster.aas_metamodel.dto import DTO
from faaster.aas_metamodel.models.operation_variable import OperationVariable


class OperationRequest(DTO):
    """The operation request object."""

    input_arguments: Optional[List[OperationVariable]] = []
    inoutput_arguments: Optional[List[OperationVariable]] = []
    client_timeout_duration: int
