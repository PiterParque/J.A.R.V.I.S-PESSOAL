"""
Jarvis: lógica (sem desenho de interface).

Contém configurações, internet/Ollama, fala, comandos programados e as threads
de trabalho (Ouvinte, Cerebro, Monitor). É usado pelo jarvis_gui.py.
Dependências: pip install PyQt6 ollama SpeechRecognition PyAudio edge-tts pygame pyttsx3
"""
import asyncio
import datetime
import json
import os
import queue
import re
import socket
import subprocess
import tempfile
import time
import urllib.request
import webbrowser
from urllib.parse import quote_plus, urlparse
import memoria
from gerenciador_sistema import GerenciadorSistema
import edge_tts
import ollama
import pyttsx3
import speech_recognition as sr

try:
    from ddgs import DDGS  # pip install ddgs
except ImportError:
    DDGS = None

os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"  # esconde a mensagem do pygame
import pygame

from PyQt6.QtCore import QThread, pyqtSignal

# ============================================================================
# Configurações
# ============================================================================
MODELO = "qwen2.5:3b"
MAX_MENSAGENS = 100#quantas mensagens recentes ficam na memória da conversa

# Memória automática: ativa apenas para informações potencialmente duradouras.
MEMORIA_AUTOMATICA = True
MAX_MEMORIAS_AUTOMATICAS = 2

GATILHOS_MEMORIA = (
    "meu projeto", "meus projetos", "estou desenvolvendo",
    "estou construindo", "estou estudando", "meu objetivo",
    "minha meta", "minha preferência", "prefiro",
    "trabalho com", "estou trabalhando", "quero que você lembre",
    "daqui para frente", "de agora em diante",
)

# Não persistir mensagens que contenham informações potencialmente sensíveis.
TERMOS_SENSIVEIS = (
    "minha senha", "minhas senhas", "meu cpf", "meu cartão",
    "meu cartao", "minha conta bancária", "minha conta bancaria",
    "meu diagnóstico", "meu diagnostico", "meus medicamentos",
    "meus remédios", "meus remedios", "meu prontuário",
    "meu prontuario",
)

VOZ_ONLINE = "pt-BR-AntonioNeural"  # ou "pt-BR-FranciscaNeural"
VELOCIDADE_ONLINE = "+0%"           # ex.: "+10%" mais rápido, "-10%" mais lento

VOZ_OFFLINE = "maria"               # parte do nome da voz instalada no Windows
VELOCIDADE_OFFLINE = 180
VOLUME_OFFLINE = 1.0

PALAVRAS_DE_SAIDA = ("sair", "encerrar", "tchau")

PROMPT_SISTEMA = (
    "Você é o Jarvis, assistente virtual pessoal de Nicolas de Paula Lança. "
    "Responda em português, em frases curtas, sem listas, sem markdown e sem emojis. "
    "Na conversa você só responde perguntas: você não abre, não cria e não lê arquivos "
    "ou pastas, e não tem acesso ao computador. Nunca diga que executou uma ação no "
    "computador. Se o Nicolas pedir algo com arquivos ou pastas, explique que ele deve "
    "começar a frase com a palavra sistema, como em: sistema listar, ou sistema criar "
    "arquivo teste.txt. Se você não souber algo, diga que não sabe."
)

# Arquivos, pastas e sistema por texto (veja gerenciador_sistema.py).
# Para usar, comece a frase com uma destas palavras. Exemplos:
#   "sistema listar documentos"
#   "sistema criar arquivo nota.txt olá mundo"
#   "sistema apagar arquivo nota.txt confirmo"   (operações destrutivas exigem "confirmo")
#   "sistema ajuda"                              (lista tudo o que ele faz)
# "cistema" e "tema" são erros comuns do reconhecimento de voz para "sistema".
GATILHOS_SISTEMA = ("comando de sistema", "gerenciador", "sistema", "cistema", "tema")

# Operações bloqueadas no Jarvis: nome -> motivo (o Jarvis explica o motivo se for pedida).
OPERACOES_DESATIVADAS = {
    "mudar_pasta": (
        "ela mudaria a pasta de trabalho de todo o Jarvis e poderia "
        "quebrar a leitura da pasta de contexto"
    ),
}

