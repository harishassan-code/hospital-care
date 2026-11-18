"""How a new notification reaches a person. `notify` hands each new row to every channel in CHANNELS. Email or
SMS is one new subclass and one entry in CHANNELS (bolt B06, non-goals)."""

from .models import Notification


class Channel:
    def send(self, notification: Notification) -> None:
        """Deliver one new notification. Called inside the domain move's transaction, so keep it cheap."""
        raise NotImplementedError


class InAppChannel(Channel):
    """The stored row is the delivery: the bell and the alerts page read it. Nothing more to do."""

    def send(self, notification: Notification) -> None:
        return None


CHANNELS: tuple[Channel, ...] = (InAppChannel(),)
