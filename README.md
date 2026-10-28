# Ambiente portátil Arch/CachyOS + Hyprland

Restauração seletiva com **Chezmoi + Ansible**, sem exportar indiscriminadamente
o diretório pessoal. O comando padrão **somente mostra um plano**.

> Este repositório foi preparado separadamente do ambiente original. Não foi
> aplicado ao sistema de origem. Não é instalador de sistema operacional nem
> ferramenta de particionamento. Use a aplicação inicialmente numa máquina
> descartável ou de destino, nunca como teste sobre sua instalação funcional.

## O que foi aprovado

- Manter todos os componentes restantes, conforme a decisão final da curadoria.
- Excluir da futura restauração: `chromium`, `firefox`, `spotify-launcher`,
  `spotify_player` (Cargo) e `steam`. Nada é desinstalado.
- Preservar Fish como shell atual, Zsh disponível e a configuração/aparência do
  prompt, sem trocar automaticamente o shell de login.
- Manter aplicativos, desenvolvimento, Hyprland, atalhos, temas, fontes e scripts
  em módulos, sem exigir que todos sejam instalados no perfil mínimo.
- Hardware, boot e serviços têm políticas próprias; aprovação para manter um
  pacote não significa habilitar todos os serviços relacionados.

O registro está em `inventory/decisions.yml`; `inventory/installed.json` contém
metadados dos 1.278 pacotes auditados. Os manifestos selecionáveis têm 251 entradas,
incluindo dependências de execução e ferramentas Bun/uv obtidas dos repositórios,
em vez de copiar executáveis pessoais. No hardware/CachyOS de origem, o mínimo
seleciona 73 pacotes e o completo 234, sem os 17 pacotes do módulo de boot.

## Requisitos e primeiro uso

O destino deve ter Arch/CachyOS x86_64 já instalado, usuário normal, Bash, Python 3,
pacman funcional, repositórios apropriados e acesso sudo para provisionamento.
Não execute o bootstrap inteiro como root. Repositórios CachyOS e otimizações
CPU-v3/v4 **não são adicionados automaticamente**.

Depois de obter e revisar este repositório, execute dentro dele:

```bash
# Seguro: inventário/plano, sem criar cache, instalar ou acessar a rede.
./bootstrap.sh --dry-run --profile auto --preset minimal
```

**Somente na máquina de destino**, um comando provisiona o perfil mínimo:

```bash
./bootstrap.sh --apply --profile auto --preset minimal --install-prerequisites --services
```

`--install-prerequisites` autoriza instalar ferramentas ausentes via pacman,
sem atualizar silenciosamente as bases. Falta de conectividade, bases antigas ou
pacotes indisponíveis interrompe a operação. Execute a atualização completa do
sistema conscientemente, se necessária; nunca faça atualização parcial com `-Sy`.

SDDM é habilitado, mas não iniciado por este comando. Se já houver outro display
manager ou backend de rede ativo conflitante, o bootstrap interrompe, sem desativá-lo.
Selecione a sessão Hyprland no próximo login/reinício apropriado.

## Seleção e perfis

```bash
./bootstrap.sh --list-components
./bootstrap.sh --preset full --dry-run
./bootstrap.sh --preset minimal --with dev,android --dry-run
./bootstrap.sh --preset full --without android,work,compatibility --dry-run
./bootstrap.sh --profile desktop --preset minimal --dry-run --json
```

| Componente | Conteúdo principal |
|---|---|
| `core`, `shell`, `desktop` | Base mínima, editores/arquivos/Git, Kitty/Fish/Zsh, sessão Hyprland |
| `apps`, `work`, `remote` | Aplicativos, comunicação/VPN e acesso remoto |
| `dev`, `android` | Linguagens, containers, ferramentas e Android Studio |
| `network`, `graphics`, `visuals` | Rede, integração gráfica, fontes/ícones |
| `cpu-intel`, `gpu-intel` | Ajustes e drivers condicionais Intel |
| `storage`, `extras`, `compatibility` | Utilitários e pacotes preservados, incluindo órfãos |
| `boot` | Pacotes relacionados a kernel/boot; sempre fora do padrão |

O completo seleciona todos os módulos, exceto boot, respeitando as condições de
hardware/distribuição. Dependências são resolvidas pelo pacman. Órfão no banco não
é sinônimo de dispensável: `qt6-wayland` foi tratado como dependência de execução
do desktop; os demais estão separados em `compatibility`. Nenhuma limpeza ocorre.

