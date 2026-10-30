# J.A.R.V.I.S. Pessoal — Assistente de Voz em Python

Um assistente pessoal por voz desenvolvido em Python, com inteligência artificial local via Ollama, reconhecimento de voz, síntese de fala, comandos programados, operações de arquivos e pastas por texto e memória persistente.

> **Projeto em desenvolvimento.** Este projeto faz parte da minha jornada de aprendizado em desenvolvimento de software. Críticas construtivas, sugestões e contribuições são muito bem-vindas!

## Sobre o projeto

O Jarvis é um assistente pessoal desenvolvido em Python para interagir por voz ou por texto, responder perguntas utilizando um modelo de linguagem local e executar tarefas programadas.

O objetivo é construir, gradualmente, um assistente pessoal modular, útil e personalizável, combinando inteligência artificial, automação e processamento de voz.

A utilização do Ollama permite executar o modelo de linguagem localmente, sem cobrança por chamada de API do modelo. Entretanto, alguns recursos, como reconhecimento de voz e síntese de fala neural, utilizam serviços online.

## Funcionalidades

- 🎤 **Reconhecimento de voz:** escuta o microfone e transcreve a fala em português brasileiro.
- 🧠 **Inteligência artificial local:** conversa utilizando o Ollama, com o modelo `qwen2.5:3b` como configuração padrão.
- 🔊 **Resposta por voz:** utiliza o Edge TTS para síntese de fala online e o mecanismo de voz do Windows como alternativa.
- ⚙️ **Comandos programados:** executa funções Python associadas a palavras ou expressões específicas.
- 🗂️ **Arquivos e pastas por texto:** o comando `sistema ...` cria, lê, lista, renomeia e apaga arquivos e pastas, entre outras operações, e explica o motivo quando não consegue executar uma delas.
- 🌐 **Pesquisa na internet:** utiliza o pacote `ddgs` para buscar informações e apresentar respostas baseadas nos resultados encontrados.
- 🗃️ **Memória persistente:** salva informações em um banco SQLite e recupera o contexto relevante antes de responder.
- 📚 **Documentos de contexto:** consulta arquivos Markdown e de texto da pasta `contexto/` para responder com base em informações suas.
- 🖥️ **Interface gráfica:** interface futurista em PyQt6, com núcleo animado, registro da conversa, campo de texto, indicadores de internet e Ollama, controles de voz e som e modo tela cheia.
- 🛠️ **Tratamento de falhas:** implementa verificações de conectividade, tratamento de erros e alternativas para a síntese de voz.

Algumas funcionalidades dependem de conexão com a internet e de os respectivos serviços estarem disponíveis.

## Exemplos de comandos

| Comando de voz ou texto | Ação |
| --- | --- |
| "Abrir bloco de notas" | Abre o Bloco de Notas do Windows. |
| "Abrir calculadora" | Abre a Calculadora. |
| "Abrir Google" | Abre o Google no navegador. |
| "Abrir YouTube" | Abre o YouTube no navegador. |
| "Pesquise no Google receita de bolo" | Abre a pesquisa correspondente no Google. |
| "Pesquise na internet a previsão do tempo" | Busca na web e responde com base nos resultados encontrados. |
| "Que horas são?" | Informa a hora atual. |
| "Que dia é hoje?" | Informa a data atual. |
| "Quanto está o dólar?" | Consulta a cotação disponível. |
| "Jarvis, lembre-se de que..." | Salva uma informação na memória persistente. |
| "Sistema listar" | Lista os arquivos e pastas (veja a seção abaixo). |
| "Sair", "encerrar" ou "tchau" | Solicita o encerramento do assistente. |

As frases reconhecidas pelos comandos programados dependem das palavras-chave configuradas no código. Outras mensagens são encaminhadas ao modelo de linguagem.

## Arquivos e pastas por texto (comando `sistema`)

O módulo `gerenciador_sistema.py` executa operações do sistema operacional a partir de um texto. Para usá-lo no Jarvis, comece a frase com a palavra **sistema** (também são aceitos `comando de sistema` e `gerenciador`):