# Resultados maiores que isso aparecem na tela, mas não são lidos em voz alta.
LIMITE_FALA_SISTEMA = 200

PADRAO_SISTEMA = re.compile(
    r"^(?:jarvis[\s,]*)?(?:"
    + "|".join(re.escape(g) for g in GATILHOS_SISTEMA)
    + r")[\s,:]+(.+)$",
    flags=re.IGNORECASE,
)

GERENCIADOR = GerenciadorSistema()
for _nome, _motivo in OPERACOES_DESATIVADAS.items():
    GERENCIADOR.desativar(_nome, _motivo)

try:
    pygame.mixer.init()
except Exception as erro:  # sem placa de som, por exemplo
    print(f"Aviso: áudio indisponível ({erro})")


# ============================================================================
# Utilidades de rede e Ollama
# ============================================================================
def tem_internet(timeout=2):
    destinos = [("www.google.com", 443), ("1.1.1.1", 443), ("1.1.1.1", 53)]
    for host, porta in destinos:
        try:
            with socket.create_connection((host, porta), timeout=timeout):
                return True
        except OSError:
            continue
    return False


def ollama_rodando():
    try:
        with urllib.request.urlopen("http://localhost:11434", timeout=2):
            return True
    except Exception:
        return False


def iniciar_ollama(espera=20):
    """Inicia o Ollama em segundo plano se ele ainda não estiver rodando."""
    if ollama_rodando():
        return True
    try:
        subprocess.Popen(
            ["ollama", "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    except Exception:
        return False
    for _ in range(espera):
        if ollama_rodando():
            return True
        time.sleep(1)
    return False


# ============================================================================
# Fala
# ============================================================================
def limpar(texto):
    """Remove símbolos de markdown para a voz não lê-los."""
    return re.sub(r"[*#`_>]", "", texto)


def falar_offline(texto):
    try:  # o pyttsx3 (SAPI) precisa do COM inicializado fora da thread principal
        import pythoncom
        pythoncom.CoInitialize()
    except Exception:
        pass
    motor = pyttsx3.init()
    for voz in motor.getProperty("voices"):
        if VOZ_OFFLINE.lower() in voz.name.lower():
            motor.setProperty("voice", voz.id)
            break
    motor.setProperty("rate", VELOCIDADE_OFFLINE)
    motor.setProperty("volume", VOLUME_OFFLINE)
    motor.say(texto)
    motor.runAndWait()


async def _gerar_audio(texto, caminho):
    comunicacao = edge_tts.Communicate(texto, VOZ_ONLINE, rate=VELOCIDADE_ONLINE)
    await comunicacao.save(caminho)


def falar_online(texto):
    arquivo = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    arquivo.close()
    try:
        asyncio.run(_gerar_audio(texto, arquivo.name))
        pygame.mixer.music.load(arquivo.name)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            pygame.time.Clock().tick(10)
        pygame.mixer.music.unload()
        return True
    except Exception as erro:
        print(f"Falha na voz online: {erro}")
        return False
    finally:
        try:
            os.remove(arquivo.name)
        except OSError:
            pass


def falar(texto):
    texto = limpar(texto)
    if not texto.strip():
        return
    if tem_internet() and falar_online(texto):
        return
    try:
        falar_offline(texto)
    except Exception as erro:
        print(f"Falha na voz offline: {erro}")



# ============================================================================
# Comandos programados (cada função devolve a frase que o Jarvis vai dizer)
# ============================================================================
DIAS = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira",
        "sexta-feira", "sábado", "domingo"]
MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
         "agosto", "setembro", "outubro", "novembro", "dezembro"]


def abrir_bloco_de_notas(_texto):
    subprocess.Popen(["notepad.exe"])
    return "Abrindo o Bloco de Notas."


def abrir_calculadora(_texto):
    subprocess.Popen(["calc.exe"])
    return "Abrindo a Calculadora."


def abrir_google(_texto):
    webbrowser.open("https://www.google.com")
    return "Abrindo o Google."


def abrir_youtube(_texto):
    webbrowser.open("https://www.youtube.com")
    return "Abrindo o YouTube."


