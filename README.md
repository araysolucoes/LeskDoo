# LeskDoo

Projeto da Aray Soluções para inventariar Windows 11, gerenciar VirtualBox e provisionar Ubuntu Server com Zabbix e Ollama.

## Estado: V001 (base inicial)

A base executável inicial foi preparada para importação no repositório. Inclui dashboard Flask local, inventário de CPU/RAM/GPU/discos/adaptadores, listagem de VMs e bridges VirtualBox, recomendação conservadora de recursos, e comandos start/shutdown ACPI desabilitados por padrão. A versão completa dos arquivos encontra-se no pacote LeskDoo-V001.zip fornecido na conversa de planejamento.

**Importante:** ainda não provisiona Ubuntu, não instala Zabbix/Ollama e não tem autenticação/CSRF. Não exponha a interface na rede.

## Arquitetura planejada

- Host: Windows 11, Python, Flask, VBoxManage
- VM: Ubuntu Server 24.04 LTS, cloud-init, SSH por chave, Docker Compose
- Monitoramento: Zabbix Server/Agent
- IA: Ollama CPU-first, Open WebUI
- Persistência: PostgreSQL e referências a credenciais em cofre seguro

## Fases

1. P0: inventário, dashboard, recomendações e segurança da API
2. P1: criação idempotente de VMs Ubuntu, rede NAT/bridge, cloud-init e SSH
3. P2: deploy Zabbix, Ollama e Open WebUI
4. P3: operações CRUD e lifecycle, backups, logs e testes de integração

O desenvolvimento deve ser validado num host Windows 11 com VirtualBox instalado antes de ser considerado pronto para produção.
