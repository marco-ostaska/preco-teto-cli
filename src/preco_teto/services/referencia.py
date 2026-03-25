from dataclasses import dataclass
from preco_teto.services import banco_central

FED_FUNDS_US = 5.25  # atualizar manualmente quando Fed mudar
CPI_US = 3.1         # atualizar manualmente quando necessário


@dataclass
class IndicesBR:
    cdi: float | None
    ipca: float | None
    melhor_indice: float | None  # max(cdi * 0.85, ipca + 2.0)


@dataclass
class IndicesUS:
    fed_funds: float
    cpi: float


def fetch_indices_br() -> IndicesBR:
    cdi = banco_central.fetch_cdi()
    ipca = banco_central.fetch_ipca()
    melhor = banco_central.melhor_indice_br(cdi, ipca)
    return IndicesBR(cdi=cdi, ipca=ipca, melhor_indice=melhor)


def fetch_indices_us() -> IndicesUS:
    return IndicesUS(fed_funds=FED_FUNDS_US, cpi=CPI_US)
