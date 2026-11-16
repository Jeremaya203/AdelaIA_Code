"""Límite de peticiones por IP (ventana fija, en memoria, sin dependencias).

Regla 45: sin límite no se expone a red abierta; cada consulta gasta
Groq+Jina. Solo cubre POST /api/query; /api/health queda libre.
"""
import threading
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Ventana fija de `max_req` peticiones por `ventana_s` segundos e IP."""

    def __init__(self, app, max_req: int = 30, ventana_s: int = 60):
        super().__init__(app)
        self.max_req = max_req
        self.ventana_s = ventana_s
        self._candados = threading.Lock()
        self._ventanas: dict[str, list[float]] = {}

    def _permitir(self, ip: str, ahora: float) -> tuple[bool, int]:
        with self._candados:
            marcas = [m for m in self._ventanas.get(ip, [])
                      if ahora - m < self.ventana_s]
            if len(marcas) >= self.max_req:
                reintento = int(self.ventana_s - (ahora - marcas[0])) + 1
                self._ventanas[ip] = marcas
                return False, reintento
            marcas.append(ahora)
            self._ventanas[ip] = marcas
            return True, 0

    async def dispatch(self, request, call_next):
        if request.url.path != "/api/query" or request.method != "POST":
            return await call_next(request)
        ip = request.client.host if request.client else "?"
        ok, reintento = self._permitir(ip, time.monotonic())
        if not ok:
            return JSONResponse(
                {"detail": "Límite de consultas excedido; reintente."},
                status_code=429,
                headers={"Retry-After": str(reintento)},
            )
        return await call_next(request)
