---
inclusion: always
---
# Produto — Faaster

**Faaster** (*Faster Asset Administration Shell Type 2 over OPC UA*) é um framework Python que publica automaticamente um **AAS Reativo (Tipo 2)** sobre **OPC UA** a partir de um modelo AAS V3 serializado (JSON, XML ou AASX).

## O que ele faz
1. Carrega e valida o modelo AAS V3 (Pydantic + constraints AASd-*).
2. Gera o address space OPC UA (AAS/Submodel/Collection → Object, Property → Variable, Operation → Method).
3. Habilita Historical Data Access (HDA) em TimescaleDB, guiado por políticas declaradas no próprio modelo (`faaster:hda:*`).
4. Carrega extensões de submodelo (`sources/`) que conectam dispositivos físicos (MQTT, Modbus, HTTP…) às variáveis OPC UA e implementam Operations.
5. Segurança OPC UA (PKI X.509, políticas Basic256Sha256/Aes128/Aes256) e integração com LDS/GDS (OPC 10000-12 §6–7).

## Contexto
- Projeto acadêmico (mestrado, UFAM), licença Apache-2.0, versão alpha (`1.0.0a2`).
- Caso validado: monitoramento energético de motor trifásico (ESP32 + ADE9000 via MQTT) no submodelo `ConditionMonitoring`.
- Diferenciais frente a AASX Server, BaSyx, FA³ST, NOVAAS: HDA integrado e orientado a política + extensões por script.

## Roadmap (pendente)
ObjectTypes/Interfaces semânticos OPC UA; SDK de drivers de sensor; eventos a partir de `Range`/`BasicEventElement`; ML na borda; escala horizontal; backend HDA MongoDB.
