class InvalidFieldException(Exception):
    """Exception raised when a provided field value is invalid (400)."""

    def __init__(self, detail: str = "Invalid value for field"):
        """Initialize an invalid field exception.

        :param detail: Error message describing the invalid field.
        :return: None
        """

        super().__init__(detail)

class InvalidIdException(Exception):
    """Exception raised when an invalid object ID is provided (400)."""

    def __init__(
        self,
        detail: str = "The provided ID is not a valid object ID",
    ):
        """Initialize an invalid ID exception.

        :param detail: Error message describing the invalid ID.
        :return: None
        """
        super().__init__(detail)
