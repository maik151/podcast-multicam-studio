"""
Excepciones de negocio y dominio para Podcast Multicam Studio.
"""

class StudioDomainException(Exception):
    """Excepción base del dominio."""
    pass

class RecordingAlreadyActiveException(StudioDomainException):
    """Se intenta iniciar una toma cuando ya hay una en curso."""
    pass

class NoActiveRecordingException(StudioDomainException):
    """Se intenta escribir o detener sin una toma activa."""
    pass

class PortConflictException(StudioDomainException):
    """El puerto de comunicación no pudo ser liberado."""
    pass

class CertificateGenerationException(StudioDomainException):
    """Fallo en la generación o carga del certificado X.509."""
    pass
