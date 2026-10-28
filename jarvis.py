import asyncio
import os
import re
import socket
import tempfile

import edge_tts
import ollama
import pyttsx3
import speech_recognition as sr
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"
  # esconde a mensagem do pygame
import pygame

MODELO = "qwen2.5:3b"

# Voz online (edge-tts)
VOZ_ONLINE = "pt-BR-AntonioNeural"   # ou "pt-BR-FranciscaNeural"
VELOCIDADE_ONLINE = "+0%"            # ex.: "+10%" mais rápido, "-10%" mais lento

# Voz offline (Windows / pyttsx3)
VOZ_OFFLINE = "maria"                # parte do nome da voz instalada
VELOCIDADE_OFFLINE = 180
VOLUME_OFFLINE = 1.0

reconhecedor = sr.Recognizer()
pygame.mixer.init()

historico = [{
    "role": "system",
    "content": "Você é o Jarvis, um assistente pessoal. Responda em português, em frases curtas, sem listas, sem markdown e sem emojis.",
}]


def tem_internet(timeout=3):
    destinos = [("www.google.com", 443), ("1.1.1.1", 443), ("1.1.1.1", 53)]
    for host, porta in destinos:
        try:
            with socket.create_connection((host, porta), timeout=timeout):
                return True
        except OSError:
            continue
    return False


def limpar(texto):
    """Remove símbolos de markdown para a voz não lê-los."""
    return re.sub(r"[*#`_>]", "", texto)


def falar_offline(texto):
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
    """Fala com o edge-tts. Devolve True se deu certo, False se falhou."""
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
    falar_offline(texto)


def ouvir():
    """Escuta o microfone e devolve o texto (ou '' se não entendeu)."""
    if not tem_internet():
        return input("Sem internet. Digite sua pergunta: ").strip()
    with sr.Microphone() as fonte:
        reconhecedor.adjust_for_ambient_noise(fonte, duration=0.5)
        print("Ouvindo...")
        try:
            audio = reconhecedor.listen(fonte, timeout=5, phrase_time_limit=15)
        except sr.WaitTimeoutError:
            return ""
    try:
        return reconhecedor.recognize_google(audio, language="pt-BR")
    except sr.UnknownValueError:
        return ""
    except sr.RequestError as erro:
        print(f"Falha no serviço de reconhecimento: {erro}")
        return ""


def perguntar(texto):
    historico.append({"role": "user", "content": texto})
    print("Jarvis: ", end="", flush=True)
    completo = ""
    for parte in ollama.chat(
        model=MODELO,
        messages=historico,
        stream=True,
        keep_alive="30m",
        options={"num_predict": 300},
    ):
        trecho = parte["message"]["content"]
        print(trecho, end="", flush=True)
        completo += trecho
    print()
    historico.append({"role": "assistant", "content": completo})
    falar(completo)


try:
    while True:
        texto = ouvir()
        if not texto:
            continue
        print(f"Você: {texto}")
        if texto.lower() in ("sair", "encerrar", "tchau"):
            break
        perguntar(texto)
except KeyboardInterrupt:
    print("\nEncerrado.")