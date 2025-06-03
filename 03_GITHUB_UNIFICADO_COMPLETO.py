# -*- coding: utf-8 -*-
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
import pandas as pd
import time
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import re
import numpy as np
from email.message import EmailMessage
import smtplib
import os
import tempfile

EMAIL_SENHA_APP = os.environ["EMAIL_SENHA_APP"]
EMAIL_REMETENTE = os.environ["EMAIL_REMETENTE"]
EMAIL_DESTINATARIO = os.environ["EMAIL_DESTINATARIO"]

####################################################################################### ETAPA 1: EXTRAÇÃO DE JOGOS DO DIA DE AMANHÃ

# Define data do dia seguinte no formato dd-mm-aaaa e yyyymmdd
data_atual = (datetime.now() + timedelta(days=1))
data_str_formatada = data_atual.strftime("%d-%m-%Y")
data_url_formatada = data_atual.strftime("%Y%m%d")

# Configurar as opções do Chrome
chrome_options = Options()
chrome_options.add_experimental_option("prefs", {"profile.managed_default_content_settings.images": 2})
chrome_options.add_argument('--ignore-certificate-errors')
chrome_options.add_argument('--ignore-ssl-errors')

# Instanciar o navegador
user_data_dir = tempfile.mkdtemp()  # cria um diretório temporário único
chrome_options.add_argument(f'--user-data-dir={user_data_dir}')  # força uso de diretório exclusivo
chrome_options.add_argument('--headless')
chrome_options.add_argument('--no-sandbox')
chrome_options.add_argument('--disable-dev-shm-usage')
chrome_options.add_argument('--disable-gpu')
driver = webdriver.Chrome(options=chrome_options)
time.sleep(2)
driver.maximize_window()
time.sleep(2)

# Acessar o site com a data automatizada
url = f'https://www.futbol24.com/Live/?__igp=1&LiveDate={data_url_formatada}'
driver.get(url)
time.sleep(3)  # Aguarda o carregamento da página

# Encontrar o elemento <tbody>
element = driver.find_element(By.CSS_SELECTOR, '#f24com_tablefixtures > tbody')

# Usar BeautifulSoup para analisar o conteúdo HTML
soup = BeautifulSoup(element.get_attribute('innerHTML'), 'html.parser')

# Encontrar todos os elementos <tr> com "match" na classe
rows_with_match = soup.find_all('tr', class_=lambda x: x and 'match' in x)

# Função para limpar os nomes dos times
def limpar_nome(nome):
    if nome:
        nome = re.sub(r'\(\d+\)', '', nome)                      # remove (1), (2), etc.
        nome = re.sub(r'1st leg: [\d-]+', '', nome)              # remove "1st leg: 0-0"
        nome = re.sub(r'Agg\.: [\d-]+', '', nome)                # remove "Agg.: 2-3"
        return nome.strip()
    return None

data = []
for row in rows_with_match:
    league = row.find(class_="league alt")
    home = row.find(class_="home")
    guest = row.find(class_="guest")
    # Captura os textos dos elementos encontrados com limpeza
    league_text = league.get_text(strip=True) if league else None
    home_text = limpar_nome(home.get_text(strip=True)) if home else None
    guest_text = limpar_nome(guest.get_text(strip=True)) if guest else None
    data.append([home_text, guest_text, league_text])

# Lista de competições filtradas
competitions = ["COL D1", "COL D1F", "BRA D1", "BRA D2", "BRA Cup", "ARG D1", "ARG Cup", "PER D1", "PAR D1", "URU D1", "BOL D1", "MEX D1PO", "UEFA CL", "ITA D1", "ITA D2", "ITA Cup", "SPA D1", "ENG PR", "ENG LCh", "FRA D1", "ENG Cup", "GER D1", "HOL D1", "POR D1", "CON CLA", "CON CSA", "ECU D1", "CHI D1", "CHI Cup", "UEFA EL", "UEFA ECL", "TUR D1", "GRE D1", "IRL D1", "JPN D1", "RUS D1", "SCO PR", "BEL D1", "GER Cup", "SPA Cup", "SPA D2", "HOL Cup", "POR Cup", "URU Cup", "PAR Cup", "KSA D1", "FIFA IC", "COL Cup", "MAR D1", "ITA SC", "POR LC", "ENG LC", "TUR Cup", "GER D2"]

# Filtrar apenas os dados das competições desejadas
fdata = [row for row in data if row[2] in competitions]

# Criar DataFrame
df = pd.DataFrame(fdata, columns=["Casa", "Visitante", "Campeonato"])

# Salvar como CSV
nome_arquivo = f"CONFRONTOS_{data_str_formatada}.csv"
df.to_csv(nome_arquivo, sep=";", encoding='utf-8-sig', index=False, header=True)

driver.close() # fecha o driver porque vamos abri-lo mais tarde

df_confrontos = pd.read_csv(f"CONFRONTOS_{data_str_formatada}.csv", sep=";") # 1. Carrega o CSV com confrontos (já gerado pelo script anterior)