`android` requer `dev`; `desktop` requer `core` e `shell`. Overrides não podem
reintroduzir exclusões anteriores nem retirar dependências de execução essenciais.
Boot exige **ambos** `--allow-boot --with boot`; mesmo assim, não há instalação de
bootloader, particionamento, cópia de fstab/UUIDs ou clonagem de initramfs.

### Hardware e overrides locais

Detectam-se classe desktop/laptop, bateria, backlight e CPU/GPU Intel, sem usar
identificadores pessoais. A configuração de monitores é genérica por padrão.
O exemplo opt-in `profiles/elitebook-example.json` preserva eDP-1 1920×1200 a 60 Hz,
escala 1,5 e a opção de autenticação por impressão digital. Nenhum cadastro
biométrico é transferido; é necessário reinscrever a digital no destino.

Crie seu `overrides.local.json` (ignorado pelo Git):

```json
{
  "profile": "laptop",
  "monitors": ["eDP-1,1920x1200@60,0x0,1.5", ",preferred,auto,1"],
  "keyboard_layout": "us",
  "keyboard_variant": "intl",
  "fingerprint": false,
  "suspend": true,
  "components_remove": ["android"],
  "packages_add": [],
  "packages_remove": []
}
```

```bash
./bootstrap.sh --overrides overrides.local.json --dry-run
```

Precedência: padrões/perfil detectado → override local → perfil explícito na CLI.
AMD e NVIDIA não têm seleção automática completa de drivers nesta versão; use
overrides revisados. Módulos bateria/brilho desaparecem do Waybar quando o recurso
não existe. Atalhos não fixam mais `WAYLAND_DISPLAY=wayland-1`.

`~/.config/hypr/local.conf` é criado apenas se ausente e preservado nas próximas
execuções. Pode sobrescrever ajustes do Hyprland. Não existe reload automático.
Identidade e preferências pessoais do Git podem ir em
`~/.config/git/local.conf`, que não é capturado pelo repositório.

## Check, aplicação e reexecução

```bash
# Requer ferramentas já disponíveis. Renderiza só em área isolada em .state/.
# Mostra nomes/status, nunca conteúdo de arquivos nem valores sensíveis.
./bootstrap.sh --check --preset minimal

# Aplicação real: somente no destino e depois da revisão do plano/check.
./bootstrap.sh --apply --preset minimal
```

- `--dry-run` não renderiza templates, não cria estado e não instala nada.
- `--check` usa Chezmoi com destino/config/cache/estado isolados, compara arquivos
  e executa Ansible check mode quando disponível. Pode criar somente estado local
  do projeto; não aplica configurações nem serviços.
- `--apply` instala apenas pacotes ausentes, sem remoções. Não força atualização
  de versões já presentes; atualização completa exige `--upgrade-system` explícito.
  Essa atualização usa os prompts do pacman e pode envolver substituições próprias
  da distribuição; não é um rollback transacional.
- `--packages-only` e `--dotfiles-only` permitem restauração separada.
- Arquivos existentes diferentes bloqueiam a aplicação por padrão. Somente
  `--replace-existing` autoriza backup e substituição dos arquivos gerenciados.
- Symlinks nos caminhos gerenciados são recusados; alterações entre planejamento
  e escrita também bloqueiam. Escritas usam substituição atômica por arquivo.
- Não é transação global: se uma etapa falhar, pacotes já instalados continuam.
  Corrija a causa e reexecute; backups registram a parte aplicada.

Para experimentar dotfiles sem tocar no seu HOME:

```bash
./bootstrap.sh --check --dotfiles-only --destination /caminho/novo/home-de-teste --preset minimal
```

O destino deve ser um diretório real sob seu controle, sem symlinks. Aplicar ali
também exige `--apply` explícito. Destino alternativo é permitido somente para
dotfiles, nunca para provisionar pacotes/serviços de outro sistema.

## Serviços

`--services` é opt-in. Os estados aprovados estão em `inventory/services.yml`.
Não se copiam unidades geradas por sessão, ambientes systemd ou logs. Nunca são
desabilitados serviços alheios, habilitado `sshd` ou reparados Twingate/Ly.

