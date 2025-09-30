# -*- coding: utf-8 -*-
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
import pandas as pd, time, re, os, smtplib
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from email.message import EmailMessage

# Secrets (defina no GitHub Actions → Settings → Secrets)
EMAIL_REMETENTE   = os.environ["EMAIL_REMETENTE"]
EMAIL_DESTINATARIO= os.environ["EMAIL_DESTINATARIO"]
EMAIL_SENHA_APP   = os.environ["EMAIL_SENHA_APP"]

# Data de ontem
data_atual = (datetime.now() - timedelta(days=1))
data_str_formatada = data_atual.strftime("%d-%m-%Y")
data_url_formatada = data_atual.strftime("%Y%m%d")

# Chrome headless (para CI)
chrome_options = Options()
chrome_options.add_experimental_option("prefs", {"profile.managed_default_content_settings.images": 2})
chrome_options.add_argument('--ignore-certificate-errors')
chrome_options.add_argument('--ignore-ssl-errors')
chrome_options.add_argument('--headless')
chrome_options.add_argument('--no-sandbox')
chrome_options.add_argument('--disable-dev-shm-usage')
chrome_options.add_argument('--disable-gpu')

driver = webdriver.Chrome(options=chrome_options)
time.sleep(1)
driver.set_window_size(1280, 800)

# Scraping
url = f'https://www.futbol24.com/Live/?__igp=1&LiveDate={data_url_formatada}'
driver.get(url)
time.sleep(3)

element = driver.find_element(By.CSS_SELECTOR, '#f24com_tableresults > tbody')
soup = BeautifulSoup(element.get_attribute('innerHTML'), 'html.parser')
rows_with_match = soup.find_all('tr', class_=lambda x: x and 'match' in x)

def limpar_nome(nome):
    if nome:
        nome = re.sub(r'\(\d+\)', '', nome)
        nome = re.sub(r'1st leg: [\d-]+', '', nome)
        nome = re.sub(r'Agg\.: [\d-]+', '', nome)
        return nome.strip()
    return None

data = []
for row in rows_with_match:
    league = row.find(class_="league alt")
    home = row.find(class_="home")
    guest = row.find(class_="guest")
    result1 = row.find(class_="result1")
    league_text = league.get_text(strip=True) if league else None
    home_text = limpar_nome(home.get_text(strip=True)) if home else None
    guest_text = limpar_nome(guest.get_text(strip=True)) if guest else None
    result_text = result1.get_text(strip=True) if result1 else None
    data.append([home_text, result_text, guest_text, league_text])

competitions = ["COL D1","BRA CNF","COL D1F","BRA D1","BRA D2","BRA Cup","ARG D1","ARG Cup","PER D1",
"PAR D1","URU D1","BOL D1","MEX D1PO","UEFA CL","ITA D1","ITA D2","ITA Cup","SPA D1","ENG PR","ENG LCh",
"FRA D1","ENG Cup","GER D1","HOL D1","POR D1","CON CLA","CON CSA","ECU D1","CHI D1","CHI Cup","UEFA EL",
"UEFA ECL","TUR D1","GRE D1","IRL D1","JPN D1","RUS D1","SCO PR","BEL D1","GER Cup","SPA Cup","SPA D2",
"POR Cup","URU Cup","KSA D1","FIFA IC","COL Cup","MAR D1","ITA SC","POR LC","ENG LC","GER D2","FIFA CWC"]

fdata = [row for row in data if row[3] in competitions]

df = pd.DataFrame(fdata, columns=["Casa", "Placar", "Visitante", "Campeonato"])
df["Casa"] = df["Casa"].str.replace("*", "", regex=False)
df["Visitante"] = df["Visitante"].str.replace("*", "", regex=False)

if not df.empty and df["Placar"].notna().any():
    df[["Placar Casa", "Placar Visitante"]] = df["Placar"].str.split("-", expand=True)
else:
    df["Placar Casa"] = ""
    df["Placar Visitante"] = ""

df = df.drop(columns=["Placar"])
df = df[["Casa", "Placar Casa", "Placar Visitante", "Visitante", "Campeonato"]]

# CSV
nomedoarquivo = f"RESULTADOS_{data_url_formatada}.csv"
df.to_csv(nomedoarquivo, sep=";", encoding='utf-8-sig', index=False, header=True)

driver.quit()

# HTML do e-mail
linhas_tabela = "".join(
    f"<tr><td>{row['Casa']}</td><td>{row['Placar Casa']}</td><td>{row['Placar Visitante']}</td>"
    f"<td>{row['Visitante']}</td><td>{row['Campeonato']}</td></tr>"
    for _, row in df.iterrows()
)

msg = EmailMessage()
msg['Subject'] = f'{data_url_formatada} | Resultados dos Jogos (BetPoint)'
msg['From'] = EMAIL_REMETENTE
msg['To'] = EMAIL_DESTINATARIO
msg.set_content("Versão em texto: ver anexo CSV ou a tabela em HTML.")

msg.add_alternative(f"""\
<html><body>
<p>Resultados de {data_str_formatada}:</p>
<table border="1" cellpadding="6" cellspacing="0" style="border-collapse: collapse; font-family: sans-serif; font-size: 14px;">
<tr><th>Casa</th><th>Placar Casa</th><th>Placar Visitante</th><th>Visitante</th><th>Campeonato</th></tr>
{linhas_tabela}
</table>
</body></html>
""", subtype='html')

with open(nomedoarquivo, "rb") as f:
    msg.add_attachment(f.read(), maintype="application", subtype="octet-stream", filename=nomedoarquivo)

with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
    smtp.login(EMAIL_REMETENTE, EMAIL_SENHA_APP)
    smtp.send_message(msg)
