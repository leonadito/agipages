from functools import lru_cache
from ipaddress import ip_address, ip_network

from django.conf import settings


@lru_cache(maxsize=8)
def _trusted_networks(cidrs):
    return tuple(ip_network(cidr, strict=False) for cidr in cidrs)


def _is_trusted_proxy(remote_addr, cidrs):
    try:
        addr = ip_address(remote_addr)
    except ValueError:
        return False
    return any(addr in network for network in _trusted_networks(cidrs))


class TrustedProxyClientIPMiddleware:
    """Troca REMOTE_ADDR pelo IP real do visitante quando a requisição vem
    do proxy reverso (Traefik).

    Em produção o Traefik roda com network_mode: host e alcança o container
    pela porta publicada em 127.0.0.1, então o Django sempre vê o gateway da
    rede Docker (ex.: 172.20.0.1) como REMOTE_ADDR. Sem esta troca, todo
    visitante parece ter o mesmo IP: o @ratelimit(key="ip") do formulário
    público vira um limite global, Lead.ip_address fica inútil e o Meta CAPI
    recebe um client_ip_address errado.

    O Traefik descarta X-Real-Ip/X-Forwarded-For vindos do cliente e grava o
    IP real em X-Real-Ip (conferido em produção com cabeçalhos forjados).
    Mesmo assim o cabeçalho só é aceito quando REMOTE_ADDR está em
    settings.TRUSTED_PROXY_CIDRS; fora disso (dev, ou acesso que não passa
    pelo proxy) REMOTE_ADDR fica como está. Precisa ser o primeiro
    middleware, antes de qualquer coisa que leia o IP."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        cidrs = tuple(getattr(settings, "TRUSTED_PROXY_CIDRS", ()))
        real_ip = request.META.get("HTTP_X_REAL_IP", "").strip()
        if cidrs and real_ip and _is_trusted_proxy(request.META.get("REMOTE_ADDR", ""), cidrs):
            try:
                ip_address(real_ip)
            except ValueError:
                pass
            else:
                request.META["REMOTE_ADDR"] = real_ip
        return self.get_response(request)
