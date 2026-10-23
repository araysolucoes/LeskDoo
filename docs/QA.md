# QA, CI/CD e comandos — LeskDoo

## Rotina local (Windows PowerShell)
```powershell
git fetch origin
git switch --track origin/dev     # apenas na primeira vez; caso dev local já exista: git switch dev
git pull --ff-only origin dev
py -3.12 -m venv .venv            # somente na primeira vez
.\.venv\Scripts\Activate.ps1
.\scripts\qa.ps1 -Install -Coverage
```

Depois da instalação inicial basta ` .\scripts\qa.ps1 -Coverage `.

## Comandos individuais
```powershell
python -m pytest -q
python -m pytest tests/test_api.py -vv
python -m pytest -q --cov=leskdoo --cov-report=html
python -m compileall -q leskdoo tests run.py
python -m ruff check --select E9,F63,F7,F82 leskdoo tests run.py
python scripts/check_yaml.py
git status --short
git branch -vv
```

## GitHub Actions

- **QA:** executa em push, PR e manualmente; matriz Ubuntu/Windows com Python 3.12 e 3.13; compileall, lint crítico, testes, cobertura, sintaxe YAML, Docker Compose config e artefatos de testes.
- **Dependency security:** verifica vulnerabilidades publicadas em dependências Python nos PRs, alterações de requirements, semanalmente e sob demanda.
- **VM end-to-end:** intencionalmente não acionado pelo CI público; executar somente no Windows 11 autorizado com VirtualBox e recursos disponíveis.

Os workflows são verificações de qualidade de código, não prova de instalação correta do Ubuntu/Zabbix/Ollama. Adoção obrigatória como branch protection deverá ser configurada no GitHub após a primeira execução bem-sucedida.

## Política
- Branch `dev`: desenvolvimento e validação automática.
- Branch `hml`: revisão/validação no PC Windows real (quando criada).
- Branch `main`: código aprovado e pronto para distribuição.
- Não versionar segredos nem `.env`; não rodar criação/destruição de VMs em runners públicos.

> A checagem obrigatória usa apenas erros críticos de sintaxe e nomes. O projeto possui dívida de estilo no código anterior; regras mais amplas serão ativadas após formatação.
