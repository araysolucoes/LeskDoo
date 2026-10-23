# LeskDoo — Aray Soluções

Gerenciador local de VirtualBox para Windows 11 com inventário, recomendações e provisionamento inicial de Ubuntu Server 24.04.

## V002 (branch dev, em revisão)

- Dashboard redesenhado com cards de hardware, VM, armazenamento e estado dos jobs.
- Assistente **Nova máquina virtual**, com nome, usuário Linux, RAM, vCPU, disco, volume, porta NAT e chave pública SSH.
- Job registrado em PostgreSQL com estados queued/running/created/error/interrupted.
- Download de imagem Ubuntu 24.04 VMDK com checagem SHA256, criação de VDI, ISO NoCloud, configuração de rede NAT e inicialização no VirtualBox.
- As VMs preexistentes são apenas listadas, nunca apagadas pelo provisionador.
- Instaladores automáticos de Zabbix, Ollama e Open WebUI **ainda não implementados**. Estado created significa VM iniciada, não sistema operacional ou SSH validados.

### Requisitos

Windows 11, Python 3.12+, Oracle VirtualBox com VBoxManage e PostgreSQL acessível.

```powershell
git fetch origin
git switch dev
git pull --ff-only origin dev
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Inicie PostgreSQL (por exemplo, `docker compose --env-file .env -f deploy/compose.postgres.yml up -d` após configurar POSTGRES_PASSWORD), e defina DATABASE_URL com os mesmos dados.

Para chave SSH pública:
```powershell
ssh-keygen -t ed25519 -f "$env:USERPROFILE\.ssh\leskdoo" -C "leskdoo"
Get-Content "$env:USERPROFILE\.ssh\leskdoo.pub"
```

No `.env`, configure `LESDKOO_ALLOW_MUTATIONS=true` **somente em uma instância local de confiança**. Suba com `python run.py` e acesse http://127.0.0.1:5050.

**Atenção:** esta é uma versão de desenvolvimento, sem controle de sessão autenticada, fila persistente de trabalhadores ou CSRF completo. Não publique o painel na internet ou LAN. As operações de provisionamento são reais, mas ainda não foram validadas num host Windows físico com VirtualBox. Confirme snapshots/backups antes de testar. Ao reiniciar a aplicação um job interrompido não é reexecutado automaticamente.

Próximos passos: validar instalação, descobrir IP/SSH, finalizar Docker/Zabbix/Ollama e healthchecks, gerenciar recovery e aprimorar segurança.

Consultar [Roadmap](docs/ROADMAP.md).


## V002 — instalação de serviços (branch dev)

Depois que o job de criação estiver no estado `created`, clique em **Instalar Zabbix + IA** na seção Provisionamentos. Informe o mesmo usuário SSH, a porta NAT, o caminho completo para a chave privada SSH do Windows e a pasta da VM.

A instalação realiza cloud-init status, instala Docker, sobe os contêineres PostgreSQL (Zabbix), Zabbix Server, Zabbix Web, Zabbix Agent2, Ollama e Open WebUI e solicita o modelo `qwen2.5:1.5b`. Requer acesso à internet na VM.

Acessos previstos **no próprio Windows host**, por NAT:
- Zabbix: http://127.0.0.1:18080
- Chat: http://127.0.0.1:13000
- SSH: 127.0.0.1:2222 (ou porta configurada)

O Zabbix possui credenciais iniciais padronizadas pelo próprio produto; altere-as no primeiro acesso. O Open WebUI permite cadastro inicial para criar o primeiro administrador: desative novos cadastros após essa etapa. **Não exponha o ambiente externamente sem autenticação forte, TLS e hardening.**

### Limitações importantes
1. O provisionamento ainda não foi testado fisicamente no Windows 11 do usuário. Concluído no código não significa instalação validada.
2. A fila de execução roda em threads do Flask. Reiniciar o servidor interrompe jobs em andamento; o estado fica `interrupted` em PostgreSQL. O operador precisa inspecionar VM e volumes antes de tentar novamente.
3. Não existem ainda rollback automatizado, limpeza guiada, backup nem monitoramento Zabbix de métricas específicas da IA. O banco registra progresso, mas ainda não implementa CRUD completo.
4. O download da imagem Ubuntu é validado por SHA256 publicado pelo mesmo servidor Ubuntu. A assinatura criptográfica do manifesto não é verificada.
5. O `services_started` confirma execução dos comandos Compose e pull do modelo, **não a prontidão HTTP nem teste de inferência end-to-end**.
6. Não habilite `LESDKOO_ALLOW_MUTATIONS=true` caso outros usuários não confiáveis possam acessar o host ou a aplicação.

### Observação sobre Zabbix
A instalação usa imagens Zabbix 7.4 em Docker Compose, compatíveis com a linha documentada pelo projeto oficial. Os contêineres podem requerer tempo adicional para inicialização do esquema PostgreSQL.
