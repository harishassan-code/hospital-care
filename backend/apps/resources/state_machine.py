"""A resource's status lifecycle: which action moves which status where. Shared by beds, blood units and later
equipment, operating rooms and ambulances (ADR-3, docs/architecture/resources.md)."""


class TransitionNotAllowed(Exception):
    """The action isn't allowed from the resource's current status. Views answer 409."""


class StateMachine:
    def __init__(self, noun: str, statuses, transitions: dict[tuple[str, str], str]):
        """`statuses` is the TextChoices class (for messages). Moves not in `transitions` are refused."""
        self.noun = noun
        self.statuses = statuses
        self.transitions = transitions
        self.actions = sorted({action for _, action in transitions})

    def next(self, status: str, action: str) -> str:
        try:
            return self.transitions[(status, action)]
        except KeyError:
            label = self.statuses(status).label.lower() if status in self.statuses.values else status
            raise TransitionNotAllowed(f"Can't {action} a {self.noun} that is {label}.") from None