todos_times = pd.unique(pd.Series(df_confrontos["Casa"].tolist() + df_confrontos["Visitante"].tolist())) # 2.1 Cria lista única de times
df_times = pd.DataFrame({"Time": todos_times}) # 2.2 Cria lista única de times

# 3. Carrega o CSV com links diretos
# Esse CSV precisa ter colunas: 'Time' e 'Link'
df_links = pd.read_csv("links_times.csv", sep=";", encoding="utf-8-sig")

# 4. Faz o merge para associar links aos times encontrados
df_times = df_times.merge(df_links, on="Time", how="left")
df_times.to_csv(f"LINKS_ENCONTRADOS_{data_str_formatada}.csv", sep=";", index=False, encoding="utf-8-sig")

nome_arquivo_txt = f"urls_jogos_do_dia_{data_str_formatada}.txt" # Supondo que seu DataFrame com links seja df_times

df_times.iloc[:, 1].dropna().to_csv(nome_arquivo_txt, index=False, header=False) # Extrai a coluna de links (segunda coluna)

####################################################################################### ETAPA 2: EXTRAÇÃO DE HISTÓRICO DE JOGOS

user_data_dir = tempfile.mkdtemp()  # cria um diretório temporário único
chrome_options.add_argument(f'--user-data-dir={user_data_dir}')  # força uso de diretório exclusivo
chrome_options.add_argument('--headless')
chrome_options.add_argument('--no-sandbox')
chrome_options.add_argument('--disable-dev-shm-usage')
chrome_options.add_argument('--disable-gpu')
driver = webdriver.Chrome(options=chrome_options)
time.sleep(10)
driver.maximize_window()
time.sleep(2)

urls_jogos_do_dia = []
with open(nome_arquivo_txt, 'r') as f:
    urls_jogos_do_dia = [line.strip() for line in f]

# Inicializa uma lista para armazenar os dataframes
dfs = []

for url in urls_jogos_do_dia:
    driver.get(url)
    time.sleep(3)  # Ajuste este tempo conforme necessário para garantir o carregamento da página
    table = driver.find_element(By.CSS_SELECTOR, '#statTR > div.table.loadingContainer > table > tbody')
    soup = BeautifulSoup(table.get_attribute('innerHTML'), 'html.parser')
    data = []
    
    for row in soup.find_all('tr'):
        row_data = [cell.get_text().split("/")[0] if i == 3 else cell.get_text() 
                    for i, cell in enumerate(row.find_all('td'))]
        data.append(row_data)
    
    df = pd.DataFrame(data)
    
    # Dividir a coluna do placar em duas colunas separadas
    new_columns = df[3].str.split('-', expand=True)
    new_columns.columns = ['Placar casa', 'Placar visitante']
    df_final = pd.concat([df.iloc[:, :3], new_columns, df.iloc[:, 4:]], axis=1)
    df_final = df_final.drop(df_final.columns[-1], axis=1)
    df_final.columns = ['Data', 'Campeonato', 'Time da casa', 'Placar casa', 'Placar visitante', 'Time visitante']
    df_final["Data"] = df_final["Data"].str.replace(".", "/")
    dfs.append(df_final)

# Combinar todos os dataframes em um único DataFrame
df_final = pd.concat(dfs, ignore_index=True).drop_duplicates()
df_final = df_final[~df_final['Placar visitante'].str.contains("W.O.", na=False)]
df_final = df_final[~df_final['Placar casa'].str.contains("P|CANC", na=False)]
df_final.replace({" AET": "", " ABD": ""}, regex=True, inplace=True)

# Salvar o dataframe como um arquivo CSV
nomedoarquivo = f"historico_times_{data_str_formatada}.csv"
df_final.to_csv(nomedoarquivo, sep=";", encoding='utf-8-sig', index=False, header=True)

# Fechar o driver no final
driver.close()
print("sucesso!")

####################################################################################### ETAPA 3: CÁLCULO


# === CONFIGURAÇÕES INICIAIS DE DATA ===
data_atual = (datetime.now() + timedelta(days=1))
data_str_formatada = data_atual.strftime("%d-%m-%Y")

# === CARREGAMENTO DOS ARQUIVOS ===
df_confrontos = pd.read_csv(f"CONFRONTOS_{data_str_formatada}.csv", sep=";")
df_historico = pd.read_csv(f"historico_times_{data_str_formatada}.csv", sep=";")
df_historico["Data"] = pd.to_datetime(df_historico["Data"], errors="coerce", dayfirst=True)
df_historico["Ano-Mês"] = df_historico["Data"].dt.to_period("M")
mand = df_historico[["Ano-Mês", "Time da casa", "Placar casa", "Placar visitante"]].copy()

# === PRÉ-PROCESSAMENTO DO HISTÓRICO ===
df_historico["Data"] = pd.to_datetime(df_historico["Data"], format="%d/%m/%Y", errors="coerce")
df_historico["Placar casa"] = pd.to_numeric(df_historico["Placar casa"], errors="coerce")
df_historico["Placar visitante"] = pd.to_numeric(df_historico["Placar visitante"], errors="coerce")
df_historico.dropna(subset=["Data", "Placar casa", "Placar visitante"], inplace=True)

