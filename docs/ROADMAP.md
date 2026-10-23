# Roadmap LeskDoo

## P0 — Inventário e segurança (base entregue)
- [x] Dashboard Flask local com inventário CPU, RAM, GPU, volumes, rede e VMs
- [x] Detectar VirtualBox e listar bridges / VMs ativas ou paradas
- [x] Recomendar CPU, RAM e volume com reservas conservadoras
- [x] Botões ligar/desligar ACPI, bloqueados por padrão
- [x] Modelo SQLAlchemy PostgreSQL (ainda não integrado ao fluxo de criação)
- [ ] Autenticação de administrador e proteção CSRF para mutações
- [ ] Serviço Windows e logs estruturados

## P1 — Provisionamento
- [ ] Descoberta de SSD/NVMe por volume via WMI e checagem de espaço reservado
- [ ] Wizard de criação com dry-run / confirmação
- [ ] Baixar e verificar checksums Ubuntu Cloud Image
- [ ] Cloud-init NoCloud por ISO e criação de VM idempotente
- [ ] Ponte Ethernet ou NAT selecionável; teste de rede, SSH e identidade SSH
- [ ] SSH por chave e segredos com DPAPI/Windows Credential Manager
- [ ] Job queue persistente / retries / rollback e auditoria no PostgreSQL

## P2 — Serviços
- [ ] Instalar Docker e validar Compose via SSH
- [ ] Instalar Zabbix com templates oficiais e agente no guest
- [ ] Instalar Ollama e puxar modelo compatível com a memória livre
- [ ] Integrar Open WebUI e fazer healthchecks; listar URLs acessíveis
- [ ] Criar indicadores IA no Zabbix (CPU/RAM, disponibilidade, latência e logs)

## P3 — Operação
- [ ] CRUD da metadata de VMs e lifecycle seguro: start, shutdown, delete com confirmação forte
- [ ] Controles de container separado da VM, sem desligar guest
- [ ] Atualizar serviços, snapshots, backup, restauração e testes em Windows real
- [ ] CI com testes e validação das configurações YAML

### Critérios de segurança
- Bind dashboard em 127.0.0.1 por padrão; sem exposição LAN sem autenticação e TLS.
- Nunca persistir senhas ou chaves SSH em texto puro no banco; apenas referências a cofre.
- Guardrails para impedir provisionamento que esgote RAM/disco do host.
- Evitar `poweroff` forçado: priorizar ACPI, reportar timeout, pedir confirmação adicional.
- Fechar a interface não desliga VMs; lifecycle de processos web e VMs independente.
