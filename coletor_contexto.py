from __future__ import annotations

from datetime import datetime
from pathlib import Path
import logging
import os
import re
import tempfile
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

BASE_DIR = Path(__file__).resolve().parent
CONTEXTO_DIR = BASE_DIR / "contexto"
ARQUIVO_SAIDA = CONTEXTO_DIR / "SITE_PRINVA.md"
ARQUIVO_LINKEDIN = CONTEXTO_DIR / "LINKEDIN.md"
LOG_DIR = BASE_DIR / "logs"
LOG_FILE = LOG_DIR / "coletor_contexto.log"

PAGINAS_PRINVA = [
    "https://prinva.com.br/",
    "https://prinva.com.br/sobre/",
    "https://prinva.com.br/termos/",
]

MAX_BYTES = 2_000_000
TIMEOUT = (5, 20)
USER_AGENT = "JarvisContextCollector/1.0 (personal knowledge refresh)"


def configurar_log() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=LOG_FILE,
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        encoding="utf-8",
    )


def obter_texto_pagina(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.netloc != "prinva.com.br":
        raise ValueError(f"URL fora da lista permitida: {url}")

    with requests.get(
        url,
        timeout=TIMEOUT,
        headers={"User-Agent": USER_AGENT},
        stream=True,
        allow_redirects=True,
    ) as resposta:
        resposta.raise_for_status()

        final = urlparse(resposta.url)
        if final.scheme != "https" or final.netloc != "prinva.com.br":
            raise ValueError("Redirecionamento para domínio não permitido.")

        tipo = resposta.headers.get("Content-Type", "").lower()
        if "text/html" not in tipo:
            raise ValueError(f"Conteúdo não HTML: {tipo}")

        pedacos = []
        total = 0
        for chunk in resposta.iter_content(chunk_size=16_384):
            if not chunk:
                continue
            total += len(chunk)
            if total > MAX_BYTES:
                raise ValueError("Página excedeu o limite de tamanho.")
            pedacos.append(chunk)

    sopa = BeautifulSoup(b"".join(pedacos), "html.parser")
    for elemento in sopa(["script", "style", "noscript", "svg", "nav", "footer", "header"]):
        elemento.decompose()

    principal = sopa.find("main") or sopa.find("article") or sopa.body or sopa
    texto = principal.get_text("\n", strip=True)
    return re.sub(r"\n{3,}", "\n\n", texto).strip()


def escrever_atomico(caminho: Path, conteudo: str) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    nome_temp = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", newline="\n",
            dir=caminho.parent, delete=False
        ) as temporario:
            temporario.write(conteudo)
            nome_temp = temporario.name
        os.replace(nome_temp, caminho)
    finally:
        if nome_temp and os.path.exists(nome_temp):
            os.unlink(nome_temp)


def atualizar_site() -> bool:
    blocos = [
        "# Contexto público da Prinva",
        "",
        f"Atualizado em: {datetime.now().astimezone().isoformat(timespec='seconds')}",
        "",
        "Conteúdo extraído de páginas públicas da Prinva. Confirme informações "
        "importantes na fonte original, pois o site pode mudar.",
        "",
    ]
    sucessos = 0

    for url in PAGINAS_PRINVA:
        try:
            texto = obter_texto_pagina(url)
            if texto:
                blocos.extend([f"## Fonte: {url}", "", texto, ""])
                sucessos += 1
                logging.info("Página coletada: %s", url)
        except Exception as erro:
            logging.exception("Falha ao coletar %s: %s", url, erro)
            blocos.extend([f"## Fonte indisponível: {url}", "", f"Erro: {erro}", ""])

    if sucessos == 0:
        logging.error("Nenhuma página foi coletada; arquivo anterior preservado.")
        return False

    escrever_atomico(ARQUIVO_SAIDA, "\n".join(blocos).strip() + "\n")
    logging.info("Contexto do site atualizado: %s", ARQUIVO_SAIDA)
    return True


def verificar_linkedin() -> None:
    # Sem login automatizado, scraping de páginas privadas, cookies ou tokens.
    if ARQUIVO_LINKEDIN.exists():
        logging.info("Arquivo LinkedIn existente preservado para atualização manual.")
        return

    modelo = """# Contexto profissional — LinkedIn

Perfil: https://www.linkedin.com/in/nicolas-lanca/
Fonte: informações fornecidas manualmente pelo titular.
Última atualização manual: preencher a data.

## Título profissional
Preencha com o título atual do seu perfil.

## Sobre
Cole aqui a seção “Sobre” do perfil.

## Experiência
Adicione cargos, organizações, datas e principais atividades.

## Formação
Adicione curso, instituição e previsão de conclusão.

## Competências e projetos
Adicione competências, certificações e projetos relevantes.

## Atualização
Atualize manualmente ou importe uma cópia do perfil exportada pelo LinkedIn.
Não inclua senhas, cookies ou tokens de acesso.
"""
    escrever_atomico(ARQUIVO_LINKEDIN, modelo)
    logging.info("Modelo de contexto do LinkedIn criado.")


def main() -> int:
    configurar_log()
    CONTEXTO_DIR.mkdir(parents=True, exist_ok=True)
    site_ok = atualizar_site()
    verificar_linkedin()
    print(f"Site Prinva: {'atualizado' if site_ok else 'falha; contexto anterior preservado'}")
    print(f"Contexto do site: {ARQUIVO_SAIDA}")
    print(f"Contexto LinkedIn: {ARQUIVO_LINKEDIN}")
    print(f"Log: {LOG_FILE}")
    return 0 if site_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