# === ESTATÍSTICAS DOS ÚLTIMOS 6 MESES ===
limite_6m = datetime.now() - timedelta(days=180)
df_6m = df_historico[df_historico["Data"] >= limite_6m]

def calcular_estatisticas(df):
    jogos_casa = df['Time da casa'].value_counts()
    jogos_visit = df['Time visitante'].value_counts()
    jogos = jogos_casa.add(jogos_visit, fill_value=0).astype(int)
    index_times = jogos.index  # times com pelo menos 1 jogo
    vitorias = pd.Series(0, index=index_times)
    empates = pd.Series(0, index=index_times)
    vitorias_casa = df[df["Placar casa"] > df["Placar visitante"]]["Time da casa"].value_counts()
    vitorias_fora = df[df["Placar visitante"] > df["Placar casa"]]["Time visitante"].value_counts()
    vitorias = vitorias.add(vitorias_casa, fill_value=0)
    vitorias = vitorias.add(vitorias_fora, fill_value=0).astype(int)
    empates_casa = df[df["Placar casa"] == df["Placar visitante"]]["Time da casa"].value_counts()
    empates_fora = df[df["Placar casa"] == df["Placar visitante"]]["Time visitante"].value_counts()
    empates = empates.add(empates_casa, fill_value=0)
    empates = empates.add(empates_fora, fill_value=0).astype(int)
    derrotas = jogos - vitorias - empates
    gf_casa = df.groupby("Time da casa")["Placar casa"].sum()
    gs_casa = df.groupby("Time da casa")["Placar visitante"].sum()
    gf_visit = df.groupby("Time visitante")["Placar visitante"].sum()
    gs_visit = df.groupby("Time visitante")["Placar casa"].sum()
    gols_feitos = gf_casa.add(gf_visit, fill_value=0).reindex(index_times, fill_value=0)
    gols_sofridos = gs_casa.add(gs_visit, fill_value=0).reindex(index_times, fill_value=0)
    saldo = gols_feitos - gols_sofridos
    media_gf = (gols_feitos / jogos).round(2)
    media_gs = (gols_sofridos / jogos).round(2)
    aproveitamento = (((vitorias * 3 + empates) / (jogos * 3)) * 100).round(1)
    return jogos, vitorias, empates, derrotas, gols_feitos, gols_sofridos, saldo, media_gf, media_gs, aproveitamento

(j6, v6, e6, d6, gf6, gs6, saldo6, mgf6, mgs6, ap6) = calcular_estatisticas(df_6m)

for lado in ['Casa', 'Visitante']:
    df_confrontos[f'6m Jogos {lado}'] = df_confrontos[lado].map(j6).fillna(0).astype(int)
    df_confrontos[f'6m Vitórias {lado}'] = df_confrontos[lado].map(v6).fillna(0).astype(int)
    df_confrontos[f'6m Empates {lado}'] = df_confrontos[lado].map(e6).fillna(0).astype(int)
    df_confrontos[f'6m Derrotas {lado}'] = df_confrontos[lado].map(d6).fillna(0).astype(int)
    df_confrontos[f'6m Gols Feitos {lado}'] = df_confrontos[lado].map(gf6).fillna(0).astype(int)
    df_confrontos[f'6m Gols Sofridos {lado}'] = df_confrontos[lado].map(gs6).fillna(0).astype(int)
    df_confrontos[f'6m Saldo de Gols {lado}'] = df_confrontos[f'6m Gols Feitos {lado}'] - df_confrontos[f'6m Gols Sofridos {lado}']
    df_confrontos[f'6m Média Gols Feitos {lado}'] = df_confrontos[lado].map(mgf6).fillna(0)
    df_confrontos[f'6m Média Gols Sofridos {lado}'] = df_confrontos[lado].map(mgs6).fillna(0)
    df_confrontos[f'6m Aproveitamento {lado} (%)'] = df_confrontos[lado].map(ap6).fillna(0)

# === ESTATÍSTICAS DOS ÚLTIMOS 5 JOGOS === 
df_mand = df_historico[["Data", "Time da casa", "Placar casa", "Placar visitante", "Time visitante"]].copy()
df_mand.columns = ["Data", "Time", "Gols Feitos", "Gols Sofridos", "Adversario"]
df_visit = df_historico[["Data", "Time visitante", "Placar visitante", "Placar casa", "Time da casa"]].copy()
df_visit.columns = ["Data", "Time", "Gols Feitos", "Gols Sofridos", "Adversario"]
df_jogos = pd.concat([df_mand, df_visit], ignore_index=True)
df_jogos.sort_values(by=["Time", "Data"], ascending=[True, False], inplace=True)
df_top5 = df_jogos.groupby("Time").head(5)

