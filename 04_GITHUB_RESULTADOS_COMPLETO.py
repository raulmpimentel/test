from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
import pandas as pd
import time
import re
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import smtplib
from email.message import EmailMessage
import os
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

data_atual = (datetime.now() - timedelta(days=1))
data_str_formatada = data_atual.strftime("%d-%m-%Y")
data_url_formatada = data_atual.strftime("%Y%m%d")

# Configurar as opções do Chrome
chrome_options = Options()
chrome_options.add_experimental_option(
    "prefs", {"profile.managed_default_content_settings.images": 2}
)
chrome_options.add_argument("--ignore-certificate-errors")
chrome_options.add_argument("--ignore-ssl-errors")

# ajustes específicos para rodar no GitHub Actions
chrome_options.add_argument("--headless=new")  # roda sem interface gráfica
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument("--disable-software-rasterizer")
chrome_options.add_argument("--user-data-dir=/tmp/chrome-user-data")  # diretório temporário
chrome_options.add_argument("--window-size=1920,1080")

# Instanciando o navegador (usando Service do webdriver-manager)
service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=chrome_options)
time.sleep(2)

# Acessar o site
url = f"https://www.futbol24.com/Live/?__igp=1&LiveDate={data_url_formatada}"
driver.get(url)
time.sleep(3)  # Ajuste conforme necessário para carregar o conteúdo

# Encontrar o elemento <tbody>
element = driver.find_element(By.CSS_SELECTOR, "#f24com_tableresults > tbody")

# Usar BeautifulSoup para analisar o conteúdo HTML
soup = BeautifulSoup(element.get_attribute("innerHTML"), "html.parser")

# Encontrar todos os elementos <tr> com "match" na classe
rows_with_match = soup.find_all("tr", class_=lambda x: x and "match" in x)

# Função para limpar os nomes dos times
def limpar_nome(nome):
    if nome:
        nome = re.sub(r"\(\d+\)", "", nome)  # remove (1), (2), etc.
        nome = re.sub(r"1st leg: [\d-]+", "", nome)  # remove "1st leg: 0-0"
        nome = re.sub(r"Agg\.: [\d-]+", "", nome)  # remove "Agg.: 2-3"
        return nome.strip()
    return None

data = []
for row in rows_with_match:
    league = row.find(class_="league alt")  # Localiza a classe "league alt"
    home = row.find(class_="home")  # Localiza a classe "home"
    guest = row.find(class_="guest")  # Localiza a classe "guest"
    result1 = row.find(class_="result1")  # Localiza a classe "result"
    # Captura os textos dos elementos encontrados
    league_text = league.get_text(strip=True) if league else None
    home_text = limpar_nome(home.get_text(strip=True)) if home else None
    guest_text = limpar_nome(guest.get_text(strip=True)) if guest else None
    result_text = result1.get_text(strip=True) if result1 else None
    # Adiciona os dados à lista
    data.append([home_text, result_text, guest_text, league_text])

# Exibir os dados extraídos no log
for row in data:
    print(row)

competitions = [
    "COL D1",
    "BRA CNF",
    "COL D1F",
    "BRA D1",
    "BRA D2",
    "BRA Cup",
    "ARG D1",
    "ARG Cup",
    "PER D1",
    "PAR D1",
    "URU D1",
    "BOL D1",
    "MEX D1PO",
    "UEFA CL",
    "ITA D1",
    "ITA D2",
    "ITA Cup",
    "SPA D1",
    "ENG PR",
    "ENG LCh",
    "FRA D1",
    "ENG Cup",
    "GER D1",
    "HOL D1",
    "POR D1",
    "CON CLA",
    "CON CSA",
    "ECU D1",
    "CHI D1",
    "CHI Cup",
    "UEFA EL",
    "UEFA ECL",
    "TUR D1",
    "GRE D1",
    "IRL D1",
    "JPN D1",
    "RUS D1",
    "SCO PR",
    "BEL D1",
    "GER Cup",
    "SPA Cup",
    "SPA D2",
    "POR Cup",
    "URU Cup",
    "KSA D1",
    "FIFA IC",
    "COL Cup",
    "MAR D1",
    "ITA SC",
    "POR LC",
    "ENG LC",
    "GER D2",
    "FIFA CWC",
]

fdata = [row for row in data if row[3] in competitions]

# Criar um DataFrame a partir dos dados
df = pd.DataFrame(fdata, columns=["Casa", "Placar", "Visitante", "Campeonato"])
df["Casa"] = df["Casa"].str.replace("*", "", regex=False)
df["Visitante"] = df["Visitante"].str.replace("*", "", regex=False)
df[["Placar Casa", "Placar Visitante"]] = df["Placar"].str.split("-", expand=True)
df = df.drop(columns=["Placar"])
df = df[["Casa", "Placar Casa", "Placar Visitante", "Visitante", "Campeonato"]]

# Salvar em um arquivo CSV
nomedoarquivo = f"RESULTADOS_{data_url_formatada}.csv"
df.to_csv(nomedoarquivo, sep=";", encoding="utf-8-sig", index=False, header=True)

# Credenciais do e-mail vindas das variáveis de ambiente do GitHub
EMAIL_REMETENTE = os.getenv("EMAIL_REMETENTE")
EMAIL_DESTINATARIO = os.getenv("EMAIL_DESTINATARIO")
SENHA_APP = os.getenv("SENHA_APP")  # corrige aqui para usar a secret correta

# === PREPARAR TABELA HTML COM O QUE FOI COLETADO ===
linhas_tabela = ""
for _, row in df.iterrows():
    linhas_tabela += f"""
      <tr>
        <td>{row['Casa']}</td>
        <td>{row['Placar Casa']}</td>
        <td>{row['Placar Visitante']}</td>
        <td>{row['Visitante']}</td>
        <td>{row['Campeonato']}</td>
      </tr>"""

msg = EmailMessage()
msg["Subject"] = f"Resultados {data_str_formatada}"
msg["From"] = EMAIL_REMETENTE
msg["To"] = EMAIL_DESTINATARIO
msg.set_content(
    "Este e-mail contém uma versão em HTML. Abra em um cliente que suporte HTML."
)

msg.add_alternative(
    f"""\
<html>
  <body>
    <p>Olá!</p>
    <p>Segue a lista de resultados coletados no Futbol24 ({data_str_formatada}):</p>
    <table border="1" cellpadding="6" cellspacing="0" style="border-collapse: collapse; font-family: sans-serif; font-size: 14px;">
      <tr>
        <th>Casa</th>
        <th>Placar Casa</th>
        <th>Placar Visitante</th>
        <th>Visitante</th>
        <th>Campeonato</th>
      </tr>
      {linhas_tabela}
    </table>
    <p>Abraço,<br>Seu robô de dados 🤖</p>
  </body>
</html>
""",
    subtype="html",
)

# === ANEXAR O CSV ===
with open(nomedoarquivo, "rb") as f:
    msg.add_attachment(
        f.read(),
        maintype="application",
        subtype="octet-stream",
        filename=nomedoarquivo,
    )

# === ENVIAR O E-MAIL ===
with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
    smtp.login(EMAIL_REMETENTE, SENHA_APP)
    smtp.send_message(msg)

print("✅ E-mail enviado com sucesso!")

