import logging

import dns.exception
import dns.resolver
from django.utils import timezone

logger = logging.getLogger(__name__)


def verify_domain_ownership(tenant, timeout=5):
    """Checks the TXT record at tenant.dns_challenge_host for the expected
    ownership-proof token, and flips domain_verified on success.

    Never raises — DNS lookups are inherently flaky (propagation delays,
    misconfigured records, resolver timeouts), and the dashboard needs a
    friendly retry message in every failure case rather than a 500.

    Returns (success: bool, error_message: str | None).
    """
    if not tenant.custom_domain:
        return False, "Cadastre um domínio antes de verificar."

    host = tenant.dns_challenge_host
    try:
        resolver = dns.resolver.Resolver()
        resolver.timeout = timeout
        resolver.lifetime = timeout
        answer = resolver.resolve(host, "TXT")
    except dns.resolver.NXDOMAIN:
        return False, f"Nenhum registro TXT encontrado em {host}. Verifique se o DNS já propagou."
    except dns.resolver.NoAnswer:
        return False, f"O registro {host} existe mas não tem um valor TXT."
    except dns.resolver.NoNameservers:
        return False, "Não foi possível consultar o DNS desse domínio agora. Tente novamente em instantes."
    except dns.exception.Timeout:
        return False, "A consulta de DNS demorou demais. Tente novamente em instantes."
    except dns.exception.DNSException:
        logger.exception("Falha inesperada ao verificar domínio %s", tenant.custom_domain)
        return False, "Não foi possível verificar o domínio agora. Tente novamente em instantes."

    found_values = {
        b"".join(rdata.strings).decode("utf-8", errors="ignore") for rdata in answer
    }
    if tenant.domain_verification_token not in found_values:
        return False, "O registro TXT encontrado não confere com o token esperado."

    tenant.domain_verified = True
    tenant.domain_verified_at = timezone.now()
    tenant.save(update_fields=["domain_verified", "domain_verified_at"])
    return True, None
