"""
aws_client.py
Helper centralizado para crear clientes boto3 con soporte para entornos
corporativos con proxies SSL que interceptan tráfico HTTPS.

Configuración (variables de entorno):
    AWS_CA_BUNDLE   — ruta al bundle de certificados corporativos (recomendado)
    AWS_SSL_VERIFY  — "false" para deshabilitar verificación SSL (solo desarrollo)
"""
import os
import warnings
import boto3

def _ssl_verify():
    """
    Determina el parámetro verify para boto3.
    Prioridad: AWS_CA_BUNDLE > AWS_SSL_VERIFY=false > True (default seguro)
    """
    ca_bundle = os.environ.get("AWS_CA_BUNDLE", "")
    if ca_bundle:
        return ca_bundle

    if os.environ.get("AWS_SSL_VERIFY", "").lower() == "false":
        warnings.warn(
            "SSL verification disabled (AWS_SSL_VERIFY=false). "
            "Use only in development environments.",
            stacklevel=3,
        )
        return False

    return True


def s3(region_name: str = None):
    """Crea un cliente S3 con configuración SSL del entorno."""
    kwargs = {"verify": _ssl_verify()}
    if region_name:
        kwargs["region_name"] = region_name
    return boto3.client("s3", **kwargs)


def athena(region_name: str = None):
    """Crea un cliente Athena con configuración SSL del entorno."""
    kwargs = {"verify": _ssl_verify()}
    if region_name:
        kwargs["region_name"] = region_name
    return boto3.client("athena", **kwargs)