UFW e SDDM recebem somente habilitação, sem start/restart automático. **UFW pode
passar a iniciar no próximo boot**: revise a política no destino antes de usar o
módulo de serviços remotamente. Serviços de sessão são habilitados sem iniciá-los
fora de uma sessão gráfica. Autenticação de VPN deve ser refeita localmente.

## Pendências reais de reprodução

Não há promessa de restauração completa enquanto estes itens não forem resolvidos:

- `slack-desktop-wayland` não foi encontrado na consulta AUR registrada. O pacote
  instalado não foi substituído por outro nome nem seu binário copiado.
- `android-studio`, `debtap`, `twingate` e `python-ewmh` foram encontrados no RPC AUR.
  Isso não prova segurança, origem histórica nem compilação. Instalação exige
  `--allow-aur`, helper disponível/instalável e revisão interativa dos PKGBUILDs.
- Codex, herdr, rtk, Minzi, toolchain Rust e Android SDK precisam de procedimentos
  de origem/versionamento definidos. Presença atual não torna sua instalação
  reproduzível. SDKs, licenças e autenticações não são copiados.
- Bun e uv são declarados como pacotes dos repositórios, não cópias de ELF pessoais.

Em um destino novo, itens ausentes sem origem resolvida bloqueiam a aplicação.
`--skip-unresolved` permite **restauração parcial explícita**, com aviso; não os
instala e não substitui por alternativas. Por exemplo, após revisar as limitações:

```bash
./bootstrap.sh --apply --preset full --install-prerequisites --skip-unresolved
```

O resultado acima não é uma réplica completa. AUR continua separado enquanto
`--allow-aur` não for fornecido. Ferramentas já presentes são preservadas sem alegar
que suas fontes foram fixadas.

## Segurança e dados excluídos

Nunca foram importados perfis de navegador, sessões, senhas, tokens, chaves SSH,
known_hosts, credenciais Git/GitHub, contas VPN, chaves de dispositivos Android,
cookies, cofres Obsidian, projetos, documentos ou históricos. Não há captura
indiscriminada de diretórios de aplicativos. `fish_variables` e estado do Chezmoi
ficaram fora; defaults CachyOS e funções/configs selecionados foram preservados.
Preferências Pure de cores/símbolos/toggles foram reconstruídas em um arquivo
de configuração com valores literais inertes, sem copiar o estado universal.
Outras variáveis universais não foram importadas. A aparência exata ainda requer conferência
visual no destino, pois não se executou a sessão Fish original para inspecioná-la.

Imagens copiadas tiveram metadados EXIF/XMP/IPTC/comentários removidos, preservando
a imagem. Um documento técnico de terceiros teve exemplos de credenciais
substituídos em memória antes da importação. Valores originais não foram exibidos
nem gravados aqui. Referências a credenciais em código são dinâmicas, não valores.

`scripts/safety.py` faz verificações conservadoras, com relatório somente de
caminho/regra. O hook pre-commit inspeciona também os blobs efetivamente staged,
não só a árvore de trabalho. **Detecção por padrões não garante ausência absoluta
de segredos**, não substitui revisão e não audita históricos externos.

O hook é habilitado apenas neste repositório por `core.hooksPath=hooks`; essa
configuração local não acompanha um clone. Para ativá-lo em outro clone:

```bash
git config --local core.hooksPath hooks
python3 -B scripts/validate.py --secrets-only
```

Backups ficam em `.state/backups/`, ignorados pelo Git e protegidos por permissões.
Eles nunca devem ser publicados ou transferidos como dotfiles. Não há remote
configurado nem push automático. Para transferir somente o conteúdo versionado,
use `git archive` ou um repositório privado revisado; não copie `.state/`.

## Validação sem provisionar o host

```bash
python3 -B scripts/validate.py
python3 -B scripts/validate.py --isolated
```

O primeiro comando usa ferramentas já presentes, AST Python, sintaxe Shell,
testes unitários e renderização Chezmoi temporária; informa checks indisponíveis.
Verifica também sintaxe Fish/Zsh/Node quando os binários existem, sem executar
plugins ou ferramentas GSD importadas.

O segundo usa imagem **já em cache** `python:3.13-slim`: não faz pull. O projeto
entra read-only; não se monta Docker socket, HOME ou diretórios pessoais. Somente
o tmpfs do container é gravável. Ferramentas de validação são baixadas do PyPI
dentro dele, sem instalação no host. O container é descartado ao sair.

