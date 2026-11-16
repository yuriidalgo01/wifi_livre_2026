import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
import unicodedata
from rapidfuzz import process, fuzz

def normalizar_texto(texto):
    """Remove acentos, pontuação e converte para maiúsculo."""
    if not isinstance(texto, str):
        return ""
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join([c for c in texto if not unicodedata.combining(c)])
    return texto.strip().upper()

# 1. Carregar a base de vias do GeoSampa (baixe previamente o .shp ou .gpkg)
# Exemplo: camada de eixos de logradouros
print("Carregando base viária do GeoSampa...")
gdf_geosampa = gpd.read_file("geosampa_logradouros.gpkg")

# Garante projeção WGS84 (EPSG:4326) para coordenadas em Lat/Long
if gdf_geosampa.crs != "EPSG:4326":
    gdf_geosampa = gdf_geosampa.to_crs(epsg=4326)

# Normaliza os nomes de logradouros do GeoSampa
# (ajuste a coluna 'nm_logradouro' conforme o nome exato no seu arquivo)
gdf_geosampa["nome_norm"] = gdf_geosampa["nm_logradouro"].apply(normalizar_texto)

# Cria um dicionário com o centroide de cada via para consultas ultra-rápidas
# Agrupando pelo nome da via para unificar múltiplos segmentos da mesma rua
print("Processando geometrias de referência...")
vias_unicas = gdf_geosampa.dissolve(by="nome_norm")
vias_centroides = vias_unicas.geometry.centroid

# 2. Carregar sua tabela de entrada (CSV ou Excel)
df_enderecos = pd.DataFrame({
    "id": [1, 2, 3],
    "logradouro": ["Av. Paulista", "Rua Augusta", "Praca da Se"],
    "bairro_esperado": ["Bela Vista", "Consolação", "Sé"]
})

df_enderecos["nome_norm"] = df_enderecos["logradouro"].apply(normalizar_texto)

# 3. Geocodificação em lote
nomes_base_geosampa = vias_centroides.index.tolist()

geometrias = []
status = []

print("Executando correspondência e cálculo de coordenadas...")
for _, row in df_enderecos.iterrows():
    nome_busca = row["nome_norm"]
    
    # Busca exata primeiro
    if nome_busca in vias_centroides:
        geometrias.append(vias_centroides[nome_busca])
        status.append("Exato")
    else:
        # Busca aproximada (Fuzzy Matching) para lidar com variações de digitação
        match, score, _ = process.extractOne(
            nome_busca, 
            nomes_base_geosampa, 
            scorer=fuzz.token_sort_ratio
        )
        if score >= 85:  # Limiar de confiança configurável
            geometrias.append(vias_centroides[match])
            status.append(f"Fuzzy ({score}%)")
        else:
            geometrias.append(None)
            status.append("Não Encontrado")

# 4. Montar o GeoDataFrame final
df_enderecos["status_geocod"] = status
gdf_resultado = gpd.GeoDataFrame(df_enderecos, geometry=geometrias, crs="EPSG:4326")

# Separa latitude e longitude em colunas tabulares caso necessário
gdf_resultado["longitude"] = gdf_resultado.geometry.x
gdf_resultado["latitude"] = gdf_resultado.geometry.y

# Remove registros não encontrados para gerar um GeoJSON válido
gdf_valido = gdf_resultado.dropna(subset=["geometry"])

# 5. Exportar como GeoJSON
gdf_valido.to_file("enderecos_geocodificados.geojson", driver="GeoJSON")

print(f"Processamento concluído. {len(gdf_valido)} de {len(df_enderecos)} registros geocodificados.")