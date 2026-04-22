"""Handle for tracking the state of an asynchronous operation execution."""

from faaster.aas_metamodel.dto import DTO


class OperationHandle(DTO):
    """Handle for tracking the state of an asynchronous operation execution."""

    handle_id: str