def calcular_estatisticas_unificado(df):
    jogos = df.groupby("Time").size()
    index_times = jogos.index
    vitorias = pd.Series(0, index=index_times)
    empates = pd.Series(0, index=index_times)
    derrotas = pd.Series(0, index=index_times)
    for time in index_times:
        subset = df[df["Time"] == time]
        vitorias[time] = (subset["Gols Feitos"] > subset["Gols Sofridos"]).sum()
        empates[time] = (subset["Gols Feitos"] == subset["Gols Sofridos"]).sum()
        derrotas[time] = (subset["Gols Feitos"] < subset["Gols Sofridos"]).sum()
    gols_feitos = df.groupby("Time")["Gols Feitos"].sum().reindex(index_times, fill_value=0)
    gols_sofridos = df.groupby("Time")["Gols Sofridos"].sum().reindex(index_times, fill_value=0)
    saldo = gols_feitos - gols_sofridos
    media_gf = (gols_feitos / jogos).round(2)
    media_gs = (gols_sofridos / jogos).round(2)
    aproveitamento = (((vitorias * 3 + empates) / (jogos * 3)) * 100).round(1)
    return jogos, vitorias, empates, derrotas, gols_feitos, gols_sofridos, saldo, media_gf, media_gs, aproveitamento

(j5, v5, e5, d5, gf5, gs5, saldo5, mgf5, mgs5, ap5) = calcular_estatisticas_unificado(df_top5)

for lado in ['Casa', 'Visitante']:
    df_confrontos[f'5J Jogos {lado}'] = df_confrontos[lado].map(j5).fillna(0).astype(int)
    df_confrontos[f'5J Vitórias {lado}'] = df_confrontos[lado].map(v5).fillna(0).astype(int)
    df_confrontos[f'5J Empates {lado}'] = df_confrontos[lado].map(e5).fillna(0).astype(int)
    df_confrontos[f'5J Derrotas {lado}'] = df_confrontos[lado].map(d5).fillna(0).astype(int)
    df_confrontos[f'5J Gols Feitos {lado}'] = df_confrontos[lado].map(gf5).fillna(0).astype(int)
    df_confrontos[f'5J Gols Sofridos {lado}'] = df_confrontos[lado].map(gs5).fillna(0).astype(int)
    df_confrontos[f'5J Saldo de Gols {lado}'] = df_confrontos[f'5J Gols Feitos {lado}'] - df_confrontos[f'5J Gols Sofridos {lado}']
    df_confrontos[f'5J Média Gols Feitos {lado}'] = df_confrontos[lado].map(mgf5).fillna(0)
    df_confrontos[f'5J Média Gols Sofridos {lado}'] = df_confrontos[lado].map(mgs5).fillna(0)
    df_confrontos[f'5J Aproveitamento {lado} (%)'] = df_confrontos[lado].map(ap5).fillna(0)

# === ESTATÍSTICAS DERIVADAS ===
for lado in ['Casa', 'Visitante']: #MÉDIAS GERAIS FEITOS E SOFRIDOS
    df_confrontos[f'Média Geral Feitos {lado}'] = ((df_confrontos[f'6m Média Gols Feitos {lado}'] + 2 * df_confrontos[f'5J Média Gols Feitos {lado}']) / 3).round(2)
    df_confrontos[f'Média Geral Sofridos {lado}'] = ((df_confrontos[f'6m Média Gols Sofridos {lado}'] + 2 * df_confrontos[f'5J Média Gols Sofridos {lado}']) / 3).round(2)

# === CÁLCULO POISSON +0.5 GOL ===
df_confrontos['Poisson +0.5 Casa'] = (1 - np.exp(-(df_confrontos['Média Geral Feitos Casa'] * df_confrontos['Média Geral Sofridos Visitante'])))
df_confrontos['Poisson +0.5 Visitante'] = (1 - np.exp(-(df_confrontos['Média Geral Feitos Visitante'] * df_confrontos['Média Geral Sofridos Casa'])))

# === PROBABILIDADE BTTS E 0,5 MATCH ===
df_confrontos['Prob. +0,5 Match'] = (df_confrontos['Poisson +0.5 Casa'] + df_confrontos['Poisson +0.5 Visitante']) - (df_confrontos['Poisson +0.5 Casa'] * df_confrontos['Poisson +0.5 Visitante'])
df_confrontos['Prob. 0 a 0'] = 1 - df_confrontos['Prob. +0,5 Match']
df_confrontos['BTTS'] = df_confrontos['Poisson +0.5 Casa'] * df_confrontos['Poisson +0.5 Visitante']
df_confrontos['Prob. No BTTS'] = (1 - df_confrontos['BTTS'])

