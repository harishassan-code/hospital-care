"""Puts the city clock on every API response (B21): X-City-Time (ISO 8601), X-City-Mode (live, paused,
fastForward) and X-City-Speed, so the site shows the same time as the data. Only while the simulation is
enabled; otherwise the headers are left off and screens use the device's clock."""

from django.conf import settings

from . import clock


class CityClockMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if settings.SIMULATION_ENABLED and request.path.startswith("/api/"):
            reading = clock.reading()
            if reading.enabled:
                response["X-City-Time"] = clock.now().isoformat()
                response["X-City-Mode"] = reading.mode
                response["X-City-Speed"] = f"{reading.speed:g}"
        return response
