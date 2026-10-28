# J.A.R.V.I.S-PESSOAL
Assistente de voz em Python com LLM local (Ollama). Ouve, responde por voz e executa comandos. Em desenvolvimento, críticas são bem-vindas!

# Jarvis: assistente de voz em Python

> **Projeto em desenvolvimento.** Ainda está evoluindo e tem muita coisa para melhorar. Críticas, sugestões e ideias são muito bem-vindas!

Um assistente pessoal por voz, feito do zero em Python, que usa um **LLM local (Ollama)** para conversar, sem custo por uso. Ele escuta, entende, responde em voz alta e também executa comandos que eu programei.

## O que ele faz hoje

- 🎤 **Escuta e transcreve** a voz em português (pt-BR)
- 🧠 **Conversa** usando um modelo local via Ollama (padrão: `qwen2.5:3b`)
- 🔊 **Responde por voz**, com voz neural online (edge-tts) e a voz do Windows como plano B quando não há internet
- ⚙️ **Executa comandos programados** e avisa por voz o que está fazendo
- 🛡️ **Trata falhas**: sem internet ele passa para o modo texto; sem Ollama ele avisa em vez de travar

### Comandos de exemplo

| Diga algo como | O que acontece |
| --- | --- |
| "abrir bloco de notas" | Abre o Bloco de Notas |
| "abrir calculadora" | Abre a Calculadora |
| "abrir google" / "abrir youtube" | Abre o site no navegador |
| "pesquisar receita de bolo" | Pesquisa o termo no Google |
| "que horas são" | Diz a hora |
| "que dia é hoje" | Diz a data |
| "sair", "encerrar" ou "tchau" | Encerra o Jarvis |

Qualquer outra frase vai para o modelo de IA, que responde em conversa.

## Como funciona

```
Microfone -> reconhecimento de voz -> é um comando programado?
                                        |-- sim -> executa a função e fala o que fez
                                        '-- não -> Ollama (LLM local) -> resposta falada
```

Os comandos são funções Python escritas por mim. O modelo **não executa nada por conta própria**: ele só gera texto. Isso deixa o comportamento previsível e seguro.

## Requisitos

- Windows (desenvolvido e testado nele)
- **Python 3.12** (versões mais novas ainda não têm pacotes prontos para algumas bibliotecas de áudio)
- [Ollama](https://ollama.com) instalado, com o modelo baixado
- Microfone
- Internet para o reconhecimento de voz e a voz neural (sem ela, o Jarvis funciona em modo texto com a voz do Windows)

## Instalação

```powershell
# 1. Clone o repositório
git clone https://github.com/SEU-USUARIO/SEU-REPOSITORIO.git
cd SEU-REPOSITORIO

# 2. Crie e ative o ambiente virtual com Python 3.12
py -3.12 -m venv venv
venv\Scripts\Activate.ps1

# 3. Instale as dependências
pip install -r requirements.txt

# 4. Baixe o modelo no Ollama
ollama pull qwen2.5:3b

# 5. Rode
python jarvis.py
```

Se o PowerShell bloquear a ativação da venv, rode antes: `Set-ExecutionPolicy -Scope Process Bypass`.

## Configuração

No topo do `jarvis.py` dá para ajustar:

- `MODELO`: qual modelo do Ollama usar
- `VOZ_ONLINE`: `pt-BR-AntonioNeural` (masculina) ou `pt-BR-FranciscaNeural` (feminina)
- `VELOCIDADE_ONLINE`: velocidade da fala (ex.: `"+10%"`)
- `MAX_MENSAGENS`: quanto da conversa fica na memória (menos = mais rápido)

### Criando um comando novo

1. Escreva uma função que faz a ação e devolve a frase que o Jarvis vai falar.
2. Adicione uma linha na lista `COMANDOS` com as palavras-gatilho.

## Privacidade e limitações

- O modelo de IA roda **no seu computador**, mas o reconhecimento de voz (Google) e a voz neural (edge-tts) usam serviços online. O áudio da sua fala é enviado ao Google, e o texto das respostas é enviado ao serviço de voz da Microsoft.
- Em computadores sem placa de vídeo, o modelo local pode demorar para responder.
- A detecção de comandos é por palavras-chave, então frases muito diferentes das previstas podem não ser reconhecidas.
- O projeto é novo e ainda tem bugs e arestas.

## Ideias para o futuro

- [ ] Palavra de ativação ("Ei, Jarvis")
- [ ] Mais comandos e habilidades
- [ ] Memória de longo prazo
- [ ] Reconhecimento de voz 100% offline
- [ ] Reduzir a latência da resposta falada

## Críticas e contribuições

Este é um projeto de aprendizado e eu **quero ouvir críticas**: sobre o código, a organização, a arquitetura, o que parece errado ou ingênuo. Pode falar com franqueza.

- 🐛 Achou um bug ou algo estranho? Abra uma **Issue**.
- 💡 Tem uma ideia ou sugestão? Abra uma **Issue** ou participe das **Discussions**.
- 🔧 Quer melhorar o código? Faça um **Pull Request**.

Obrigado por dar uma olhada!

## Autor

Feito por **NICOLAS LANÇA** | [LinkedIn](https://www.linkedin.com/in/nicolas-lanca)

## Licença

Defina uma licença (por exemplo, MIT) e adicione o arquivo `LICENSE`.
