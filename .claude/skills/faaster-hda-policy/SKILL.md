---
name: faaster-hda-policy
description: Use ao configurar historização (HDA) de variáveis no modelo AAS via extensions faaster:hda:*, ou ao alterar faaster/hda/ (políticas, manager, storage TimescaleDB).
---
# Políticas HDA no modelo AAS

A política é declarada como `extensions` na **Property com `category: "VARIABLE"`**. Sem `faaster:hda:*` → não historiza. Código de referência: `faaster/hda/policies.py` (`extract_policy`, `AggregationPolicy`).

## Modo sample (padrão) — hypertable raw + continuous aggregates
```json
"extensions": [
  {"name": "faaster:hda:mode", "value": "sample"},
  {"name": "faaster:hda:levels", "value": "1min,1hour,1day"},
  {"name": "faaster:hda:sample_interval", "value": "1"},
  {"name": "faaster:hda:retention:raw", "value": "30 days"},
  {"name": "faaster:hda:retention:1min", "value": "1 year"}
]
```
Padrões: levels `1min,1hour,1day`; retenção raw 30 days, 1min 1 year, 1hour 5 years, 1day sem expiração. Cria nós virtuais `Value@<level>`.

## Modo aggregate — buffer em memória, 1 registro por janela (ex.: ANEEL 15 min)
```json
"extensions": [
  {"name": "faaster:hda:mode", "value": "aggregate"},
  {"name": "faaster:hda:window", "value": "15min"},
  {"name": "faaster:hda:function", "value": "mean"},
  {"name": "faaster:hda:retention", "value": "5 years"}
]
```
Funções: `mean | sum | max | min | last`.

Janelas válidas (ambos os modos): `1min, 5min, 10min, 15min, 1hour, 1day` (`_WINDOW_SECONDS`). Para adicionar uma janela, altere esse dicionário e cubra em `tests/unit/test_hda_policies.py`.

## Rodando
```bash
docker compose -f docker-compose-dev.yaml up   # requer: docker network create faaster-network
python server.py -m models/x.json --url-database postgresql://faaster:faaster@localhost:5432 --db-backend timescaledb --db-name x_001
```

## Novo backend
Implemente `IHDAStorage` (ver `faaster/interfaces/ihda.py` e `infra/database_timescale.py`) e registre em `faaster/hda/factory.py`. Não importe a implementação concreta fora da factory/container.
