import pandas as pd
from pathlib import Path
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter

# 1. Definição dos caminhos
file_path = Path(r"C:\Users\x432601\Documents\GitHub\ETL_wifi_livre_2026\data_manual")
input_file = file_path / "pontos_programa_wifi-livre-sp.txt"
output_file = file_path / "pontos_programa_wifi-livre-sp_geolocalizado.csv"

# 2. Leitura dos dados
df = pd.read_csv(input_file, sep=";", encoding="utf-8")

# Padronização de campos fixos
df['Cidade'] = 'São Paulo'
df['Estado'] = 'SP'
df['Pais'] = 'Brasil'

# 3. Remoção de duplicatas com base nos dados de endereço
df = df.drop_duplicates(subset=['Logradouro', 'CEP'])

# 4. Configuração do Nominatim com RateLimiter
geolocator = Nominatim(user_agent="wifi_livre_2026")
geocode_com_delay = RateLimiter(
    geolocator.geocode,
    min_delay_seconds=1.0,
    max_retries=2,
    error_wait_seconds=5.0
)

# 5. Função para montar a query estruturada e executar a busca
def buscar_coordenadas(row):
    query = {
        'street': str(row['Logradouro']),
        'postalcode': str(row['CEP']),
        'city': str(row['Cidade']),
        'state': str(row['Estado']),
        'country': str(row['Pais'])
    }
    
    # Remove chaves vazias ou 'nan' para não quebrar a busca
    query = {k: v for k, v in query.items() if v and v.lower() != 'nan'}
    
    try:
        return geocode_com_delay(query)
    except Exception:
        return None

# 6. Execução da geocodificação
df["geolocalizacao"] = df.apply(buscar_coordenadas, axis=1)

# 7. Extração de latitude e longitude
df["latitude"] = df["geolocalizacao"].apply(lambda loc: loc.latitude if loc else None)
df["longitude"] = df["geolocalizacao"].apply(lambda loc: loc.longitude if loc else None)

# 8. Salvamento do resultado
df.to_csv(output_file, sep=";", index=False, encoding="utf-8")