# === XG, OVERALL SCORE, DESEQUILÍBRIO ===
df_confrontos['Simplified xG Casa'] = (((df_confrontos['6m Média Gols Feitos Casa'] * df_confrontos['6m Média Gols Sofridos Visitante']) + (df_confrontos['5J Média Gols Feitos Casa'] * df_confrontos['5J Média Gols Sofridos Visitante'])) / 2).round(2)
df_confrontos['Simplified xG Visitante'] = (((df_confrontos['6m Média Gols Feitos Visitante'] * df_confrontos['6m Média Gols Sofridos Casa']) + (df_confrontos['5J Média Gols Feitos Visitante'] * df_confrontos['5J Média Gols Sofridos Casa'])) / 2).round(2)
df_confrontos['Overall Score'] = (df_confrontos['Simplified xG Casa'] + df_confrontos['Simplified xG Visitante']).round(2)
df_confrontos["Desequilíbrio Absoluto xG"] = abs(df_confrontos["Simplified xG Casa"] - df_confrontos["Simplified xG Visitante"])
df_confrontos["Desequilíbrio % xG"] = (df_confrontos["Desequilíbrio Absoluto xG"] / df_confrontos["Overall Score"]).replace([float('inf'), -float('inf')], 0).fillna(0).round(2)

# === DATA DOS ÚLTIMOS 5 JOGOS ===
df_historico_base = pd.concat([df_historico[["Time da casa", "Data"]].rename(columns={"Time da casa": "Time"}),df_historico[["Time visitante", "Data"]].rename(columns={"Time visitante": "Time"})]) # Unifica time mandante e visitante com datas
df_historico_base = df_historico_base.dropna().sort_values(by=["Time", "Data"], ascending=[True, False]) # Ordena por data descrescente
df_ultimos_jogos = df_historico_base.groupby("Time").head(5) # Agrupa e extrai as 5 datas mais recentes por time
df_datas_expandida = df_ultimos_jogos.groupby("Time")["Data"].apply(list).apply(lambda x: x + [None] * (5 - len(x))) # Agrupa e extrai as 5 datas mais recentes por time
df_datas_expandida = pd.DataFrame(df_datas_expandida.tolist(), index=df_datas_expandida.index, columns=["Last Game 1_date", "Last Game 2_date", "Last Game 3_date", "Last Game 4_date", "Last Game 5_date"]) # Converte para DataFrame com colunas separadas

for i in range(1, 6): # Mapear para cada time da casa
    df_confrontos[f"Last Game {i}_date | H"] = df_confrontos["Casa"].map(df_datas_expandida[f"Last Game {i}_date"])

for i in range(1, 6): # Mapear para cada time visitante
    df_confrontos[f"Last Game {i}_date | A"] = df_confrontos["Visitante"].map(df_datas_expandida[f"Last Game {i}_date"])

# === NOME DOS TIMES DOS ÚLTIMOS 5 JOGOS ===
df_mand_adv = df_historico[["Data", "Time da casa", "Time visitante"]].rename(columns={"Time da casa": "Time", "Time visitante": "Adversario"})
df_mand_adv["Adversario"] = df_mand_adv["Adversario"] + " (H)"
df_visit_adv = df_historico[["Data", "Time visitante", "Time da casa"]].rename(columns={"Time visitante": "Time", "Time da casa": "Adversario"})
df_visit_adv["Adversario"] = df_visit_adv["Adversario"] + " (A)"
df_historico_adv = pd.concat([df_mand_adv, df_visit_adv], ignore_index=True)
df_historico_adv = df_historico_adv.dropna().sort_values(by=["Time", "Data"], ascending=[True, False])
df_ultimos_adv = df_historico_adv.groupby("Time").head(5) # Agrupa e extrai as 5 partidas mais recentes
df_adv_expandido = df_ultimos_adv.groupby("Time")["Adversario"].apply(list).apply(lambda x: x + [None] * (5 - len(x)))
df_adv_expandido = pd.DataFrame(df_adv_expandido.tolist(), index=df_adv_expandido.index, columns=[
    "Last Game 1_adv", "Last Game 2_adv", "Last Game 3_adv", "Last Game 4_adv", "Last Game 5_adv"])
for i in range(1, 6): # Mapear para Casa (H) e Visitante (A)
    df_confrontos[f"Last Game {i}_adv | H"] = df_confrontos["Casa"].map(df_adv_expandido[f"Last Game {i}_adv"])
    df_confrontos[f"Last Game {i}_adv | A"] = df_confrontos["Visitante"].map(df_adv_expandido[f"Last Game {i}_adv"])

# === GOLS FEITOS E SOFRIDOS POR JOGO DOS ULTIMOS 5J ===
df_top5_sorted = df_top5.sort_values(by=["Time", "Data"], ascending=[True, False]) # Agrupa e extrai listas de gols feitos e sofridos por time
gols_for_series = df_top5_sorted.groupby("Time")["Gols Feitos"].apply(list).apply(lambda x: x + [None] * (5 - len(x))) # Gols feitos
df_golsfor = pd.DataFrame(gols_for_series.tolist(), index=gols_for_series.index, columns=[f"Last Game {i}_goalsfor" for i in range(1, 6)])
gols_against_series = df_top5_sorted.groupby("Time")["Gols Sofridos"].apply(list).apply(lambda x: x + [None] * (5 - len(x))) # Gols sofridos
df_golsagainst = pd.DataFrame(gols_against_series.tolist(), index=gols_against_series.index, columns=[
    f"Last Game {i}_goalsagainst" for i in range(1, 6)])