def limpar_consulta(texto):
    """Tira as palavras de comando ("pesquise", "na internet"...) e deixa só o assunto."""
    t = re.sub(r"\b(jarvis|por favor)\b", " ", texto, flags=re.IGNORECASE)
    t = re.sub(r"\b(pesquis\w*|procur\w*|busqu\w*|busc\w*)\b", " ", t, count=1, flags=re.IGNORECASE)
    t = re.sub(r"\b(na internet|na web|no google|online)\b", " ", t, flags=re.IGNORECASE)
    t = re.sub(r"\s+", " ", t).strip()
    return re.sub(r"^(por|sobre|a respeito de)\s+", "", t, flags=re.IGNORECASE)


def pesquisar_no_google(texto):
    """Abre a pesquisa no navegador (comando explícito: 'pesquise no google ...')."""
    consulta = limpar_consulta(texto)
    if not consulta:
        return "O que você quer pesquisar?"
    webbrowser.open("https://www.google.com/search?q=" + quote_plus(consulta))
    return f"Pesquisando {consulta} no Google."


def dizer_hora(_texto):
    agora = datetime.datetime.now()
    return f"Agora são {agora:%H} horas e {agora:%M} minutos."


def dizer_data(_texto):
    hoje = datetime.date.today()
    return f"Hoje é {DIAS[hoje.weekday()]}, {hoje.day} de {MESES[hoje.month - 1]} de {hoje.year}."


# (palavras que você diz, código da moeda, como o Jarvis fala)
MOEDAS = (
    (("dólar", "dolar", "dólares", "dolares"), "USD", "o dólar"),
    (("euro", "euros"), "EUR", "o euro"),
    (("libra", "libras"), "GBP", "a libra"),
    (("bitcoin", "bitcoins"), "BTC", "o bitcoin"),
)


def formatar_reais(valor):
    texto = f"{valor:,.2f}"  # 1,234.56 -> 1.234,56
    return "R$ " + texto.replace(",", "#").replace(".", ",").replace("#", ".")


def dizer_cotacao(texto):
    """Cotação em reais pela AwesomeAPI (sem chave; dados com cache de ~1 minuto)."""
    minusculo = texto.lower()
    escolhidas = [
        (codigo, nome)
        for palavras, codigo, nome in MOEDAS
        if any(re.search(rf"\b{p}\b", minusculo) for p in palavras)
    ]
    if not escolhidas:
        # "cotação das ações da Petrobras" etc.: devolve None e a pergunta vai para a pesquisa na web
        if re.search(r"cota[cç][aã]o\s+d[oae]s?\s+\w+", minusculo):
            return None
        escolhidas = [("USD", "o dólar")]
    pares = ",".join(f"{codigo}-BRL" for codigo, _ in escolhidas)
    try:
        pedido = urllib.request.Request(
            f"https://economia.awesomeapi.com.br/json/last/{pares}",
            headers={"User-Agent": "Mozilla/5.0"},
        )
        with urllib.request.urlopen(pedido, timeout=8) as resposta:
            dados = json.load(resposta)
    except Exception as erro:
        print(f"[erro na cotação] {erro}")
        return "Não consegui consultar a cotação agora."

    frases = []
    for codigo, nome in escolhidas:
        item = dados.get(f"{codigo}BRL")
        if not item:
            continue
        valor = float(item["bid"])
        variacao = float(item["pctChange"])
        if variacao > 0:
            tendencia = f"em alta de {abs(variacao):.2f} por cento".replace(".", ",")
        elif variacao < 0:
            tendencia = f"em queda de {abs(variacao):.2f} por cento".replace(".", ",")
        else:
            tendencia = "estável"
        frases.append(f"{nome.capitalize()} está a {formatar_reais(valor)}, {tendencia}.")
    return " ".join(frases) or "Não encontrei essa cotação."


