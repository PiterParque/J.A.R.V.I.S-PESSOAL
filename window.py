"""
Jarvis: interface futurista (PyQt6).

Execute este arquivo: python jarvis_gui.py
Precisa do jarvis_core.py e do gerenciador_sistema.py na mesma pasta.
"""
import datetime
import math
import sys
import threading

from PyQt6.QtCore import QPointF, QRectF, Qt, QTimer
from PyQt6.QtGui import (QBrush, QColor, QFont, QLinearGradient, QPainter,
                         QPainterPath, QPen, QRadialGradient, QShortcut,
                         QKeySequence, QTextCharFormat, QTextCursor)
from PyQt6.QtWidgets import (QApplication, QHBoxLayout, QLabel, QLineEdit,
                             QPushButton, QSizePolicy, QTextEdit, QVBoxLayout,
                             QWidget)

from jarvis_core import MODELO, Cerebro, Monitor, Ouvinte
import memoria

INICIAR_EM_TELA_CHEIA = True  # F11 alterna; Esc sai da tela cheia

# ============================================================================
# Visual
# ============================================================================
COR_CIANO = "#00E5FF"
COR_TEXTO = "#CFF6FF"
COR_USUARIO = "#6FA8FF"
COR_JARVIS = "#00E5FF"
COR_SISTEMA = "#5E8FA0"
COR_OK = "#3DFFB5"
COR_ERRO = "#FF5C7A"


def rotulo(texto, tamanho=10, cor="#8FD8E8", negrito=False, espaco=0):
    lbl = QLabel(texto)
    fonte = QFont("Consolas", tamanho)
    fonte.setBold(negrito)
    if espaco:
        fonte.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, espaco)
    lbl.setFont(fonte)
    lbl.setStyleSheet(f"color: {cor};")
    return lbl


