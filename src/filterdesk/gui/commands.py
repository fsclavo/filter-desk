"""QUndoCommand wrappers around DesignSession mutations."""

from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from typing import TYPE_CHECKING

from PySide6.QtGui import QUndoCommand

from filterdesk.domain.circuit import Circuit
from filterdesk.domain.overlays import LimitRegion, Marker
from filterdesk.domain.specs import FilterSpec

if TYPE_CHECKING:
    from filterdesk.services.session import DesignSession


class EditCircuitCommand(QUndoCommand):
    """Topology edit (insert/delete/convert) with full circuit snapshot."""

    def __init__(
        self,
        session: DesignSession,
        new_circuit: Circuit,
        *,
        text: str = "Edit circuit",
        on_applied: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(text)
        self._session = session
        self._new = deepcopy(new_circuit)
        self._old = deepcopy(session.circuit)
        self._on_applied = on_applied

    def redo(self) -> None:
        self._session.replace_circuit(deepcopy(self._new))
        if self._on_applied is not None:
            self._on_applied()

    def undo(self) -> None:
        assert self._old is not None
        self._session.replace_circuit(deepcopy(self._old))
        if self._on_applied is not None:
            self._on_applied()


class SetElementValueCommand(QUndoCommand):
    def __init__(
        self,
        session: DesignSession,
        element_id: str,
        old_value: float,
        new_value: float,
        *,
        on_applied: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(f"Edit {element_id}")
        self._session = session
        self._element_id = element_id
        self._old = old_value
        self._new = new_value
        self._on_applied = on_applied

    def redo(self) -> None:
        self._session.update_element_value(self._element_id, self._new)
        if self._on_applied is not None:
            self._on_applied()

    def undo(self) -> None:
        self._session.update_element_value(self._element_id, self._old)
        if self._on_applied is not None:
            self._on_applied()


class SynthesizeCommand(QUndoCommand):
    """Snapshot circuit/spec/prototype around a synthesize call."""

    def __init__(
        self,
        session: DesignSession,
        new_spec: FilterSpec,
        *,
        on_applied: Callable[[], None] | None = None,
    ) -> None:
        super().__init__("Synthesize")
        self._session = session
        self._new_spec = new_spec
        self._on_applied = on_applied
        self._old_spec = deepcopy(session.spec)
        self._old_circuit = deepcopy(session.circuit)
        self._old_prototype = deepcopy(session.prototype)

    def redo(self) -> None:
        self._session.set_spec(self._new_spec)
        self._session.synthesize()
        if self._on_applied is not None:
            self._on_applied()

    def undo(self) -> None:
        self._session.spec = self._old_spec
        self._session.circuit = self._old_circuit
        self._session.prototype = self._old_prototype
        self._session.analysis = None
        self._session.dirty = True
        if self._on_applied is not None:
            self._on_applied()


class SetMarkersCommand(QUndoCommand):
    def __init__(
        self,
        session: DesignSession,
        new_markers: list[Marker],
        *,
        on_applied: Callable[[], None] | None = None,
        text: str = "Edit markers",
    ) -> None:
        super().__init__(text)
        self._session = session
        self._old = list(session.markers)
        self._new = list(new_markers)
        self._on_applied = on_applied

    def redo(self) -> None:
        self._session.set_markers(self._new)
        if self._on_applied is not None:
            self._on_applied()

    def undo(self) -> None:
        self._session.set_markers(self._old)
        if self._on_applied is not None:
            self._on_applied()


class SetLimitsCommand(QUndoCommand):
    def __init__(
        self,
        session: DesignSession,
        new_limits: list[LimitRegion],
        *,
        on_applied: Callable[[], None] | None = None,
        text: str = "Edit limits",
    ) -> None:
        super().__init__(text)
        self._session = session
        self._old = list(session.limits)
        self._new = list(new_limits)
        self._on_applied = on_applied

    def redo(self) -> None:
        self._session.set_limits(self._new)
        if self._on_applied is not None:
            self._on_applied()

    def undo(self) -> None:
        self._session.set_limits(self._old)
        if self._on_applied is not None:
            self._on_applied()