# Para criar um comando novo: escreva a função acima e adicione uma linha aqui.
COMANDOS = [
    (["bloco de nota", "notepad"], abrir_bloco_de_notas),
    (["calculadora"], abrir_calculadora),
    (["abrir google", "abre o google"], abrir_google),
    (["abrir youtube", "abre o youtube"], abrir_youtube),
    (["pesquisar no google", "pesquise no google", "pesquisa no google",
      "procure no google", "busque no google"], pesquisar_no_google),
    (["cotação", "cotacao", "bitcoin",
      "quanto está o dólar", "quanto esta o dolar", "quanto está o euro", "quanto esta o euro",
      "quanto está a libra", "quanto esta a libra", "quanto vale o dólar", "quanto vale o dolar",
      "quanto vale o euro", "quanto custa o dólar", "quanto custa o dolar",
      "valor do dólar", "valor do dolar", "valor do euro", "preço do dólar", "preço do euro"],
     dizer_cotacao),
    (["que horas", "me diga as horas", "hora é essa"], dizer_hora),
    (["que dia é hoje", "data de hoje", "qual a data"], dizer_data),
]


def executar_comando(texto):
    """Executa um comando programado. Devolve a frase de resposta, ou None."""
    minusculo = texto.lower()
    for gatilhos, funcao in COMANDOS:
        if any(g in minusculo for g in gatilhos):
            try:
                return funcao(texto)
            except Exception as erro:
                print(f"[erro no comando] {erro}")
                return "Não consegui executar esse comando."
    return None


# ============================================================================
# Pesquisa na internet (DuckDuckGo, pelo pacote ddgs)
# ============================================================================
# Se a frase tiver uma dessas palavras, o Jarvis pesquisa na internet antes de
# responder. Adicione as suas à vontade.
GATILHOS_WEB = (
    "pesquis", "procur", "busque", "na internet", "na web", "notícia", "noticia",
    "cotação", "cotacao", "previsão", "previsao", "clima", "placar",
    "quem ganhou", "resultado do", "últimas", "ultimas", "atualmente",
    "no momento", "lançamento", "lancamento",
)


def precisa_pesquisar(texto):
    minusculo = texto.lower()
    return any(g in minusculo for g in GATILHOS_WEB)


def buscar_na_web(texto, max_resultados=4):
    """Pesquisa na internet. Devolve [{'titulo', 'trecho', 'url'}] ou [] se falhar."""
    if DDGS is None:
        print("[busca] pacote ddgs não instalado: pip install ddgs")
        return []
    consulta = limpar_consulta(texto) or texto
    try:
        busca = DDGS()
        if re.search(r"not[ií]cia", texto, re.IGNORECASE):
            brutos = list(busca.news(consulta, region="br-pt", max_results=max_resultados))
        else:
            brutos = list(busca.text(consulta, region="br-pt", max_results=max_resultados))
    except Exception as erro:
        print(f"[erro na busca] {erro}")
        return []
    resultados = [
        {
            "titulo": r.get("title", ""),
            "trecho": r.get("body", ""),
            "url": r.get("href") or r.get("url", ""),
        }
        for r in brutos
    ]
    for i, r in enumerate(resultados, 1):  # aparece no terminal: veja o que a busca trouxe
        print(f"[busca {i}] {r['titulo']} | {r['trecho'][:120]}")
    return resultados


def montar_prompt_web(pergunta, resultados):
    """Junta a pergunta com os resultados da busca para o modelo responder."""
    hoje = datetime.date.today()
    blocos = [
        f"[{i}] {r['titulo']}\n{r['trecho'][:300]}"
        for i, r in enumerate(resultados, 1)
    ]
    return (
        f"Hoje é {hoje:%d/%m/%Y}.\n"
        f"Pergunta: {pergunta}\n\n"
        "Resultados da busca na internet:\n" + "\n\n".join(blocos) + "\n\n"
        "Responda à pergunta usando os resultados acima, em português, em até três "
        "frases curtas, sem markdown e sem listas. Informe os valores, nomes e datas "
        "que aparecerem nos trechos. Só diga que não encontrou se realmente não "
        "houver nada relevante, e não indique outros sites."
    )


def nomes_das_fontes(resultados, limite=3):
    nomes = []
    for r in resultados:
        site = urlparse(r["url"]).netloc.replace("www.", "")
        if site and site not in nomes:
            nomes.append(site)
    return nomes[:limite]


