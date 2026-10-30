"""
gerenciador_sistema.py

Objeto que executa operações de arquivos, pastas e sistema a partir de um texto.
Uso em outro arquivo:

    from gerenciador_sistema import GerenciadorSistema

    g = GerenciadorSistema()
    print(g.executar("listar ."))
    print(g.executar('criar arquivo nota.txt "olá mundo"'))
    print(g.executar("ler arquivo nota.txt"))

Toda chamada devolve uma string: o resultado, ou o motivo de não ter sido possível.
"""
import datetime
import os
import shlex
import subprocess
import unicodedata
from dataclasses import dataclass
from typing import Callable


class ErroOperacao(Exception):
    """Erro cuja mensagem já explica o motivo ao usuário."""


@dataclass
class Operacao:
    nome: str
    funcao: Callable
    uso: str
    descricao: str
    min_args: int = 0
    max_args: int = 0          # -1 = sem limite
    destrutiva: bool = False
    aliases: tuple = ()


class GerenciadorSistema:
    def __init__(self, exigir_confirmacao=True, limite_linhas=50,
                 encoding="utf-8", max_bytes_leitura=1_000_000,
                 timeout_comando=30):
        self.exigir_confirmacao = exigir_confirmacao  # operações destrutivas pedem "confirmo"
        self.limite_linhas = limite_linhas            # corta saídas muito longas
        self.encoding = encoding                      # codificação dos arquivos de texto
        self.max_bytes_leitura = max_bytes_leitura    # tamanho máximo para ler um arquivo
        self.timeout_comando = timeout_comando        # segundos para comandos do shell
        self.operacoes = {}
        self._indice = {}
        self._desativadas = {}                        # nome -> motivo
        self._registrar_operacoes()

    # ------------------------------------------------------------------
    # Interface pública
    # ------------------------------------------------------------------
    def executar(self, texto):
        """Interpreta o texto, executa a operação e devolve o resultado em string."""
        if not texto or not texto.strip():
            return "Não recebi nenhum comando. Digite 'ajuda' para ver as operações."

        try:
            tokens = self._separar(texto)
        except ValueError as erro:
            return (f"Não consegui interpretar o texto ({erro}). "
                    "Verifique se todas as aspas foram fechadas.")
        if not tokens:
            return "Não recebi nenhum comando. Digite 'ajuda' para ver as operações."

        operacao, usados = self._encontrar([self._normalizar(t) for t in tokens])
        if operacao is None:
            inicio = " ".join(tokens[:2])
            return (f"Não entendi o comando '{inicio}'. "
                    "Digite 'ajuda' para ver as operações disponíveis.")

        if operacao.nome in self._desativadas:
            return (f"A operação '{operacao.nome}' está desativada: "
                    f"{self._desativadas[operacao.nome]}.")

        args = tokens[usados:]
        confirmado = False
        if operacao.destrutiva and args and self._normalizar(args[-1]) == "confirmo":
            args = args[:-1]
            confirmado = True

        if len(args) < operacao.min_args:
            return (f"Faltam informações para '{operacao.nome}'. "
                    f"Uso: {operacao.uso}")
        if operacao.max_args != -1 and len(args) > operacao.max_args:
            return (f"Há informações demais para '{operacao.nome}'. Uso: {operacao.uso}. "
                    "Se algum caminho tiver espaços, coloque-o entre aspas.")

        if operacao.destrutiva and self.exigir_confirmacao and not confirmado:
            return (f"'{operacao.nome}' não foi executada porque é destrutiva "
                    f"({operacao.descricao}). Para confirmar, repita o comando "
                    "acrescentando 'confirmo' no final.")

        try:
            resultado = operacao.funcao(*args)
        except ErroOperacao as erro:
            return f"Não consegui executar '{operacao.nome}': {erro}"
        except Exception as erro:  # a camada de texto nunca deve quebrar o programa
            return f"Não consegui executar '{operacao.nome}': {self._explicar_erro(erro)}"

        return self._limitar(self._formatar(resultado))

    __call__ = executar

    def reconhece(self, texto):
        """Diz se o texto começa com uma operação conhecida (sem executar nada)."""
        try:
            tokens = self._separar(texto)
        except ValueError:
            return False
        if not tokens:
            return False
        operacao, _ = self._encontrar([self._normalizar(t) for t in tokens])
        return operacao is not None

    def desativar(self, nome, motivo):
        """Bloqueia uma operação; ao ser pedida, o objeto explica o motivo."""
        if nome not in self.operacoes:
            raise KeyError(f"Operação desconhecida: {nome}")
        self._desativadas[nome] = motivo

    # ------------------------------------------------------------------
    # Interpretação do texto
    # ------------------------------------------------------------------
    @staticmethod
    def _separar(texto):
        # posix=False mantém as barras invertidas dos caminhos do Windows
        tokens = shlex.split(texto, posix=False)
        limpos = []
        for t in tokens:
            if len(t) >= 2 and t[0] == t[-1] and t[0] in "\"'":
                t = t[1:-1]
            limpos.append(t)
        return limpos

    @staticmethod
    def _normalizar(texto):
        sem_acento = unicodedata.normalize("NFKD", texto)
        return "".join(c for c in sem_acento if not unicodedata.combining(c)).lower()

    def _encontrar(self, normalizados):
        maior = max(len(chave) for chave in self._indice)
        for n in range(min(maior, len(normalizados)), 0, -1):
            operacao = self._indice.get(tuple(normalizados[:n]))
            if operacao:
                return operacao, n
        return None, 0

    # ------------------------------------------------------------------
    # Formatação e erros
    # ------------------------------------------------------------------
    @staticmethod
    def _formatar(resultado):
        if resultado is None:
            return "Executado com sucesso."
        if isinstance(resultado, bool):
            return "Sim" if resultado else "Não"
        if isinstance(resultado, (list, tuple)):
            return "\n".join(str(item) for item in resultado) or "(vazio)"
        return str(resultado)

    def _limitar(self, texto):
        linhas = texto.splitlines()
        if len(linhas) <= self.limite_linhas:
            return texto
        omitidas = len(linhas) - self.limite_linhas
        return "\n".join(linhas[:self.limite_linhas]) + f"\n... ({omitidas} linhas omitidas)"

    @staticmethod
    def _explicar_erro(erro):
        nome = getattr(erro, "filename", None)
        alvo = f"'{nome}'" if nome else "o caminho informado"
        if isinstance(erro, FileNotFoundError):
            return f"{alvo} não existe (ou alguma pasta do caminho não existe)."
        if isinstance(erro, FileExistsError):
            return f"já existe um arquivo ou pasta com o nome {alvo}."
        if isinstance(erro, PermissionError):
            return (f"sem permissão para acessar {alvo}; ele pode estar aberto "
                    "em outro programa ou protegido pelo sistema.")
        if isinstance(erro, IsADirectoryError):
            return f"{alvo} é uma pasta, e esta operação exige um arquivo."
        if isinstance(erro, NotADirectoryError):
            return f"{alvo} é um arquivo, e esta operação exige uma pasta."
        if isinstance(erro, UnicodeDecodeError):
            return ("o arquivo não é um texto legível na codificação usada; "
                    "ele pode ser binário (imagem, PDF, programa).")
        if isinstance(erro, subprocess.TimeoutExpired):
            return "o comando demorou demais e foi interrompido."
        if isinstance(erro, OSError):
            return f"o sistema operacional recusou a operação ({erro.strerror or erro})."
        if isinstance(erro, ValueError):
            return f"valor inválido ({erro})."
        return f"erro inesperado ({type(erro).__name__}: {erro})."

    # ------------------------------------------------------------------
    # Registro das operações
    # ------------------------------------------------------------------
    def _op(self, nome, funcao, uso, descricao, min_args=0, max_args=0,
            destrutiva=False, aliases=()):
        operacao = Operacao(nome, funcao, uso, descricao, min_args, max_args,
                            destrutiva, tuple(aliases))
        self.operacoes[nome] = operacao
        for chave in (nome, *aliases):
            palavras = tuple(self._normalizar(chave).split())
            self._indice[palavras] = operacao

    def _registrar_operacoes(self):
        op = self._op
        op("ajuda", self._ajuda, "ajuda", "mostra as operações disponíveis",
           aliases=("comandos", "help"))

        # Pasta atual e navegação
        op("pasta_atual", self._pasta_atual, "pasta atual",
           "mostra a pasta de trabalho atual",
           aliases=("pasta atual", "diretorio atual", "onde estou"))
        op("mudar_pasta", self._mudar_pasta, "mudar pasta <caminho>",
           "muda a pasta de trabalho do programa", 1, 1,
           aliases=("mudar pasta", "ir para"))
        op("listar", self._listar, "listar [pasta]",
           "lista arquivos e pastas", 0, 1,
           aliases=("listar", "liste", "mostrar arquivos", "ls", "dir"))
        op("listar_detalhado", self._listar_detalhado, "listar detalhado [pasta]",
           "lista com tipo e tamanho", 0, 1,
           aliases=("listar detalhado", "listar com detalhes"))
        op("percorrer", self._percorrer, "percorrer [pasta]",
           "lista a pasta e todas as subpastas", 0, 1,
           aliases=("percorrer", "listar tudo", "listar subpastas"))

        # Criar, renomear e apagar
        op("criar_pasta", self._criar_pasta, "criar pasta <caminho>",
           "cria uma pasta", 1, 1, aliases=("criar pasta", "nova pasta"))
        op("criar_pastas", self._criar_pastas, "criar pastas <caminho>",
           "cria a pasta e as intermediárias que faltarem", 1, 1,
           aliases=("criar pastas",))
        op("renomear", self._renomear, "renomear <origem> <destino>",
           "renomeia ou move arquivo/pasta", 2, 2, aliases=("renomear", "mover"))
        op("substituir", self._substituir, "substituir <origem> <destino>",
           "move sobrescrevendo o destino *", 2, 2, destrutiva=True,
           aliases=("substituir",))
        op("apagar_arquivo", self._apagar_arquivo, "apagar arquivo <caminho>",
           "apaga um arquivo *", 1, 1, destrutiva=True,
           aliases=("apagar arquivo", "apagar", "remover arquivo", "deletar arquivo"))
        op("apagar_pasta", self._apagar_pasta, "apagar pasta <caminho>",
           "apaga uma pasta vazia *", 1, 1, destrutiva=True,
           aliases=("apagar pasta", "remover pasta"))
        op("apagar_pastas", self._apagar_pastas, "apagar pastas <caminho>",
           "apaga pastas vazias em cadeia *", 1, 1, destrutiva=True,
           aliases=("apagar pastas",))

        # Caminhos
        op("juntar_caminho", self._juntar_caminho, "juntar caminho <parte1> <parte2> ...",
           "junta partes de um caminho", 2, -1, aliases=("juntar caminho",))
        op("existe", self._existe, "existe <caminho>",
           "informa se o caminho existe", 1, 1, aliases=("existe",))
        op("eh_arquivo", self._eh_arquivo, "eh arquivo <caminho>",
           "informa se é um arquivo", 1, 1, aliases=("eh arquivo", "e arquivo"))
        op("eh_pasta", self._eh_pasta, "eh pasta <caminho>",
           "informa se é uma pasta", 1, 1, aliases=("eh pasta", "e pasta"))
        op("caminho_absoluto", self._caminho_absoluto, "caminho absoluto <caminho>",
           "converte para caminho absoluto", 1, 1, aliases=("caminho absoluto",))
        op("nome_arquivo", self._nome_arquivo, "nome arquivo <caminho>",
           "devolve só o nome do arquivo", 1, 1, aliases=("nome arquivo", "nome do arquivo"))
        op("pasta_do_arquivo", self._pasta_do_arquivo, "pasta do arquivo <caminho>",
           "devolve só a pasta do caminho", 1, 1, aliases=("pasta do arquivo",))
        op("separar_extensao", self._separar_extensao, "separar extensao <caminho>",
           "separa o nome da extensão", 1, 1, aliases=("separar extensao", "extensao"))
        op("tamanho", self._tamanho, "tamanho <arquivo>",
           "tamanho do arquivo", 1, 1, aliases=("tamanho",))
        op("data_modificacao", self._data_modificacao, "data modificacao <caminho>",
           "data da última modificação", 1, 1,
           aliases=("data modificacao", "data de modificacao", "modificado em"))
        op("pasta_usuario", self._pasta_usuario, "pasta usuario [~]",
           "resolve a pasta do usuário", 0, 1, aliases=("pasta usuario", "pasta do usuario"))

        # Variáveis de ambiente
        op("ler_variavel", self._ler_variavel, "ler variavel <nome> [padrao]",
           "lê uma variável de ambiente", 1, 2, aliases=("ler variavel", "variavel"))
        op("todas_variaveis", self._todas_variaveis, "todas variaveis",
           "lista todas as variáveis de ambiente", aliases=("todas variaveis", "listar variaveis"))

        # Sistema
        op("cpus", self._cpus, "cpus", "número de processadores", aliases=("cpus", "processadores"))
        op("id_processo", self._id_processo, "id processo",
           "identificador do processo atual", aliases=("id processo",))
        op("tamanho_terminal", self._tamanho_terminal, "tamanho terminal",
           "largura e altura do terminal", aliases=("tamanho terminal",))
        op("abrir_arquivo", self._abrir_arquivo, "abrir arquivo <caminho>",
           "abre com o programa padrão (só Windows)", 1, 1,
           aliases=("abrir arquivo", "abrir"))
        op("executar_comando", self._executar_comando, "executar comando <comando>",
           "executa um comando no shell e devolve a saída *", 1, -1, destrutiva=True,
           aliases=("executar comando", "executar", "cmd"))

        # Permissões e metadados
        op("info_arquivo", self._info_arquivo, "info arquivo <caminho>",
           "tipo, tamanho, datas e permissões", 1, 1,
           aliases=("info arquivo", "info", "informacoes do arquivo"))
        op("tem_permissao", self._tem_permissao, "tem permissao <caminho> [rwx]",
           "verifica leitura (r), escrita (w), execução (x)", 1, 2,
           aliases=("tem permissao", "verificar permissao"))
        op("mudar_permissao", self._mudar_permissao, "mudar permissao <caminho> <modo octal>",
           "altera permissões, como 644 *", 2, 2, destrutiva=True,
           aliases=("mudar permissao",))

        # CRUD de arquivos de texto
        op("criar_arquivo", self._criar_arquivo, "criar arquivo <caminho> [conteudo]",
           "cria um arquivo (não sobrescreve)", 1, -1,
           aliases=("criar arquivo", "novo arquivo"))
        op("ler_arquivo", self._ler_arquivo, "ler arquivo <caminho>",
           "lê um arquivo de texto", 1, 1, aliases=("ler arquivo", "ler"))
        op("atualizar_arquivo", self._atualizar_arquivo, "atualizar arquivo <caminho> <conteudo>",
           "substitui todo o conteúdo *", 1, -1, destrutiva=True,
           aliases=("atualizar arquivo", "atualizar", "sobrescrever arquivo"))
        op("acrescentar_arquivo", self._acrescentar_arquivo,
           "acrescentar arquivo <caminho> <conteudo>",
           "adiciona texto ao final", 2, -1,
           aliases=("acrescentar arquivo", "acrescentar", "adicionar ao arquivo"))

    # ------------------------------------------------------------------
    # Ajuda
    # ------------------------------------------------------------------
    def _ajuda(self):
        linhas = ["Operações disponíveis (* = destrutiva, exige 'confirmo' no final):"]
        for operacao in self.operacoes.values():
            if operacao.nome not in self._desativadas:
                linhas.append(f"{operacao.uso} - {operacao.descricao}")
        return linhas

    # ------------------------------------------------------------------
    # Utilidades internas
    # ------------------------------------------------------------------
    @staticmethod
    def _tamanho_legivel(n):
        valor = float(n)
        for unidade in ("bytes", "KB", "MB", "GB", "TB"):
            if valor < 1024 or unidade == "TB":
                return f"{valor:.0f} bytes" if unidade == "bytes" else f"{valor:.1f} {unidade}"
            valor /= 1024

    @staticmethod
    def _data(timestamp):
        return datetime.datetime.fromtimestamp(timestamp).strftime("%d/%m/%Y %H:%M:%S")

    # ------------------------------------------------------------------
    # Pasta atual e navegação
    # ------------------------------------------------------------------
    def _pasta_atual(self):
        return os.getcwd()

    def _mudar_pasta(self, caminho):
        os.chdir(caminho)
        return f"Pasta de trabalho agora: {os.getcwd()}"

    def _listar(self, caminho="."):
        return sorted(os.listdir(caminho), key=str.lower)

    def _listar_detalhado(self, caminho="."):
        linhas = []
        with os.scandir(caminho) as entradas:
            for entrada in sorted(entradas, key=lambda e: e.name.lower()):
                if entrada.is_dir():
                    linhas.append(f"[pasta]   {entrada.name}")
                else:
                    tamanho = self._tamanho_legivel(entrada.stat().st_size)
                    linhas.append(f"[arquivo] {entrada.name} ({tamanho})")
        return linhas

    def _percorrer(self, caminho="."):
        if not os.path.exists(caminho):
            raise FileNotFoundError(2, "não existe", caminho)
        if not os.path.isdir(caminho):
            raise NotADirectoryError(20, "não é pasta", caminho)
        linhas = []
        for raiz, pastas, arquivos in os.walk(caminho):
            linhas.append(f"{raiz} ({len(pastas)} pastas, {len(arquivos)} arquivos)")
            linhas.extend(f"  - {nome}" for nome in sorted(arquivos, key=str.lower))
        return linhas

    # ------------------------------------------------------------------
    # Criar, renomear e apagar
    # ------------------------------------------------------------------
    def _criar_pasta(self, caminho):
        os.mkdir(caminho)
        return f"Pasta '{caminho}' criada."

    def _criar_pastas(self, caminho):
        existia = os.path.isdir(caminho)
        os.makedirs(caminho, exist_ok=True)
        return f"A pasta '{caminho}' já existia." if existia else f"Pasta '{caminho}' criada."

    def _renomear(self, origem, destino):
        os.rename(origem, destino)
        return f"'{origem}' renomeado/movido para '{destino}'."

    def _substituir(self, origem, destino):
        os.replace(origem, destino)
        return f"'{origem}' movido para '{destino}', sobrescrevendo o que existia."

    def _apagar_arquivo(self, caminho):
        if os.path.isdir(caminho):
            raise ErroOperacao(f"'{caminho}' é uma pasta; use 'apagar pasta'.")
        os.remove(caminho)
        return f"Arquivo '{caminho}' apagado."

    def _exigir_pasta_vazia(self, caminho):
        if not os.path.isdir(caminho):
            if os.path.exists(caminho):
                raise NotADirectoryError(20, "não é pasta", caminho)
            raise FileNotFoundError(2, "não existe", caminho)
        if os.listdir(caminho):
            raise ErroOperacao(f"a pasta '{caminho}' não está vazia; esta operação só "
                               "remove pastas vazias.")

    def _apagar_pasta(self, caminho):
        self._exigir_pasta_vazia(caminho)
        os.rmdir(caminho)
        return f"Pasta '{caminho}' apagada."

    def _apagar_pastas(self, caminho):
        self._exigir_pasta_vazia(caminho)
        os.removedirs(caminho)
        return f"Pasta '{caminho}' e as pastas vazias acima dela foram apagadas."

    # ------------------------------------------------------------------
    # Caminhos
    # ------------------------------------------------------------------
    def _juntar_caminho(self, *partes):
        return os.path.join(*partes)

    def _existe(self, caminho):
        return os.path.exists(caminho)

    def _eh_arquivo(self, caminho):
        return os.path.isfile(caminho)

    def _eh_pasta(self, caminho):
        return os.path.isdir(caminho)

    def _caminho_absoluto(self, caminho):
        return os.path.abspath(caminho)

    def _nome_arquivo(self, caminho):
        return os.path.basename(caminho) or "(o caminho termina em uma pasta, sem nome de arquivo)"

    def _pasta_do_arquivo(self, caminho):
        return os.path.dirname(caminho) or "(o caminho não informa pasta)"

    def _separar_extensao(self, caminho):
        nome, extensao = os.path.splitext(caminho)
        return [f"Nome: {nome}", f"Extensão: {extensao or '(sem extensão)'}"]

    def _tamanho(self, caminho):
        if os.path.isdir(caminho):
            raise ErroOperacao(f"'{caminho}' é uma pasta; esta operação mede arquivos.")
        n = os.path.getsize(caminho)
        if n < 1024:
            return f"{n} bytes"
        return f"{self._tamanho_legivel(n)} ({n} bytes)"

    def _data_modificacao(self, caminho):
        return self._data(os.path.getmtime(caminho))

    def _pasta_usuario(self, caminho="~"):
        return os.path.expanduser(caminho)

    # ------------------------------------------------------------------
    # Variáveis de ambiente
    # ------------------------------------------------------------------
    def _ler_variavel(self, nome, padrao=None):
        valor = os.getenv(nome, padrao)
        if valor is None:
            raise ErroOperacao(f"a variável de ambiente '{nome}' não está definida.")
        return valor

    def _todas_variaveis(self):
        return [f"{k}={v}" for k, v in sorted(os.environ.items())]

    # ------------------------------------------------------------------
    # Sistema
    # ------------------------------------------------------------------
    def _cpus(self):
        n = os.cpu_count()
        if n is None:
            raise ErroOperacao("o sistema não informou o número de processadores.")
        return str(n)

    def _id_processo(self):
        return str(os.getpid())

    def _tamanho_terminal(self):
        try:
            t = os.get_terminal_size()
        except OSError:
            raise ErroOperacao("o programa não está rodando em um terminal (por exemplo, "
                               "na interface gráfica), então não há tamanho de terminal "
                               "para medir.")
        return f"{t.columns} colunas x {t.lines} linhas"

    def _abrir_arquivo(self, caminho):
        if not hasattr(os, "startfile"):
            raise ErroOperacao("abrir com o programa padrão só está disponível no Windows.")
        if not os.path.exists(caminho):
            raise FileNotFoundError(2, "não existe", caminho)
        os.startfile(caminho)
        return f"Abrindo '{caminho}' com o programa padrão."

    def _executar_comando(self, *partes):
        comando = " ".join(partes)
        codificacao = "oem" if os.name == "nt" else "utf-8"  # acentos corretos no Windows
        r = subprocess.run(comando, shell=True, capture_output=True, text=True,
                           encoding=codificacao, errors="replace",
                           timeout=self.timeout_comando)
        saida = (r.stdout + r.stderr).strip()
        if r.returncode != 0:
            saida += f"\n(o comando terminou com código de saída {r.returncode})"
        return saida.strip() or "Executado, sem saída."

    # ------------------------------------------------------------------
    # Permissões e metadados
    # ------------------------------------------------------------------
    def _info_arquivo(self, caminho):
        st = os.stat(caminho)
        tipo = "pasta" if os.path.isdir(caminho) else "arquivo"
        rotulo = "Criado em" if os.name == "nt" else "Metadados alterados em"
        return [
            f"Tipo: {tipo}",
            f"Tamanho: {self._tamanho_legivel(st.st_size)}",
            f"Modificado em: {self._data(st.st_mtime)}",
            f"{rotulo}: {self._data(st.st_ctime)}",
            f"Permissões (octal): {oct(st.st_mode & 0o777)[2:]}",
        ]

    def _tem_permissao(self, caminho, modos="r"):
        if not os.path.exists(caminho):
            raise FileNotFoundError(2, "não existe", caminho)
        mapa = {"r": (os.R_OK, "leitura"), "w": (os.W_OK, "escrita"), "x": (os.X_OK, "execução")}
        linhas = []
        for m in modos.lower():
            if m not in mapa:
                raise ErroOperacao("use apenas as letras r (leitura), w (escrita) e x (execução).")
            flag, nome = mapa[m]
            linhas.append(f"{nome}: {'Sim' if os.access(caminho, flag) else 'Não'}")
        return linhas

    def _mudar_permissao(self, caminho, modo):
        try:
            valor = int(modo, 8)
        except ValueError:
            raise ErroOperacao("o modo deve ser um número octal, como 644 ou 755.")
        os.chmod(caminho, valor)
        aviso = " (no Windows, só o atributo somente leitura é afetado)" if os.name == "nt" else ""
        return f"Permissões de '{caminho}' alteradas para {modo}{aviso}."

    # ------------------------------------------------------------------
    # CRUD de arquivos de texto
    # ------------------------------------------------------------------
    def _criar_arquivo(self, caminho, *conteudo):
        with open(caminho, "x", encoding=self.encoding) as f:  # "x" nunca sobrescreve
            f.write(" ".join(conteudo))
        return f"Arquivo '{caminho}' criado."

    def _ler_arquivo(self, caminho):
        if os.path.isdir(caminho):
            raise IsADirectoryError(21, "é pasta", caminho)
        tamanho = os.path.getsize(caminho)
        if tamanho > self.max_bytes_leitura:
            raise ErroOperacao(f"o arquivo tem {self._tamanho_legivel(tamanho)}, acima do "
                               f"limite de leitura de {self._tamanho_legivel(self.max_bytes_leitura)}.")
        with open(caminho, "r", encoding=self.encoding) as f:
            return f.read() or "(arquivo vazio)"

    def _exigir_arquivo(self, caminho):
        if os.path.isdir(caminho):
            raise IsADirectoryError(21, "é pasta", caminho)
        if not os.path.isfile(caminho):
            raise FileNotFoundError(2, "não existe", caminho)

    def _atualizar_arquivo(self, caminho, *conteudo):
        self._exigir_arquivo(caminho)
        with open(caminho, "w", encoding=self.encoding) as f:
            f.write(" ".join(conteudo))
        return f"Arquivo '{caminho}' atualizado."

    def _acrescentar_arquivo(self, caminho, *conteudo):
        self._exigir_arquivo(caminho)
        with open(caminho, "a", encoding=self.encoding) as f:
            f.write(" ".join(conteudo))
        return f"Conteúdo acrescentado em '{caminho}'."


if __name__ == "__main__":
    gerenciador = GerenciadorSistema()
    print("Digite um comando ('ajuda' para a lista, 'sair' para encerrar).")
    while True:
        entrada = input("> ")
        if entrada.strip().lower() == "sair":
            break
        print(gerenciador.executar(entrada))