# Mapear no df_confrontos para Casa (H) e Visitante (A)
for i in range(1, 6):
    df_confrontos[f"Last Game {i}_goalsfor | H"] = df_confrontos["Casa"].map(df_golsfor[f"Last Game {i}_goalsfor"])
    df_confrontos[f"Last Game {i}_goalsfor | A"] = df_confrontos["Visitante"].map(df_golsfor[f"Last Game {i}_goalsfor"])
    df_confrontos[f"Last Game {i}_goalsagainst | H"] = df_confrontos["Casa"].map(df_golsagainst[f"Last Game {i}_goalsagainst"])
    df_confrontos[f"Last Game {i}_goalsagainst | A"] = df_confrontos["Visitante"].map(df_golsagainst[f"Last Game {i}_goalsagainst"])

# === % DE JOGOS COM GOLS FEITOS OU SOFRIDOS 5J ===
# Função para contar % jogos com pelo menos 1 gol
def pct_jogos_com_gols(lista, tipo="feitos"):
    if not isinstance(lista, list):
        return 0
    return round(sum(1 for x in lista if pd.notna(x) and x > 0) / len(lista) * 100, 1)

# Aplica a função ao df_top5
df_top5_sorted = df_top5.sort_values(by=["Time", "Data"], ascending=[True, False])

# Agrupa gols feitos e sofridos
df_gf_list = df_top5_sorted.groupby("Time")["Gols Feitos"].apply(list).apply(lambda x: x + [None] * (5 - len(x)))
df_gs_list = df_top5_sorted.groupby("Time")["Gols Sofridos"].apply(list).apply(lambda x: x + [None] * (5 - len(x)))

# Calcula os percentuais
pct_feitos = df_gf_list.apply(pct_jogos_com_gols)
pct_sofridos = df_gs_list.apply(lambda x: pct_jogos_com_gols(x, tipo="sofridos"))

# Mapeia no df_confrontos
df_confrontos["% feitos L5 casa"] = df_confrontos["Casa"].map(pct_feitos).fillna(0)
df_confrontos["% sofridos L5 casa"] = df_confrontos["Casa"].map(pct_sofridos).fillna(0)
df_confrontos["% feitos L5 visitante"] = df_confrontos["Visitante"].map(pct_feitos).fillna(0)
df_confrontos["% sofridos L5 visitante"] = df_confrontos["Visitante"].map(pct_sofridos).fillna(0)

# Criar coluna de resultado no df_top5
def resultado(feitos, sofridos):
    if pd.isna(feitos) or pd.isna(sofridos):
        return None
    if feitos > sofridos:
        return "W"
    elif feitos == sofridos:
        return "D"
    else:
        return "L"

df_top5["Resultado"] = df_top5.apply(lambda x: resultado(x["Gols Feitos"], x["Gols Sofridos"]), axis=1)

# Agrupar por time em lista
df_resultados = df_top5.sort_values(by=["Time", "Data"], ascending=[True, False])
df_resultado_listas = df_resultados.groupby("Time")["Resultado"].apply(list).apply(lambda x: x + [None] * (5 - len(x)))

# Expandir em colunas
df_resultado_exp = pd.DataFrame(df_resultado_listas.tolist(), index=df_resultado_listas.index, columns=[f"Last Game {i}_r" for i in range(1, 6)])

# Mapear no df_confrontos
for i in range(1, 6):
    df_confrontos[f"Last Game {i}_r | H"] = df_confrontos["Casa"].map(df_resultado_exp[f"Last Game {i}_r"])
    df_confrontos[f"Last Game {i}_r | V"] = df_confrontos["Visitante"].map(df_resultado_exp[f"Last Game {i}_r"])

# === APROVEITAMENTO POR MÊS PARA CADA TIME === ######################################################

# 1. Criar coluna 'Ano-Mês'
df_historico["Data"] = pd.to_datetime(df_historico["Data"], errors="coerce", dayfirst=True)
df_historico["Ano-Mês"] = df_historico["Data"].dt.to_period("M")

# 2. Gerar DataFrame unificado de jogos
mand = df_historico[["Ano-Mês", "Time da casa", "Placar casa", "Placar visitante"]].copy()
mand.columns = ["Ano-Mês", "Time", "GF", "GS"]
visit = df_historico[["Ano-Mês", "Time visitante", "Placar visitante", "Placar casa"]].copy()
visit.columns = ["Ano-Mês", "Time", "GF", "GS"]
df_jogos_mes = pd.concat([mand, visit], ignore_index=True)

# 3. Calcular aproveitamento por time e por mês
def calc_aproveitamento_grupo(grupo):
    jogos = len(grupo)
    v = (grupo["GF"] > grupo["GS"]).sum()
    e = (grupo["GF"] == grupo["GS"]).sum()
    pontos = v * 3 + e
    return round((pontos / (jogos * 3)) * 100, 1) if jogos > 0 else 0

