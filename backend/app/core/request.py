from ipaddress import ip_address, ip_network

from fastapi import Request

from app.core.config import get_settings


def client_ip(request: Request) -> str | None:
    if request.client is None:
        return None
    connection_ip = request.client.host
    if not _is_trusted_proxy(connection_ip):
        return connection_ip

    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        forwarded_ip = _client_ip_from_forwarded_for(forwarded_for)
        if forwarded_ip:
            return forwarded_ip

    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip() or connection_ip

    return connection_ip


def _client_ip_from_forwarded_for(value: str) -> str | None:
    forwarded_chain = [item.strip() for item in value.split(",") if item.strip()]
    for forwarded_ip in reversed(forwarded_chain):
        if not _is_valid_ip(forwarded_ip):
            continue
        if not _is_trusted_proxy(forwarded_ip):
            return forwarded_ip
    return forwarded_chain[0] if forwarded_chain else None


def _is_trusted_proxy(connection_ip: str) -> bool:
    trusted_hosts = {host.strip() for host in get_settings().trusted_proxy_hosts}
    if connection_ip in trusted_hosts:
        return True

    try:
        address = ip_address(connection_ip)
    except ValueError:
        return False

    for trusted_host in trusted_hosts:
        try:
            if address in ip_network(trusted_host, strict=False):
                return True
        except ValueError:
            continue
    return False


def _is_valid_ip(value: str) -> bool:
    try:
        ip_address(value)
    except ValueError:
        return False
    return True