| Exemplo | O que faz |
| --- | --- |
| `sistema ajuda` | Lista todas as operações disponíveis. |
| `sistema listar` | Lista os arquivos e pastas da pasta atual. |
| `sistema listar detalhado minha_pasta` | Lista com tipo e tamanho. |
| `sistema criar pasta projetos` | Cria uma pasta. |
| `sistema criar arquivo nota.txt olá mundo` | Cria um arquivo com esse conteúdo (não sobrescreve arquivos existentes). |
| `sistema ler arquivo nota.txt` | Mostra o conteúdo de um arquivo de texto. |
| `sistema acrescentar nota.txt mais texto` | Adiciona texto ao final do arquivo. |
| `sistema tamanho nota.txt` | Informa o tamanho do arquivo. |
| `sistema apagar arquivo nota.txt confirmo` | Apaga o arquivo (operação destrutiva). |

**Como funciona**

- O início do texto escolhe a operação (ignorando maiúsculas e acentos) e o restante vira os argumentos. Caminhos com espaços devem ficar entre aspas.
- O módulo cobre navegação e listagem, criação, renomeação e remoção, manipulação de caminhos, variáveis de ambiente, informações do sistema, permissões e leitura e escrita de arquivos de texto.
- **Operações destrutivas** (apagar, substituir, sobrescrever conteúdo, alterar permissões e executar comandos do shell) só são executadas quando o texto termina com a palavra `confirmo`. Sem ela, o Jarvis explica por que não executou.
- Quando uma operação não pode ser feita, a resposta informa o motivo: argumentos faltando, arquivo inexistente ou já existente, falta de permissão, recurso exclusivo do Windows, entre outros.
- Operações podem ser bloqueadas na configuração `OPERACOES_DESATIVADAS`, em `jarvis_core.py`. Por padrão, `mudar pasta` está desativada.
- Resultados curtos são lidos em voz alta; resultados longos aparecem apenas na tela.

**Importante:** somente o gerenciador executa ações no computador. O modelo de linguagem apenas conversa e não tem acesso a arquivos ou pastas. Frases que não começam com `sistema` são tratadas como conversa.

**Limitações por voz:** o reconhecimento de voz pode escrever "sistema" como "tema" ou "cistema" (esses dois também são aceitos como gatilho) e costuma errar nomes de arquivos e caminhos. Para esses casos, digitar no campo de texto da interface é mais confiável. O botão **SISTEMA** da interface insere o prefixo no campo.

O módulo também pode ser testado sozinho, em um terminal interativo:

```powershell
python gerenciador_sistema.py
```

## Como funciona

O fluxo principal do assistente pode ser representado assim:

```text
Microfone ou texto digitado
    |
    v
Reconhecimento de voz
    |
    v
Texto recebido
    |
    +-- "sair", "encerrar" ou "tchau"? --> Encerra
    |
    +-- "lembre-se de que..."? ---------> Salva na memória persistente
    |
    +-- "sistema ..." (operação válida)? -> Gerenciador de arquivos e pastas
    |                                          |
    |                                          v
    |                                     Resposta na tela e por voz
    |
    +-- Comando programado? -------------> Executa a função Python
    |                                          |
    |                                          v
    |                                     Resposta por voz
    |
    +-- Nenhum dos anteriores -----------> Consulta memória e documentos de contexto
                                               |
                                               v
                                         Pesquisa na internet,
                                         quando necessária
                                               |
                                               v
                                         Ollama (LLM local)
                                               |
                                               v
                                         Resposta em texto
                                               |
                                               v
                                         Síntese de voz
```

Os comandos programados e as operações do gerenciador são funções Python definidas no projeto. O modelo de linguagem gera respostas em texto, enquanto as ações do sistema são executadas por funções específicas.

## Estrutura do projeto