df_jogos_mes["GF"] = pd.to_numeric(df_jogos_mes["GF"], errors="coerce")
df_jogos_mes["GS"] = pd.to_numeric(df_jogos_mes["GS"], errors="coerce")
df_jogos_mes.dropna(subset=["GF", "GS"], inplace=True)
aproveitamento_mensal = (
    df_jogos_mes.groupby(["Time", "Ano-Mês"])[["GF", "GS"]]
    .apply(calc_aproveitamento_grupo)
    .reset_index()
)
aproveitamento_mensal.columns = ["Time", "Ano-Mês", "Aproveitamento"]

# 4. Gerar lista dos últimos 6 meses (Mês 0 = atual)
meses_anteriores = [(datetime.now().replace(day=1) - pd.DateOffset(months=i)).to_period("M") for i in range(6)]

# 5. Criar um dicionário de DataFrames para acesso rápido
df_aprov_dict = {}
for i, mes in enumerate(meses_anteriores):
    df_mes = aproveitamento_mensal[aproveitamento_mensal["Ano-Mês"] == mes].set_index("Time")["Aproveitamento"]
    df_aprov_dict[i] = df_mes

# 6. Mapear no df_confrontos
for i in range(6):
    df_confrontos[f"Aproveitamento Mês -{i} Casa"] = df_confrontos["Casa"].map(df_aprov_dict[i]).fillna(0)
    df_confrontos[f"Aproveitamento Mês -{i} Visitante"] = df_confrontos["Visitante"].map(df_aprov_dict[i]).fillna(0)

# === SALVA O RESULTADO FINAL ===
df_confrontos = df_confrontos.round(2)
colunas_desejadas = [
    "Casa", "Visitante", "Campeonato",
    # Estatísticas 6 meses
    "6m Jogos Casa", "6m Vitórias Casa", "6m Empates Casa", "6m Derrotas Casa",
    "6m Gols Feitos Casa", "6m Gols Sofridos Casa",
    "6m Jogos Visitante", "6m Vitórias Visitante", "6m Empates Visitante", "6m Derrotas Visitante",
    "6m Gols Feitos Visitante", "6m Gols Sofridos Visitante",
    # Estatísticas 5 jogos
    "5J Jogos Casa", "5J Vitórias Casa", "5J Empates Casa", "5J Derrotas Casa",
    "5J Gols Feitos Casa", "5J Gols Sofridos Casa",
    "5J Jogos Visitante", "5J Vitórias Visitante", "5J Empates Visitante", "5J Derrotas Visitante",
    "5J Gols Feitos Visitante", "5J Gols Sofridos Visitante",
    # Datas dos últimos 5 jogos
    "Last Game 1_date | H", "Last Game 2_date | H", "Last Game 3_date | H", "Last Game 4_date | H", "Last Game 5_date | H",
    "Last Game 1_date | A", "Last Game 2_date | A", "Last Game 3_date | A", "Last Game 4_date | A", "Last Game 5_date | A",
    # Adversários
    "Last Game 1_adv | H", "Last Game 2_adv | H", "Last Game 3_adv | H", "Last Game 4_adv | H", "Last Game 5_adv | H",
    "Last Game 1_adv | A", "Last Game 2_adv | A", "Last Game 3_adv | A", "Last Game 4_adv | A", "Last Game 5_adv | A",
    # Gols feitos
    "Last Game 1_goalsfor | H", "Last Game 2_goalsfor | H", "Last Game 3_goalsfor | H", "Last Game 4_goalsfor | H", "Last Game 5_goalsfor | H",
    "Last Game 1_goalsfor | A", "Last Game 2_goalsfor | A", "Last Game 3_goalsfor | A", "Last Game 4_goalsfor | A", "Last Game 5_goalsfor | A",
    # Gols sofridos
    "Last Game 1_goalsagainst | H", "Last Game 2_goalsagainst | H", "Last Game 3_goalsagainst | H", "Last Game 4_goalsagainst | H", "Last Game 5_goalsagainst | H",
    "Last Game 1_goalsagainst | A", "Last Game 2_goalsagainst | A", "Last Game 3_goalsagainst | A", "Last Game 4_goalsagainst | A", "Last Game 5_goalsagainst | A",
    # Aproveitamento mensal por time
    "Aproveitamento Mês -0 Casa", "Aproveitamento Mês -0 Visitante",
    "Aproveitamento Mês -1 Casa", "Aproveitamento Mês -1 Visitante",
    "Aproveitamento Mês -2 Casa", "Aproveitamento Mês -2 Visitante",
    "Aproveitamento Mês -3 Casa", "Aproveitamento Mês -3 Visitante",
    "Aproveitamento Mês -4 Casa", "Aproveitamento Mês -4 Visitante",
    "Aproveitamento Mês -5 Casa", "Aproveitamento Mês -5 Visitante",
    "Simplified xG Casa", "Simplified xG Visitante", "Overall Score", 
    "Desequilíbrio Absoluto xG", "Desequilíbrio % xG",
    "Poisson +0.5 Casa","Poisson +0.5 Visitante",
    "Prob. +0,5 Match","Prob. 0 a 0",
    "BTTS", "Prob. No BTTS",
]