class Orbe(QWidget):
    """Núcleo animado: anéis girando, brilho central e cor conforme o estado."""
    CORES = {"ocioso": "#1FA8C9", "ouvindo": "#00E5FF",
             "pensando": "#B07CFF", "falando": "#3DFFB5"}
    VELOCIDADES = {"ocioso": 0.6, "ouvindo": 1.0, "pensando": 3.2, "falando": 1.6}
    AMPLITUDES = {"ocioso": 0.03, "ouvindo": 0.06, "pensando": 0.04, "falando": 0.13}

    def __init__(self):
        super().__init__()
        self.estado = "ocioso"
        self.fase = 0.0
        self.cor = QColor(self.CORES["ocioso"])
        self.setMinimumSize(280, 280)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._passo)
        self.timer.start(33)

    def definir_estado(self, estado):
        self.estado = estado

    def _passo(self):
        self.fase += self.VELOCIDADES[self.estado]
        alvo = QColor(self.CORES[self.estado])
        c = self.cor
        self.cor = QColor(
            c.red() + round((alvo.red() - c.red()) * 0.15),
            c.green() + round((alvo.green() - c.green()) * 0.15),
            c.blue() + round((alvo.blue() - c.blue()) * 0.15),
        )
        self.update()

    def paintEvent(self, _evento):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        cx, cy = self.width() / 2, self.height() / 2
        raio = min(self.width(), self.height()) / 2 - 12
        t = self.fase
        cor = self.cor
        amp = self.AMPLITUDES[self.estado]
        pulso = 1 + amp * (0.6 * math.sin(math.radians(t * 9)) + 0.4 * math.sin(math.radians(t * 23)))

        def com_alpha(alpha):
            return QColor(cor.red(), cor.green(), cor.blue(), alpha)

        # brilho central
        r_brilho = raio * 0.58 * pulso
        grad = QRadialGradient(QPointF(cx, cy), r_brilho)
        grad.setColorAt(0.0, QColor(255, 255, 255, 235))
        grad.setColorAt(0.25, com_alpha(210))
        grad.setColorAt(1.0, com_alpha(0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(grad))
        p.drawEllipse(QPointF(cx, cy), r_brilho, r_brilho)
        p.setBrush(Qt.BrushStyle.NoBrush)

        # anel externo fino + marcas
        p.setPen(QPen(com_alpha(90), 1.2))
        p.drawEllipse(QPointF(cx, cy), raio, raio)
        p.setPen(QPen(com_alpha(150), 1.5))
        for i in range(72):
            ang = math.radians(i * 5 + t * 0.25)
            comp = 12 if i % 6 == 0 else 5
            c, s = math.cos(ang), math.sin(ang)
            p.drawLine(QPointF(cx + c * (raio - comp), cy + s * (raio - comp)),
                       QPointF(cx + c * raio, cy + s * raio))

        def arcos(r, quantidade, extensao, largura, alpha, rotacao):
            caneta = QPen(com_alpha(alpha), largura)
            caneta.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(caneta)
            retangulo = QRectF(cx - r, cy - r, 2 * r, 2 * r)
            passo = 360 / quantidade
            for i in range(quantidade):
                inicio = i * passo + rotacao
                p.drawArc(retangulo, int(inicio * 16), int(extensao * 16))

        arcos(raio * 0.86, 3, 80, 3, 230, t * 1.2)
        arcos(raio * 0.72, 2, 120, 5, 170, -t * 2.0)
        arcos(raio * 0.58, 9, 20, 2, 130, t * 0.8)

        # anel interno
        r_int = raio * 0.30 * pulso
        p.setPen(QPen(QColor(255, 255, 255, 200), 1.5))
        p.drawEllipse(QPointF(cx, cy), r_int, r_int)


class Painel(QWidget):
    """Fundo da janela: gradiente escuro, grade HUD, borda neon e colchetes."""

    def __init__(self):
        super().__init__()
        self.raio = 18  # vira 0 em tela cheia (sem cantos arredondados)

    def paintEvent(self, _evento):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        caminho = QPainterPath()
        caminho.addRoundedRect(QRectF(1, 1, w - 2, h - 2), self.raio, self.raio)

        grad = QLinearGradient(0, 0, 0, h)
        grad.setColorAt(0, QColor(6, 16, 30, 245))
        grad.setColorAt(1, QColor(2, 6, 14, 245))
        p.fillPath(caminho, QBrush(grad))

        p.setClipPath(caminho)
        p.setPen(QPen(QColor(0, 229, 255, 14), 1))
        for x in range(0, w, 40):
            p.drawLine(x, 0, x, h)
        for y in range(0, h, 40):
            p.drawLine(0, y, w, y)
        p.setClipping(False)

        p.setPen(QPen(QColor(0, 229, 255, 110), 1.5))
        p.drawPath(caminho)

        caneta = QPen(QColor(0, 229, 255, 230), 2.5)
        caneta.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(caneta)
        m, c = 10, 28
        for x, y, dx, dy in ((m, m, 1, 1), (w - m, m, -1, 1),
                             (m, h - m, 1, -1), (w - m, h - m, -1, -1)):
            p.drawLine(x, y, x + dx * c, y)
            p.drawLine(x, y, x, y + dy * c)


class BarraTitulo(QWidget):
    """Área arrastável no topo (a janela não tem a moldura padrão do Windows)."""

    def mousePressEvent(self, evento):
        if evento.button() == Qt.MouseButton.LeftButton:
            janela = self.window().windowHandle()
            if janela:
                janela.startSystemMove()


ESTILO = f"""
QTextEdit, QLineEdit {{
    background: rgba(0, 20, 35, 150);
    border: 1px solid rgba(0, 229, 255, 90);
    border-radius: 8px;
    color: {COR_TEXTO};
    padding: 10px;
    selection-background-color: #0A5A70;
}}
QLineEdit:focus {{ border: 1px solid {COR_CIANO}; }}
QPushButton {{
    background: rgba(0, 229, 255, 25);
    color: {COR_CIANO};
    border: 1px solid rgba(0, 229, 255, 140);
    border-radius: 6px;
    padding: 9px 16px;
    font-weight: bold;
}}
QPushButton:hover {{ background: rgba(0, 229, 255, 60); }}
QPushButton:checked {{ background: rgba(0, 229, 255, 95); color: #FFFFFF; }}
QPushButton#janela, QPushButton#fechar {{ padding: 4px 11px; border-radius: 4px; }}
QPushButton#fechar:hover {{ background: rgba(255, 60, 90, 150); color: #FFFFFF; }}
QScrollBar:vertical {{ background: transparent; width: 8px; }}
QScrollBar::handle:vertical {{ background: rgba(0, 229, 255, 110); border-radius: 4px; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
"""

TEXTOS_ESTADO = {"ocioso": "EM ESPERA", "ouvindo": "OUVINDO",
                 "pensando": "PROCESSANDO", "falando": "RESPONDENDO"}


class JanelaJarvis(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("J.A.R.V.I.S")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setStyleSheet(ESTILO)
        self.resize(1040, 660)
        self.setMinimumSize(900, 580)
        self.estado_cerebro = "ocioso"
        self._primeiro_token = False  # True logo após "JARVIS ▸ ", até chegar o 1º trecho

        self._montar_interface()
        QShortcut(QKeySequence("F11"), self).activated.connect(self.alternar_tela_cheia)
        QShortcut(QKeySequence("Esc"), self).activated.connect(self.sair_tela_cheia)
        self._iniciar_threads()

        self._inserir("[sistema] Módulos iniciados. Fale, ou digite abaixo.\n", COR_SISTEMA)
        self._inserir("[sistema] Arquivos e pastas: comece com 'sistema' (ex.: sistema listar .). "
                      "Digite 'sistema ajuda' para ver todas as operações.\n\n", COR_SISTEMA)
        self._atualizar_estado()

    # ------------------------------------------------------------------ UI
    def _montar_interface(self):
        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        painel = Painel()
        self.painel = painel
        raiz.addWidget(painel)

        corpo = QVBoxLayout(painel)
        corpo.setContentsMargins(26, 16, 26, 20)
        corpo.setSpacing(14)

        # --- cabeçalho
        barra = BarraTitulo()
        cab = QHBoxLayout(barra)
        cab.setContentsMargins(0, 0, 0, 0)
        titulos = QVBoxLayout()
        titulos.setSpacing(0)
        titulos.addWidget(rotulo("J.A.R.V.I.S", 18, COR_CIANO, True, 6))
        titulos.addWidget(rotulo("SISTEMA PESSOAL DE ASSISTÊNCIA  //  v0.1", 8, "#3F8FA3", False, 2))
        cab.addLayout(titulos)
        cab.addStretch()
        self.lbl_relogio = rotulo("", 11, "#8FD8E8", False, 2)
        cab.addWidget(self.lbl_relogio)
        cab.addSpacing(18)
        btn_tela = QPushButton("□")
        btn_tela.setObjectName("janela")
        btn_tela.setToolTip("Tela cheia (F11)")
        btn_tela.clicked.connect(self.alternar_tela_cheia)
        btn_min = QPushButton("—")
        btn_min.setObjectName("janela")
        btn_min.clicked.connect(self.showMinimized)
        btn_fechar = QPushButton("✕")
        btn_fechar.setObjectName("fechar")
        btn_fechar.clicked.connect(self.close)
        cab.addWidget(btn_tela)
        cab.addWidget(btn_min)
        cab.addWidget(btn_fechar)
        corpo.addWidget(barra)

        # --- corpo: esquerda (orbe + status) e direita (log + entrada)
        centro = QHBoxLayout()
        centro.setSpacing(24)
        corpo.addLayout(centro, 1)

        esquerda = QVBoxLayout()
        self.orbe = Orbe()
        esquerda.addWidget(self.orbe, 1)
        self.lbl_estado = rotulo("EM ESPERA", 13, COR_CIANO, True, 4)
        self.lbl_estado.setAlignment(Qt.AlignmentFlag.AlignCenter)
        esquerda.addWidget(self.lbl_estado)
        esquerda.addSpacing(8)
        self.chip_internet = rotulo("", 9)
        self.chip_ollama = rotulo("", 9)
        self.chip_modelo = rotulo("", 9)
        for chip in (self.chip_internet, self.chip_ollama, self.chip_modelo):
            chip.setTextFormat(Qt.TextFormat.RichText)
            esquerda.addWidget(chip)
        self._definir_chip(self.chip_internet, "INTERNET", None)
        self._definir_chip(self.chip_ollama, "OLLAMA  ", None)
        self.chip_modelo.setText(f"MODELO&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<span style='color:{COR_CIANO}'>{MODELO}</span>")
        coluna_esq = QWidget()
        coluna_esq.setLayout(esquerda)
        coluna_esq.setFixedWidth(340)
        centro.addWidget(coluna_esq)

        direita = QVBoxLayout()
        direita.setSpacing(10)
        direita.addWidget(rotulo("REGISTRO DE COMUNICAÇÃO", 9, "#3F8FA3", True, 3))
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setFont(QFont("Consolas", 11))
        direita.addWidget(self.log, 1)

        linha = QHBoxLayout()
        self.entrada = QLineEdit()
        self.entrada.setFont(QFont("Consolas", 11))
        self.entrada.setPlaceholderText(
            "Pergunta ou comando (ex.: sistema listar .) e pressione Enter...")
        self.entrada.returnPressed.connect(self._enviar_digitado)
        btn_enviar = QPushButton("ENVIAR")
        btn_enviar.clicked.connect(self._enviar_digitado)
        self.btn_sistema = QPushButton("SISTEMA")
        self.btn_sistema.setToolTip(
            "Prepara o campo para operações de arquivos e pastas "
            "(insere 'sistema ' no início)")
        self.btn_sistema.clicked.connect(self._preparar_sistema)
        self.btn_voz = QPushButton("VOZ ATIVA")
        self.btn_voz.setCheckable(True)
        self.btn_voz.setChecked(True)
        self.btn_voz.toggled.connect(self._alternar_voz)
        self.btn_som = QPushButton("SOM")
        self.btn_som.setCheckable(True)
        self.btn_som.setChecked(True)
        self.btn_som.toggled.connect(self._alternar_som)
        linha.addWidget(self.entrada, 1)
        linha.addWidget(btn_enviar)
        linha.addWidget(self.btn_sistema)
        linha.addWidget(self.btn_voz)
        linha.addWidget(self.btn_som)
        direita.addLayout(linha)
        centro.addLayout(direita, 1)

        # relógio
        self.timer_relogio = QTimer(self)
        self.timer_relogio.timeout.connect(self._atualizar_relogio)
        self.timer_relogio.start(1000)
        self._atualizar_relogio()

    def _iniciar_threads(self):
        self.ocupado = threading.Event()
        self.ouvinte = Ouvinte(self.ocupado)
        self.cerebro = Cerebro(self.ocupado)
        self.monitor = Monitor()

        self.ouvinte.texto_ouvido.connect(self._receber_usuario)
        self.ouvinte.aviso.connect(self._aviso)
        self.cerebro.estado.connect(self._mudou_estado_cerebro)
        self.cerebro.inicio_resposta.connect(self._inicio_resposta)
        self.cerebro.token.connect(self._token)
        self.cerebro.fim_resposta.connect(self._fim_resposta)
        self.cerebro.encerrar.connect(self._encerrar_depois)
        self.cerebro.info.connect(self._aviso)
        self.monitor.internet.connect(lambda ok: self._definir_chip(self.chip_internet, "INTERNET", ok))
        self.monitor.ollama_ok.connect(lambda ok: self._definir_chip(self.chip_ollama, "OLLAMA  ", ok))

        for t in (self.cerebro, self.ouvinte, self.monitor):
            t.start()

    # ------------------------------------------------------------ helpers
    def _definir_chip(self, chip, nome, ok):
        if ok is None:
            valor = f"<span style='color:{COR_SISTEMA}'>● VERIFICANDO</span>"
        elif ok:
            valor = f"<span style='color:{COR_OK}'>● ONLINE</span>"
        else:
            valor = f"<span style='color:{COR_ERRO}'>● OFFLINE</span>"
        nome_html = nome.replace(" ", "&nbsp;")
        chip.setText(f"{nome_html}&nbsp;&nbsp;{valor}")

    def _atualizar_relogio(self):
        self.lbl_relogio.setText(datetime.datetime.now().strftime("%H:%M:%S   %d/%m/%Y"))

    def _inserir(self, texto, cor, negrito=False):
        cursor = self.log.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        formato = QTextCharFormat()
        formato.setForeground(QColor(cor))
        fonte = QFont("Consolas", 11)
        fonte.setBold(negrito)
        formato.setFont(fonte)
        cursor.insertText(texto, formato)
        self.log.setTextCursor(cursor)
        self.log.ensureCursorVisible()

    def _atualizar_estado(self):
        if self.estado_cerebro in ("pensando", "falando"):
            estado = self.estado_cerebro
        elif self.ouvinte.escutando:
            estado = "ouvindo"
        else:
            estado = "ocioso"
        self.orbe.definir_estado(estado)
        self.lbl_estado.setText(TEXTOS_ESTADO[estado])

    # ------------------------------------------------------------- eventos
    def _enviar_digitado(self):
        texto = self.entrada.text().strip()
        if texto:
            self.entrada.clear()
            self._receber_usuario(texto)

    def _preparar_sistema(self):
        """Atalho: coloca 'sistema ' no começo do campo para operações de arquivos."""
        texto = self.entrada.text()
        if not texto.lower().lstrip().startswith("sistema"):
            self.entrada.setText("sistema " + texto.lstrip())
        self.entrada.setFocus()
        self.entrada.setCursorPosition(len(self.entrada.text()))

    def _receber_usuario(self, texto):
        self._inserir("VOCÊ ▸ ", COR_USUARIO, True)
        self._inserir(texto + "\n\n", COR_TEXTO)
        self.cerebro.enviar(texto)

    def _aviso(self, mensagem):
        self._inserir(f"[sistema] {mensagem}\n\n", COR_SISTEMA)

    def _mudou_estado_cerebro(self, estado):
        self.estado_cerebro = estado
        self._atualizar_estado()

    def _inicio_resposta(self):
        self._inserir("JARVIS ▸ ", COR_JARVIS, True)
        self._primeiro_token = True

    def _token(self, trecho):
        # Resultados com várias linhas (listas de arquivos, ajuda) começam
        # abaixo do rótulo "JARVIS ▸", para as colunas não ficarem tortas.
        if self._primeiro_token and "\n" in trecho.strip():
            self._inserir("\n", COR_TEXTO)
        self._primeiro_token = False
        self._inserir(trecho, COR_TEXTO)

    def _fim_resposta(self):
        self._inserir("\n\n", COR_TEXTO)

    def _alternar_voz(self, ativa):
        self.ouvinte.escutando = ativa
        self.btn_voz.setText("VOZ ATIVA" if ativa else "VOZ PAUSADA")
        self._atualizar_estado()

    def _alternar_som(self, ativo):
        self.cerebro.som = ativo
        self.btn_som.setText("SOM" if ativo else "MUDO")

    def _encerrar_depois(self):
        QTimer.singleShot(300, self.close)

    def alternar_tela_cheia(self):
        if self.isFullScreen():
            self.painel.raio = 18
            self.showNormal()
        else:
            self.painel.raio = 0
            self.showFullScreen()
        self.painel.update()

    def sair_tela_cheia(self):
        if self.isFullScreen():
            self.alternar_tela_cheia()

    def closeEvent(self, evento):
        self.ouvinte.rodando = False
        self.cerebro.rodando = False
        self.monitor.rodando = False
        for t in (self.ouvinte, self.cerebro, self.monitor):
            if not t.wait(1500):
                t.terminate()
                t.wait(500)
        super().closeEvent(evento)


def main():
    app = QApplication(sys.argv)
    app.setFont(QFont("Consolas", 10))
    janela = JanelaJarvis()
    janela.show()
    if INICIAR_EM_TELA_CHEIA:
        janela.alternar_tela_cheia()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()