# ============================================================================
# Threads de trabalho (nada disso roda na thread da interface)
# ============================================================================
class Ouvinte(QThread):
    """Escuta o microfone continuamente e emite o texto reconhecido."""
    texto_ouvido = pyqtSignal(str)
    aviso = pyqtSignal(str)

    def __init__(self, ocupado):
        super().__init__()
        self.ocupado = ocupado          # Event: Jarvis está processando/falando
        self.escutando = True
        self.rodando = True
        self.reconhecedor = sr.Recognizer()
        self.reconhecedor.dynamic_energy_threshold = True

    def run(self):
        calibrado = False
        avisou_mic = False
        avisou_rede = False
        while self.rodando:
            if not self.escutando or self.ocupado.is_set():
                time.sleep(0.1)
                continue
            try:
                with sr.Microphone() as fonte:
                    if not calibrado:
                        self.reconhecedor.adjust_for_ambient_noise(fonte, duration=0.6)
                        calibrado = True
                    try:
                        audio = self.reconhecedor.listen(fonte, timeout=2, phrase_time_limit=15)
                    except sr.WaitTimeoutError:
                        continue
            except Exception as erro:
                if not avisou_mic:
                    self.aviso.emit(f"Microfone indisponível: {erro}")
                    avisou_mic = True
                time.sleep(3)
                continue

            # Se o Jarvis começou a falar nesse meio tempo, descarta o áudio.
            if not self.escutando or self.ocupado.is_set():
                continue
            try:
                texto = self.reconhecedor.recognize_google(audio, language="pt-BR")
            except sr.UnknownValueError:
                continue
            except sr.RequestError:
                if not avisou_rede:
                    self.aviso.emit("Sem conexão com o serviço de reconhecimento de voz.")
                    avisou_rede = True
                time.sleep(3)
                continue
            avisou_rede = False
            if texto.strip():
                self.texto_ouvido.emit(texto.strip())