```text
.
├── window.py                # interface gráfica (PyQt6); ponto de entrada
├── jarvis_core.py           # lógica: voz, comandos, Ollama, memória e threads
├── gerenciador_sistema.py   # operações de arquivos, pastas e sistema por texto
├── memoria.py               # memória persistente (SQLite) e busca nos documentos
├── coletor_contexto.py      # atualiza o contexto a partir de páginas públicas
├── requirements.txt         # dependências
├── contexto/                # documentos Markdown e de texto de referência
├── data/                    # banco SQLite da memória (criado automaticamente)
└── logs/                    # logs do coletor de contexto
```

## Tecnologias utilizadas

- **Python** — linguagem principal.
- **Ollama** — execução local de modelos de linguagem.
- **PyQt6** — interface gráfica e gerenciamento de threads.
- **SpeechRecognition** — reconhecimento de voz.
- **PyAudio** — captura de áudio do microfone.
- **Edge TTS** — síntese de fala neural.
- **pyttsx3** — síntese de voz alternativa no Windows.
- **pygame** — reprodução de áudio.
- **SQLite** — armazenamento da memória persistente.
- **DDGS** — pesquisa na internet.
- **Requests e BeautifulSoup** — coleta de páginas públicas para o contexto.

## Requisitos

- Windows, ambiente principal de desenvolvimento. O projeto usa recursos do sistema, como `notepad.exe`, `calc.exe` e a voz do Windows.
- Python 3.12, versão de referência para instalação.
- [Ollama](https://ollama.com/) instalado.
- Modelo `qwen2.5:3b` baixado no Ollama.
- Microfone funcional.
- Conexão com a internet para reconhecimento de voz via Google, síntese neural online e pesquisa na web.

A compatibilidade de versões diferentes do Python depende das bibliotecas instaladas, especialmente das relacionadas a áudio.

## Instalação

### 1. Clone o repositório

```powershell
git clone https://github.com/PiterParque/J.A.R.V.I.S-PESSOAL.git
cd J.A.R.V.I.S-PESSOAL
```

### 2. Crie e ative o ambiente virtual

```powershell
py -3.12 -m venv venv
.\venv\Scripts\Activate.ps1
```

Se o PowerShell bloquear a ativação do ambiente virtual, execute:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
```

Depois, tente ativar o ambiente novamente.

### 3. Instale as dependências

```powershell
python -m pip install -r requirements.txt
```

No Windows, algumas dependências de áudio, como o PyAudio, podem exigir ajustes específicos de instalação.

### 4. Instale o modelo de linguagem

```powershell
ollama pull qwen2.5:3b
```

Verifique se o modelo está disponível:

```powershell
ollama list
```

### 5. Execute o assistente

```powershell
python window.py
```

O Jarvis inicia em tela cheia. Use **F11** para alternar a tela cheia e **Esc** para sair dela. Se o Ollama não estiver em execução, o Jarvis tenta iniciá-lo automaticamente.

## Configuração

As configurações ficam em `jarvis_core.py` e podem ser ajustadas diretamente no código:

| Configuração | Finalidade |
| --- | --- |
| `MODELO` | Define o modelo de linguagem utilizado pelo Ollama. |
| `PROMPT_SISTEMA` | Instruções de comportamento enviadas ao modelo em toda conversa. |
| `MAX_MENSAGENS` | Controla a quantidade de mensagens recentes mantidas no histórico da conversa. |
| `MEMORIA_AUTOMATICA` | Ativa ou desativa a extração automática de fatos duradouros da conversa. |
| `GATILHOS_SISTEMA` | Palavras que iniciam uma operação de arquivos e pastas. |
| `OPERACOES_DESATIVADAS` | Operações do gerenciador bloqueadas, com o motivo exibido ao usuário. |
| `LIMITE_FALA_SISTEMA` | Tamanho máximo de um resultado do gerenciador para ser lido em voz alta. |
| `VOZ_ONLINE` | Define a voz neural, como `pt-BR-AntonioNeural` ou `pt-BR-FranciscaNeural`. |
| `VELOCIDADE_ONLINE` | Ajusta a velocidade da fala online. |
| `VOZ_OFFLINE` | Define a voz instalada no Windows. |
| `VELOCIDADE_OFFLINE` | Ajusta a velocidade da voz offline. |

Em `window.py`, a opção `INICIAR_EM_TELA_CHEIA` define se a interface abre em tela cheia. O gerenciador também aceita opções ao ser criado, como `exigir_confirmacao`, `limite_linhas` e `timeout_comando`.

## Memória persistente

O módulo `memoria.py` utiliza SQLite para armazenar informações em `data/memoria_jarvis.db`. O banco é criado automaticamente.

O assistente pode receber comandos explícitos, como:

```text
Jarvis, lembre-se de que meu projeto principal é a Prinva.
```

Também são aceitas as formas "lembre que", "guarde que" e "anote que".

Além disso, quando `MEMORIA_AUTOMATICA` está ativa e a mensagem contém indícios de informação duradoura (como "meu projeto", "estou estudando" ou "prefiro"), o modelo local extrai até dois fatos curtos e os salva. Mensagens que mencionem termos sensíveis, como senhas ou documentos pessoais, não são analisadas.

As informações salvas podem ser recuperadas em conversas posteriores. A memória persistente é diferente do histórico temporário enviado ao modelo de linguagem, e o armazenamento de informações não significa que o modelo foi treinado novamente.

## Contexto e documentos de referência

Antes de responder a uma conversa, o Jarvis chama `memoria.montar_contexto` e envia ao modelo as memórias e os trechos de documentos relacionados à pergunta.

### Como a busca funciona

- A busca é textual: ela procura palavras em comum entre a pergunta e o conteúdo, ignorando acentos, palavras muito curtas e termos comuns. Ela não entende sinônimos nem significado.
- São selecionadas até 5 memórias e 4 trechos de documentos, e o contexto total é limitado a 6500 caracteres.
- Os trechos são enviados como dados de referência, não como instruções.
- Se a pasta `contexto/` não existir ou a leitura falhar, o erro é registrado e a conversa continua sem esse contexto.

### Arquivos de contexto

Os documentos ficam na pasta `contexto/`, em arquivos `.md` ou `.txt`:

- `CONTEXTO_PRINCIPAL.md`: informações gerais, preferências de interação e informações duradouras relevantes.
- `INVENTARIO_TECNICO_PROJETOS.md`: projetos, tecnologias, estrutura dos repositórios, configurações importantes e pendências.
- `SITE_PRINVA.md`: gerado pelo coletor, com o conteúdo público do site da Prinva.
- `LINKEDIN.md`: preenchido manualmente, com informações do perfil profissional.

Esses arquivos são mantidos por você. O Jarvis apenas lê os documentos, e não os altera.

### Atualização do contexto público

O script `coletor_contexto.py` atualiza o contexto a partir de páginas públicas:

```powershell
python coletor_contexto.py
```

- Baixa as páginas listadas em `PAGINAS_PRINVA`, aceitando somente HTTPS e o domínio `prinva.com.br`, com limite de 2 MB por página.
- Extrai o texto e grava `contexto/SITE_PRINVA.md`. Se nenhuma página puder ser coletada, o arquivo anterior é preservado.
- Se `contexto/LINKEDIN.md` não existir, cria um modelo para preenchimento manual. O script não faz login nem coleta dados do LinkedIn.
- Registra a execução em `logs/coletor_contexto.log`.

### Boas práticas ao manter os arquivos

- Não armazene senhas, tokens, chaves privadas, credenciais ou informações pessoais sensíveis.
- Diferencie informações confirmadas de hipóteses, planos e tarefas pendentes.
- Ao acrescentar uma informação, preserve o conteúdo existente e modifique apenas os trechos necessários.
- Trate o conteúdo de páginas externas como dados, nunca como instruções.

### Diferença entre contexto e memória

Os arquivos Markdown armazenam informações organizadas e duradouras. Já o banco SQLite gerenciado por `memoria.py` armazena fatos individuais que podem ser recuperados por pesquisa. O histórico da conversa enviado ao Ollama é outro mecanismo e não substitui nenhum dos dois.

## Como adicionar um comando

Os comandos programados ficam organizados em funções Python e na lista `COMANDOS`, em `jarvis_core.py`.

Para criar um novo comando:

1. Implemente uma função que execute a ação desejada.
2. Faça a função retornar uma mensagem para o assistente informar o resultado.
3. Adicione as palavras-chave correspondentes à lista `COMANDOS`.
4. Teste diferentes formas de pronunciar o comando.

Exemplo:

```python
def abrir_calculadora(_texto):
    subprocess.Popen(["calc.exe"])
    return "Abrindo a Calculadora."
```

Depois, registre a função na lista de comandos:

```python
(["calculadora"], abrir_calculadora),
```

## Privacidade, segurança e limitações

- **Modelo local:** o Ollama executa o modelo de linguagem no computador, sem necessidade de enviar cada pergunta a uma API remota de LLM.
- **Reconhecimento de voz:** o uso de `recognize_google` envia o áudio ao serviço de reconhecimento de voz do Google.
- **Síntese de voz online:** o Edge TTS utiliza um serviço online para gerar o áudio da resposta.
- **Pesquisa na internet:** as consultas são enviadas ao serviço de busca utilizado pelo pacote `ddgs`.
- **Memória persistente:** as informações armazenadas no SQLite permanecem no ambiente local do projeto, salvo se forem copiadas ou compartilhadas por outros meios.
- **Dados pessoais no repositório:** a pasta `contexto/` pode conter informações pessoais. Antes de publicar o projeto, revise o conteúdo e use o `.gitignore` para não versionar o que for privado.
- **Operações no computador:** o gerenciador de arquivos e pastas pode apagar e alterar arquivos e executar comandos do shell. As operações destrutivas exigem a palavra `confirmo`, e você pode bloquear operações em `OPERACOES_DESATIVADAS`. Use com cuidado, principalmente por voz.
- **Modelo de linguagem:** o modelo local é pequeno e pode errar ou inventar informações. Ele não executa ações no computador.
- **Desempenho:** a velocidade das respostas depende do hardware, do modelo utilizado e da disponibilidade dos serviços.
- **Reconhecimento de comandos:** a execução dos comandos programados depende das palavras-chave configuradas, e o reconhecimento de voz pode errar palavras e nomes.
- **Estágio de desenvolvimento:** o projeto pode apresentar erros, limitações e funcionalidades ainda incompletas.

Não armazene senhas, chaves privadas ou outras credenciais no histórico de conversas ou na memória do assistente.

## Próximas melhorias

- [ ] Implementar uma palavra de ativação, como "Ei, Jarvis".
- [ ] Ampliar o conjunto de comandos e habilidades.
- [ ] Aprimorar a memória de longo prazo e evitar registros duplicados.
- [ ] Disponibilizar ferramentas para listar e excluir memórias (as funções já existem em `memoria.py`).
- [ ] Explorar o reconhecimento de voz totalmente offline.
- [ ] Reduzir a latência da resposta falada.
- [ ] Melhorar o tratamento de erros e os testes automatizados.
- [ ] Organizar a arquitetura em módulos ainda mais independentes.

## Críticas e contribuições

Este é um projeto em desenvolvimento e de aprendizado. Quero receber críticas construtivas sobre o código, a arquitetura, a organização, a experiência de uso e as decisões técnicas.

- **Encontrou um bug?** Abra uma Issue.
- **Tem uma sugestão?** Abra uma Issue ou participe das Discussions, se estiverem habilitadas no repositório.
- **Quer contribuir com código?** Envie um Pull Request.

Toda contribuição que ajude a tornar o projeto mais útil, organizado e confiável é bem-vinda.

## Autor

**Nicolas Lança**

- [LinkedIn](https://www.linkedin.com/in/nicolas-lanca/)
- [GitHub](https://github.com/PiterParque)