Ansible é testado com pacman simulado: syntax, check sem alteração da fixture,
primeira execução e segunda com `changed=0`. Isso **não** substitui instalação real
em Arch, validação de PKGBUILD ou systemd real. Provisionamento real, Hyprland/lock
em sessão, monitores físicos, suspensão, Bluetooth, fingerprint e energia precisam
de uma VM Arch e/ou hardware apropriado; não foram exercitados na instalação atual.
Veja `VALIDATION.md` para os resultados e limites desta entrega.

## Recuperação

Após uma aplicação com alterações, cada execução registra um manifesto em
`.state/backups/<execução>/manifest.json`. Primeiro visualize a recuperação:

```bash
python3 -B scripts/recover.py --manifest .state/backups/EXECUCAO/manifest.json
```

Somente para efetivar, acrescente `--apply`. Para destino alternativo, informe
o mesmo `--destination` usado originalmente.

A recuperação só restaura/substitui/remove arquivos se seus hashes ainda forem
os da aplicação registrada. Edições posteriores são preservadas e causam bloqueio.
Arquivos criados pela aplicação podem ser removidos com essa autorização explícita;
diretórios, pacotes e serviços não são removidos nem revertidos. Não há rollback
automático do pacman. Backups divergentes ou ausentes também bloqueiam.

## Manutenção e limites

- Edite manifestos por módulo; valide antes de executar. As listas antigas do
  repositório original não prevalecem sobre a curadoria registrada aqui.
- Ajustes locais ficam em overrides ignorados e `hypr/local.conf`; alterações
  feitas diretamente em arquivos gerenciados serão detectadas, não sobrescritas
  silenciosamente. O bootstrap não converte essas alterações em fonte sozinho.
- Atualize código, ferramentas e pacotes conscientemente; não há cron de atualização.
- Arch rolling reproduz o estado declarado, não versões históricas bit a bit.
  Dependências são resolvidas conforme os repositórios do destino. Para fixação
  integral seriam necessários snapshots/arquivo de pacotes e fontes verificadas.
- Plugins OpenCode mantêm a configuração compatível atual, incluindo referências
  `@latest`; esse comportamento não é pinning. Auth/runtime não são transportados.
- Código OpenCode/GSD e recursos foram incluídos por allowlist revisada. Nenhum
  plugin, instalador GSD ou skill foi executado para realizar esta captura.
- `reference/inactive/` guarda configurações antigas e scripts apenas como
  referência. O script de clima usa geolocalização por IP e permanece inativo;
  `remove-nvidia` nunca é chamado pelo bootstrap.
- `scripts/capture*.py` são ferramentas da captura inicial, não atualização
  automática: recusam sobrescrever conteúdo divergente e não são chamadas pelo
  bootstrap. A implementação inicial preservou o repositório antigo; em
  2026-10-28, seu conteúdo foi substituído por este projeto com autorização,
  mantendo o histórico Git anterior.

## Substituição do repositório antigo — 2026-10-28

Este projeto substitui os dotfiles antigos, incluindo o perfil i3/X11 e os hooks
automáticos de instalação/remoção do Chezmoi. O histórico anterior permanece no
Git; nenhum force-push é necessário. A substituição do repositório não aplica
configurações nem desfaz instalações/remoções feitas anteriormente no sistema.

**Não execute `chezmoi apply` usando a raiz deste repositório como sourceDir.**
A estrutura mudou: os templates ficam em `chezmoi/`, e o ponto de entrada é
`./bootstrap.sh`, que realiza renderização isolada e verifica conflitos antes de
aplicar. Uma configuração Chezmoi antiga apontando para a raiz não é migrada
automaticamente. Comece com `./bootstrap.sh --preset minimal --dry-run`.

O relatório `VALIDATION.md` documenta os testes da entrega inicial; as menções à
preservação do repositório original naquele relatório referem-se àquela etapa.
- Banco dconf global, perfis NetworkManager e cadastros Bluetooth/fingerprint não
  são clonados: podem conter dados pessoais/segredos. GTK é restaurado por arquivos
  selecionados; aplicações que dependam exclusivamente de dconf/libadwaita podem
  requerer preferências locais adicionais. Dependências dos scripts estão em
  `inventory/config-dependencies.yml`.
