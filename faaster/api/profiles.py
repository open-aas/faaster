"""
Perfis de serviço (Service Specification Profiles) declarados em /description.

IDTA-01002-3-2 §Service Specifications and Profiles. Os identificadores
incluem major e minor da versão da API.
"""

_BASE = "https://admin-shell.io/aas/API/3/2"

AAS_REPOSITORY_READ = f"{_BASE}/AssetAdministrationShellRepositoryServiceSpecification/SSP-002"
SUBMODEL_REPOSITORY_READ = f"{_BASE}/SubmodelRepositoryServiceSpecification/SSP-002"

# Perfis implementados por este servidor
IMPLEMENTED_PROFILES = [
    AAS_REPOSITORY_READ,
    SUBMODEL_REPOSITORY_READ,
]