# Filtrar o DataFrame final
df_confrontos = df_confrontos[colunas_desejadas]

data_str_formatada = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
nome_arquivo_csv = f"confrontos_stats_6m_5j_{data_str_formatada}.csv"

df_confrontos.to_csv(nome_arquivo_csv, sep=";", index=False, encoding="utf-8-sig", decimal=",")

print("✅ Estatísticas combinadas salvas com sucesso!")

time.sleep(5) # _________________________________________________________________________________ MANDAR E-MAIL



# === DEFINIR A DATA ATUAL ===
data_atual = datetime.now().strftime("%Y-%m-%d")
data_amanha = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")

# === CONFIGURAÇÕES DE E-MAIL ===
EMAIL_REMETENTE = 'raulmpimentel@gmail.com'
EMAIL_DESTINATARIO = 'raulmpimentel@hotmail.com'
SENHA_APP = 'ousa uhmx vhzd xpoy'  # nunca a senha real da conta

# === SELECIONAR E ORDENAR OS DADOS PARA O CORPO DO E-MAIL ===
colunas_email = [
    "Casa", "Visitante", "Campeonato",
    "Simplified xG Casa", "Simplified xG Visitante",
    "Overall Score", "Desequilíbrio Absoluto xG", "Desequilíbrio % xG",
    "Poisson +0.5 Casa", "Poisson +0.5 Visitante",
    "Prob. +0,5 Match", "Prob. 0 a 0",
    "BTTS", "Prob. No BTTS"
]


df_email = df_confrontos[colunas_email].copy()
df_email = df_email.sort_values(by="Overall Score", ascending=False)

# === FORMATAR CADA LINHA COMO TEXTO ===
linhas_email = []
for _, row in df_email.iterrows():
    linha = (
        f"{row['Casa']} x {row['Visitante']} - {row['Campeonato']} | "
        f"xG: {row['Simplified xG Casa']:.2f} x {row['Simplified xG Visitante']:.2f} | "
        f"Total: {row['Overall Score']:.2f} | "
        f"Dif.: {row['Desequilíbrio Absoluto xG']:.2f} ({row['Desequilíbrio % xG']:.0%})"
    )
    linhas_email.append(linha)

texto_email = "\n".join(linhas_email)

# === MONTAR MENSAGEM ===
msg = EmailMessage()
msg['Subject'] = f'{data_amanha} | Estatísticas Avançadas de Jogos do Dia'
msg['From'] = EMAIL_REMETENTE
msg['To'] = EMAIL_DESTINATARIO
msg.set_content("Este e-mail contém uma versão em HTML. Use um cliente que suporte HTML.")

# === Montar linhas da tabela HTML separadamente ===
linhas_tabela = ""
for _, row in df_email.iterrows():
    linhas_tabela += f"""
      <tr>
        <td>{row['Casa']}</td>
        <td>{row['Visitante']}</td>
        <td>{row['Campeonato']}</td>
        <td>{row['Simplified xG Casa']:.2f}</td>
        <td>{row['Simplified xG Visitante']:.2f}</td>
        <td>{row['Overall Score']:.2f}</td>
        <td>{row['Poisson +0.5 Casa']:.0%}</td>
        <td>{row['Poisson +0.5 Visitante']:.0%}</td>
        <td>{row['Prob. +0,5 Match']:.0%}</td>
        <td>{row['Prob. 0 a 0']:.0%}</td>
        <td>{row['BTTS']:.0%}</td>
        <td>{row['Prob. No BTTS']:.0%}</td>
      </tr>"""

msg.add_alternative(f"""\
<html>
  <body>
    <p>Olá!</p>
    <p>Segue a análise dos confrontos de hoje ordenada por <strong>Overall Score</strong>:</p>
    <table border="1" cellpadding="6" cellspacing="0" style="border-collapse: collapse; font-family: sans-serif; font-size: 14px;">
      <tr>
        <th>Casa</th>
        <th>Visitante</th>
        <th>Campeonato</th>
        <th>xG Casa</th>
        <th>xG Visitante</th>
        <th>Overall</th>
        <th>Poisson +0,5 Home</th>
        <th>Poisson +0,5 Away</th>
        <th>+0,5 Goal Probability</th>
        <th>0-0 Probability</th>
        <th>BTTS Chance</th>
        <th>No BTTS Chance</th>
      </tr>
      {linhas_tabela}
    </table>
    <p>Abraço,<br>Seu robô de dados 🤖</p>
  </body>
</html>
""", subtype='html')

with open(nome_arquivo_csv, "rb") as f:
    msg.add_attachment(
        f.read(),
        maintype="application",
        subtype="octet-stream",
        filename=nome_arquivo_csv
    )

# === ENVIAR O E-MAIL ===
with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
    smtp.login(EMAIL_REMETENTE, SENHA_APP)
    smtp.send_message(msg)

print("✅ E-mail enviado com sucesso!")
