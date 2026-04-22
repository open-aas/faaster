"""Data model for OperationResult, representing the result of an operation."""

from typing import List, Optional
from faaster.aas_metamodel.dto import DTO
from faaster.aas_metamodel.models.execution_state import ExecutionState
from faaster.aas_metamodel.models.message import Message
from faaster.aas_metamodel.models.operation_variable import OperationVariable


class OperationResult(DTO):
    """Data model for OperationResult, representing the result of an operation.

    With associated messages, execution state, and success status.
    """

    output_arguments: Optional[List[OperationVariable]] = []
    inoutput_arguments: Optional[List[OperationVariable]] = []
    messages: List[Message]
    execution_state: ExecutionState
    success: bool
