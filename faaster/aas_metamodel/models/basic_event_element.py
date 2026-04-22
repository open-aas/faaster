"""A basic event element."""

from typing import Literal, Optional
from pydantic import Field
from faaster.aas_metamodel.models.constrained_string import ConstrainedString
from faaster.aas_metamodel.models.direction import Direction
from faaster.aas_metamodel.models.event_element import EventElement
from faaster.aas_metamodel.models.model_type import ModelType
from faaster.aas_metamodel.models.reference import Reference
from faaster.aas_metamodel.models.state_of_event import StateOfEvent


class BasicEventElement(EventElement):
    """A basic event element.

    :param observed: Reference to te Referable, which defines the scope of the event.
    Can be AAS, Submodel or SubmodelElement.
    Reference to a referable, e.g. a data element or a submodel, that is being observed.
    :param direction: Direction of event.
    :param state: State of event.
    :param message_topic: Information for the outer message infrastructure for scheduling
    the event to the respective communication channel.
    :param message_broker: Information, which outer message infrastructure shall handle messages
    for the EventElement. Refers to a Submodel, SubmodelElementList.
    SubmodelElementCollection or Entity, which contains DataElements describing the proprietary
    specification for the message broker.
    :param last_update: Timestamp in UTC, when the last event was received (input direction)
    or sent (output direction).
    :param min_interval: For input direction, reports on the maximum frequency, the software entity
    behind the respective Referable can handle input events.
    For output events, specifies the maximum frequency of outputting this event to an outer
    infrastructure.
    Might be not specified, that is, there is no minimal interval.
    :param max_interval: For input direction: not applicable.
    For output direction: maximum interval in time, the respective Referable shall send an
    update of the status of the event, even if no other trigger condition for the event was not met.
    Might be not specified, that is, there is no maximum interval.
    """

    type_model: Literal[ModelType.BASIC_EVENT_ELEMENT] = Field(
        alias="modelType", default=ModelType.BASIC_EVENT_ELEMENT
    )
    observed: Reference
    direction: Direction
    state: StateOfEvent
    message_topic: Optional[ConstrainedString] = None
    message_broker: Optional[Reference] = None
    # last_update: Optional[datetime] = None
    # min_interval: Optional[timedelta] = None
    # max_interval: Optional[timedelta] = None
    last_update: Optional[ConstrainedString] = None
    min_interval: Optional[ConstrainedString] = None
    max_interval: Optional[ConstrainedString] = None
