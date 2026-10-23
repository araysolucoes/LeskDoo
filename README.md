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
