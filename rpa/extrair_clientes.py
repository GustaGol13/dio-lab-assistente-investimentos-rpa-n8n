#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Assistente de Investimentos - RPA de Extração de Clientes
Pipeline: Web Scraping com BeautifulSoup -> Envio para Webhook N8N

Desafio DIO: Criando um Assistente de Investimentos com RPA e IA Generativa
"""

import os
import sys
import json
import argparse
from pathlib import Path
import requests
from bs4 import BeautifulSoup

# Configuração de encoding para compatibilidade com consoles Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# URL padrão da página simulada no GitHub Pages
DEFAULT_URL_PAGINA = "https://digitalinnovationone.github.io/dio-lab-assistente-investimentos-rpa-n8n/"
DEFAULT_WEBHOOK_URL = "http://localhost:5678/webhook/assistente-investimentos"


def extrair_clientes(url_ou_caminho: str) -> list[dict]:
    """
    Realiza o RPA de extração dos dados dos clientes da tabela HTML.
    Suporta tanto URL remota (HTTP/HTTPS) quanto arquivo HTML local (docs/index.html).
    """
    print(f"\n[RPA] Conectando a fonte de dados: {url_ou_caminho}...")

    if url_ou_caminho.startswith("http://") or url_ou_caminho.startswith("https://"):
        resposta = requests.get(url_ou_caminho, timeout=15)
        resposta.raise_for_status()
        html = resposta.text
    else:
        with open(url_ou_caminho, "r", encoding="utf-8") as f:
            html = f.read()

    soup = BeautifulSoup(html, "html.parser")
    linhas = soup.select("#clientes tbody tr")

    if not linhas:
        print("[RPA] [!] Nenhuma linha encontrada na tabela #clientes.")
        return []

    clientes = []
    for linha in linhas:
        colunas = linha.find_all("td")
        if len(colunas) >= 4:
            cliente = {
                "nome": colunas[0].get_text(strip=True),
                "email": colunas[1].get_text(strip=True),
                "saldo": colunas[2].get_text(strip=True),
                "perfil": colunas[3].get_text(strip=True),
            }
            clientes.append(cliente)

    print(f"[RPA] [OK] Extracao concluida com sucesso! {len(clientes)} clientes coletados.")
    return clientes


def exibir_tabela_clientes(clientes: list[dict]):
    """Imprime uma prévia organizada dos clientes no terminal."""
    print("\n" + "=" * 70)
    print(f"{'NOME':<20} | {'PERFIL':<12} | {'SALDO':<15} | {'EMAIL'}")
    print("-" * 70)
    for c in clientes:
        print(f"{c['nome']:<20} | {c['perfil']:<12} | {c['saldo']:<15} | {c['email']}")
    print("=" * 70 + "\n")


def enviar_para_n8n(clientes: list[dict], webhook_url: str) -> dict | None:
    """Envia o payload JSON com os clientes para o Webhook orquestrador do N8N."""
    print(f"[N8N] Enviando {len(clientes)} clientes para o Webhook: {webhook_url}...")
    payload = {"clientes": clientes}

    try:
        resposta = requests.post(
            webhook_url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=60,
        )

        if resposta.status_code == 200:
            print(f"[N8N] [OK] Sucesso! Status HTTP {resposta.status_code}")
            try:
                dados_retorno = resposta.json()
                return dados_retorno
            except json.JSONDecodeError:
                print("[N8N] [i] Resposta recebida (texto puro):", resposta.text)
                return {"texto": resposta.text}
        else:
            print(f"[N8N] [X] Erro ao enviar para o N8N: HTTP {resposta.status_code}")
            print(f"[N8N] Detalhes do erro: {resposta.text}")
            return None

    except requests.exceptions.ConnectionError:
        print(f"[N8N] [X] Falha de conexao com {webhook_url}.")
        print("[N8N] [Dica] Verifique se o n8n esta rodando e se o workflow esta ativo ou ouvindo em modo de teste.")
        return None
    except Exception as e:
        print(f"[N8N] [X] Ocorreu um erro inesperado: {e}")
        return None


def exibir_retorno_n8n(retorno: dict):
    """Exibe o resultado processado pelo workflow do N8N com formatação amigável."""
    print("\n" + "=" * 75)
    print("RESULTADO DO PROCESSAMENTO N8N - ASSISTENTE DE INVESTIMENTOS")
    print("=" * 75)

    total = retorno.get("total_processado") or retorno.get("total_clientes") or len(retorno.get("resultados", []))
    modo = retorno.get("modo") or retorno.get("tipo_execucao") or "Processamento concluido"
    print(f"Total Processado: {total}")
    print(f"Modo: {modo}")

    resultados = retorno.get("resultados") or retorno.get("recomendacoes") or []

    for i, item in enumerate(resultados, 1):
        print("\n" + "-" * 75)
        print(f"[{i}/{len(resultados)}] Cliente: {item.get('nome')} | Perfil: {item.get('perfil')} | Saldo: {item.get('saldo_original') or item.get('saldo')}")
        if item.get("produto_destaque"):
            print(f"Produto em Destaque: {item.get('produto_destaque')}")
        print("\nMensagem Gerada:")
        print(item.get("mensagem", "Sem mensagem disponivel."))

    print("\n" + "=" * 75)


def main():
    parser = argparse.ArgumentParser(description="RPA de Extração de Clientes e Integração N8N")
    parser.add_argument(
        "--url",
        default=DEFAULT_URL_PAGINA,
        help="URL ou caminho local do HTML contendo a tabela de clientes.",
    )
    parser.add_argument(
        "--webhook",
        default=os.environ.get("N8N_WEBHOOK_URL", ""),
        help="URL do Webhook do N8N (produção ou teste). Se não informado, executa apenas a extração.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Apenas extrai e exibe os dados dos clientes sem enviar para o Webhook.",
    )

    args = parser.parse_args()

    # 1. Executar RPA
    clientes = extrair_clientes(args.url)
    if not clientes:
        print("[ERRO] Nenhum cliente encontrado. Abortando.")
        sys.exit(1)

    exibir_tabela_clientes(clientes)

    # 2. Enviar ao N8N se webhook foi informado e não é dry-run
    if args.dry_run:
        print("[INFO] Modo --dry-run ativo. Os dados nao foram enviados ao Webhook.")
        return

    webhook_url = args.webhook.strip()
    if not webhook_url:
        print("[INFO] Nenhuma URL de Webhook foi informada via --webhook ou N8N_WEBHOOK_URL.")
        print("[INFO] Use --webhook <URL_DO_WEBHOOK> para enviar os clientes ao N8N.")
        return

    retorno = enviar_para_n8n(clientes, webhook_url)
    if retorno:
        exibir_retorno_n8n(retorno)


if __name__ == "__main__":
    main()
