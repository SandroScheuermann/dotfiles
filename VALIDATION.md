# Validação da entrega — 2026-10-20

**Implementação preparada e testes isolados aprovados, com limites explícitos.**
Não foi executado provisionamento real no sistema de origem.

## Resultados

| Verificação | Resultado / escopo |
|---|---|
| Testes locais | 40/40 aprovados |
| Testes no container | 37 aprovados; 3 skips esperados: Git index e 2 testes Chezmoi, já cobertos no host |
| Sintaxe Python | AST dos 7 arquivos Python de implementação/testes, sem gerar bytecode |
| Shell | `bash -n` em 10 scripts ativos; ShellCheck warning/error aprovado no container |
| Fish/Zsh | Sintaxe de 5 arquivos Fish e 1 Zsh renderizados, sem carregar a sessão original |
| Node | `node --check` em 144 fontes CJS/MJS renderizadas; código não executado |
| YAML | PyYAML + yamllint estrito nos manifestos/perfis/playbooks/configuração de lint |
| JSON renderizado | 25 documentos analisados, incluindo Waybar |
| Chezmoi | 539 arquivos no render completo; perfis mínimo/laptop e completo/desktop renderizados e reaplicados em diretórios temporários |
| Recursos | Imports CSS e referências locais do desktop verificadas; temas dependentes do Waybar incluídos |
| Ansible | `--syntax-check`, `--check`, aplicação simulada e segunda execução com `changed=0` no role de pacotes |
| Segurança | Árvore e blobs reais staged verificados; testes de credenciais sintéticas, symlinks, conflitos, TOCTOU, permissões e recuperação |
| Exclusões | Chromium, Firefox, Spotify GUI/CLI e Steam não reaparecem na seleção |

O container foi descartável, com filesystem read-only, projeto montado read-only,
sem HOME pessoal, Docker socket, privilégios/capabilities extras ou acesso a arquivos
de autenticação. Somente seu tmpfs foi gravável. Ferramentas foram instaladas nele,
nunca no host. A imagem `python:3.13-slim` já estava em cache; não houve pull.

Os dois testes Chezmoi foram executados no host com config, estado, cache e destino
temporários exclusivos. Não se executou `chezmoi apply` contra o HOME atual.

O teste de idempotência Ansible usa um executável pacman falso em PATH dentro do
container, gravando apenas uma fixture temporária. Check mode não alterou essa
fixture; a primeira aplicação adicionou somente o pacote ausente; a segunda foi
idempotente. As tarefas systemd foram verificadas sintaticamente, mas **não houve
teste funcional ou de idempotência de serviços reais**.

## Pacotes e fontes

Na consulta às bases locais, o plano completo do CachyOS/Intel selecionou:

- 234 pacotes: 229 de repositório, 4 candidatos AUR e 1 com origem pendente.
- Os 229 de repositório tinham metadados locais de disponibilidade.
- 232 dos 234 já estavam instalados. Bun e uv continuam ausentes como pacotes,
  embora seus executáveis manuais existam; nenhuma instalação foi feita.
- Consulta RPC AUR encontrou Android Studio, debtap, Twingate e python-ewmh;
  não encontrou `slack-desktop-wayland`.

Não houve refresh das bases, atualização, build AUR ou instalação real. Metadados
locais não garantem disponibilidade futura nos mirrors. Dependências transitivas,
conflitos de transação e PKGBUILDs precisam de validação real no destino/VM.
Pacman verificou integridade do banco local durante a auditoria, sem erros.

Ferramentas manuais e plugins `@latest` permanecem sem fixação integral. Presença
na origem não foi confundida com reprodutibilidade. Veja `inventory/manual.yml`.

## Preservação conferida

- Pacman permaneceu com **1.278 instalados e 226 explícitos**, como na auditoria.
- Os conjuntos de unidades habilitadas permaneceram iguais à captura:
  **25 de sistema e 6 de usuário**.
- Arquivos rastreados do repositório original de dotfiles continuaram sem alterações.
- Nenhum pacote foi removido, instalado ou atualizado no host; nenhum serviço foi
  habilitado/desabilitado/reiniciado pela implementação.
- Nenhum arquivo de configuração ativo foi aplicado ou substituído. As escritas
  da implementação ficaram no novo projeto; testes usaram diretórios temporários.
- Nenhum push foi executado, nem histórico/remote do repositório anterior importado.

Isso é uma conferência direcionada, não um snapshot criptográfico de todo o sistema.

## Não comprovado nesta entrega

- Instalação completa em VM Arch/CachyOS limpa: não havia VM apropriada; não foi
  criada nem instalado QEMU no host. O container Debian/Python não substitui isso.
- Inicialização real de Hyprland, parsers nativos de todos os componentes gráficos,
  pixel-perfect do prompt, login/lock/fingerprint, áudio/Bluetooth, hotplug de
  monitores, suspensão e comportamento térmico/energético em outro hardware.
- Seleção automática completa de drivers AMD/NVIDIA ou configuração de repos CPU-v3/v4.
- Migração de banco dconf global ou dados pessoais de rede/Bluetooth/biometria.
- Compilação e segurança das fontes AUR, restauração integral de Slack, Codex,
  herdr, rtk, Minzi, Rust/Android SDK e funcionamento dos plugins importados.
- Ausência matemática de segredos: scanner é heurístico e requer revisão humana
  antes de publicar. Histórico Git externo não foi auditado nem copiado.

## Repetir os testes

```bash
python3 -B scripts/validate.py
python3 -B scripts/validate.py --isolated
```

O segundo comando usa rede somente para ferramentas de teste no container. Falta
de Docker/imagem em cache/ferramentas é relatada, nunca resolvida instalando no host.

Antes de uma restauração real, confira `--dry-run`, execute `--check` com as
ferramentas presentes e resolva as fontes pendentes, ou aceite conscientemente
`--skip-unresolved` como restauração parcial. Backups e recuperação não são rollback
de pacotes, serviços ou atualizações de sistema.