class Cerebro(QThread):
    """Recebe textos, executa comandos ou conversa com o Ollama e fala."""
    estado = pyqtSignal(str)        # "pensando" | "falando" | "ocioso"
    inicio_resposta = pyqtSignal()
    token = pyqtSignal(str)
    fim_resposta = pyqtSignal()
    encerrar = pyqtSignal()
    info = pyqtSignal(str)          # linhas de status para o registro

    def __init__(self, ocupado):
        super().__init__()
        self.ocupado = ocupado
        self.fila = queue.Queue()
        self.rodando = True
        self.som = True
        self.historico = [{"role": "system", "content": PROMPT_SISTEMA}]

    def enviar(self, texto):
        self.fila.put(texto)

    def run(self):
        iniciar_ollama()
        while self.rodando:
            try:
                texto = self.fila.get(timeout=0.3)
            except queue.Empty:
                continue
            self.ocupado.set()
            try:
                self._atender(texto)
            except Exception as erro:
                print(f"[erro] {erro}")
            finally:
                self.ocupado.clear()
                self.estado.emit("ocioso")

    
    def _atender(self, texto):
        self.estado.emit("pensando")

        if texto.lower().strip() in PALAVRAS_DE_SAIDA:
            self._responder_fixo("Até logo!")
            self.encerrar.emit()
            return

        # Comando para salvar uma memória permanente.
        padrao_memoria = (
            r"^(?:jarvis[\s,]*)?"
            r"(?:lembre-se de que|lembre-se que|lembre que|"
            r"guarde que|anote que)\s+(.+)$"
        )
        correspondencia = re.match(
            padrao_memoria, texto.strip(), flags=re.IGNORECASE
        )

        if correspondencia:
            conteudo = correspondencia.group(1).strip()

            if conteudo:
                try:
                    resultado = memoria.salvar_memoria(conteudo)

                    if resultado:
                        self._responder_fixo(
                            "Certo. Salvei essa informação na minha memória."
                        )
                    else:
                        self._responder_fixo(
                            "Não consegui confirmar o salvamento dessa informação."
                        )
                except Exception as erro:
                    print(f"[erro ao salvar memória] {erro}")
                    self._responder_fixo(
                        "Não consegui salvar essa informação."
                    )
            else:
                self._responder_fixo("Qual informação você quer que eu lembre?")
            return

        # Arquivos, pastas e sistema: "sistema listar documentos", etc.
        # Só entra aqui se o texto depois do gatilho for uma operação conhecida;
        # frases como "sistema operacional é o quê?" seguem para a conversa normal.
        correspondencia_sistema = PADRAO_SISTEMA.match(texto.strip())

        if correspondencia_sistema:
            pedido = correspondencia_sistema.group(1).strip()

            if GERENCIADOR.reconhece(pedido):
                self._responder_sistema(pedido)
                return

        resposta = executar_comando(texto)

        if resposta is not None:
            self._responder_fixo(resposta)
            return

        self._conversar(texto)


    def _responder_fixo(self, texto):
        self.inicio_resposta.emit()
        self.token.emit(texto)
        self.fim_resposta.emit()
        self._falar(texto)

    def _responder_sistema(self, pedido):
        """Executa o pedido no GerenciadorSistema, mostra tudo na tela e fala só o que for curto."""
        try:
            resultado = GERENCIADOR.executar(pedido)
        except Exception as erro:
            print(f"[erro no gerenciador] {erro}")
            resultado = "Não consegui executar essa operação."

        self.inicio_resposta.emit()
        self.token.emit(resultado)
        self.fim_resposta.emit()

        if "\n" in resultado or len(resultado) > LIMITE_FALA_SISTEMA:
            self._falar("Pronto. O resultado está na tela.")
        else:
            self._falar(resultado)

    def _falar(self, texto):
        if not self.som:
            return
        self.estado.emit("falando")
        falar(texto)
 
    def _conversar(self, texto):
        def extrair_memorias_automaticas(texto):
                    """
                    Identifica fatos duradouros declarados pelo usuário.
                    Usa o Ollama local e não grava automaticamente informações sensíveis.
                    """
                    if not MEMORIA_AUTOMATICA or not texto.strip():
                        return []
        
                    texto_normalizado = texto.casefold()
        
                    # Não tenta memorizar mensagens que mencionem dados sensíveis.
                    if any(termo in texto_normalizado for termo in TERMOS_SENSIVEIS):
                        return []
        
                    # Só executa a análise quando houver indícios de informação duradoura.
                    if not any(gatilho in texto_normalizado for gatilho in GATILHOS_MEMORIA):
                        return []
        
                    instrucao = f"""
                    Analise exclusivamente a mensagem do usuário abaixo e identifique
                    informações úteis para conversas futuras.
        
                    Regras:
                    - Considere apenas fatos explicitamente declarados pelo usuário.
                    - Priorize projetos, estudos, objetivos, tecnologias utilizadas
                    e preferências estáveis de interação.
                    - Não infira fatos nem transforme hipóteses em certezas.
                    - Não registre informações de saúde, religião, política, sexualidade,
                    senhas, documentos pessoais, dados financeiros ou outros dados sensíveis.
                    - Ignore perguntas casuais, informações passageiras e fatos sobre terceiros.
                    - Não inclua a resposta do assistente nem invente informações.
                    - Retorne no máximo {MAX_MEMORIAS_AUTOMATICAS} fatos curtos.
                    - Se não houver informação adequada, retorne uma lista vazia.
        
                    Mensagem do usuário:
                    {texto}
        
                    Responda somente em JSON, neste formato:
                    {{"memorias": ["fato 1", "fato 2"]}}
                    """
        
                    try:
                        resposta = ollama.chat(
                            model=MODELO,
                            messages=[
                                {
                                    "role": "system",
                                    "content": (
                                        "Você identifica fatos para uma memória pessoal. "
                                        "Siga rigorosamente as regras e não invente dados."
                                    ),
                                },
                                {"role": "user", "content": instrucao},
                            ],
                            format="json",
                            options={"temperature": 0, "num_predict": 180},
                            keep_alive="30m",
                        )
        
                        dados = json.loads(resposta["message"]["content"])
                        memorias = dados.get("memorias", [])
        
                        if not isinstance(memorias, list):
                            return []
        
                        resultado = []
        
                        for item in memorias[:MAX_MEMORIAS_AUTOMATICAS]:
                            if not isinstance(item, str):
                                continue
        
                            fato = item.strip()
        
                            if not fato or len(fato) > 350:
                                continue
        
                            # Segunda verificação antes de permitir o salvamento.
                            fato_normalizado = fato.casefold()
        
                            if any(
                                termo in fato_normalizado
                                for termo in TERMOS_SENSIVEIS
                            ):
                                continue
        
                            resultado.append(fato)
        
                        return resultado
        
                    except Exception as erro:
                        print(f"[memória automática] Não foi possível extrair fatos: {erro}")
                        return []
             
        self.historico.append({"role": "user", "content": texto})
        del self.historico[1:-MAX_MENSAGENS]

        mensagens = self.historico
        fontes = []

        # Consulta memórias salvas e documentos da pasta contexto.
        try:
            contexto_local = memoria.montar_contexto(texto)
        except Exception as erro:
            print(f"[erro ao consultar memória] {erro}")
            contexto_local = ""

        if precisa_pesquisar(texto):
            if not tem_internet():
                self.historico.pop()
                self._responder_fixo(
                    "Estou sem internet agora, então não consigo pesquisar isso."
                )
                return

            self.info.emit("Pesquisando na internet...")
            resultados = buscar_na_web(texto)

            if not resultados:
                self.historico.pop()
                self._responder_fixo(
                    "Não consegui encontrar resultados na internet agora."
                )
                return

            fontes = nomes_das_fontes(resultados)

            # Os resultados da web são usados apenas nesta chamada.
            conteudo_usuario = montar_prompt_web(texto, resultados)

            if contexto_local:
                conteudo_usuario += (
                    "\n\nContexto local do usuário, obtido dos arquivos "
                    "e das memórias salvas:\n"
                    + contexto_local
                    + "\n\nUse esse contexto somente quando for relevante "
                    "para a pergunta. Não invente informações ausentes."
                )

            mensagens = self.historico[:-1] + [
                {"role": "user", "content": conteudo_usuario}
            ]

        elif contexto_local:
            # Mantém as mensagens anteriores e enriquece a pergunta atual.
            conteudo_usuario = (
                f"Pergunta do usuário: {texto}\n\n"
                "Contexto local relevante:\n"
                f"{contexto_local}\n\n"
                "Use o contexto quando ajudar a responder. "
                "Não invente fatos que não estejam nele."
            )

            mensagens = self.historico[:-1] + [
                {"role": "user", "content": conteudo_usuario}
            ]

        self.inicio_resposta.emit()
        completo = ""

        try:
            for parte in ollama.chat(
                model=MODELO,
                messages=mensagens,
                stream=True,
                keep_alive="30m",
                options={"num_predict": 300},
            ):
                trecho = parte["message"]["content"]
                completo += trecho
                self.token.emit(trecho)

        except Exception as erro:
            print(f"[erro no Ollama] {erro}")
            self.historico.pop()
            aviso = "Não consegui falar com o Ollama. Verifique se ele está aberto."
            self.token.emit(aviso)
            self.fim_resposta.emit()
            self._falar(aviso)
            return

        self.fim_resposta.emit()
        self.historico.append(
            {"role": "assistant", "content": completo}
        )

        if fontes:
            self.info.emit("Fontes: " + ", ".join(fontes))
        
        # Analisa a mensagem original do usuário após uma resposta bem-sucedida.
        # Não interrompe a conversa caso a memória automática falhe.
        try:
            memorias_novas = extrair_memorias_automaticas(texto)

            for fato in memorias_novas:
                salvo = memoria.salvar_memoria(fato)

                if salvo:
                    self.info.emit("Nova informação adicionada à memória.")
                    print(f"[memória automática] {fato}")

        except Exception as erro:
            print(f"[memória automática] Erro ao salvar: {erro}")

        self._falar(completo)
    

class Monitor(QThread):
    """Verifica de tempos em tempos internet e Ollama (para os indicadores)."""
    internet = pyqtSignal(bool)
    ollama_ok = pyqtSignal(bool)

    def __init__(self):
        super().__init__()
        self.rodando = True

    def run(self):
        while self.rodando:
            self.internet.emit(tem_internet(timeout=2))
            self.ollama_ok.emit(ollama_rodando())
            for _ in range(50):
                if not self.rodando:
                    return
                time.sleep(0.1)