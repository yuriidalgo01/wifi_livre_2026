import argparse
import sys
import re
from pathlib import Path
import pandas as pd
import requests
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter
from tqdm import tqdm


def extrair_numero(logradouro: str) -> str:
    """Tenta extrair o número do imóvel do final da string do logradouro."""
    match = re.search(r",\s*(\d+)", str(logradouro))
    return match.group(1) if match else ""


def geocodificar_por_cep(cep: str, numero: str, session: requests.Session, geocode_nominatim) -> tuple:
    """
    1. Tenta buscar coordenadas diretas via BrasilAPI v2.
    2. Se não houver coordenadas, usa os dados limpos da BrasilAPI no Nominatim.
    Retorna: (latitude, longitude, origem)
    """
    cep_limpo = "".join(filter(str.isdigit, str(cep)))
    if len(cep_limpo) != 8:
        return None, None, "CEP_Invalido"

    url = f"https://brasilapi.com.br/api/cep/v2/{cep_limpo}"
    
    try:
        resp = session.get(url, timeout=5)
        if resp.status_code == 200:
            dados = resp.json()
            location = dados.get("location", {})
            coords = location.get("coordinates", {})

            # 1. BrasilAPI v2: Coordenadas diretas
            if isinstance(coords, dict) and coords.get("latitude") and coords.get("longitude"):
                return coords.get("latitude"), coords.get("longitude"), "BrasilAPI_Direto"
            elif isinstance(coords, list) and len(coords) == 2:
                # GeoJSON padrão: [longitude, latitude]
                return coords[1], coords[0], "BrasilAPI_Direto"

            # 2. Fallback Nominatim: Monta endereço padronizado com os dados retornados
            rua = dados.get("street", "")
            bairro = dados.get("neighborhood", "")
            cidade = dados.get("city", "São Paulo")
            uf = dados.get("state", "SP")

            endereco_partes = [rua, numero, bairro, cidade, uf, "Brasil"]
            endereco_completo = ", ".join([p for p in endereco_partes if p and str(p).strip()])
            
            loc = geocode_nominatim(endereco_completo)
            if loc:
                return loc.latitude, loc.longitude, "Nominatim_Fallback"
            
            return None, None, "Nominatim_Nao_Encontrado"
        
        return None, None, f"Erro_HTTP_{resp.status_code}"

    except Exception as e:
        return None, None, f"Excecao_{type(e).__name__}"


def executar_teste_comparacao(input_path: Path, output_path: Path, user_agent: str, delay: float, amostra: int | None):
    if not input_path.exists():
        print(f"Erro: Arquivo '{input_path}' não encontrado.", file=sys.stderr)
        sys.exit(1)

    print(f"Lendo dados de: {input_path}")
    df = pd.read_csv(input_path, sep=";", encoding="utf-8")

    # Limpeza básica e remoção de duplicatas
    df = df.drop_duplicates(subset=["Logradouro", "CEP"]).copy()

    # Aplica recorte de amostra para teste rápido
    if amostra and amostra > 0 and amostra < len(df):
        print(f"Executando modo teste: processando apenas as primeiras {amostra} linhas.")
        df = df.head(amostra).copy()
    else:
        print(f"Processando todas as {len(df)} linhas.")

    # Geocoder e Session HTTP
    geolocator = Nominatim(user_agent=user_agent)
    geocode_nominatim = RateLimiter(
        geolocator.geocode,
        min_delay_seconds=delay,
        max_retries=2,
        error_wait_seconds=4.0
    )
    session = requests.Session()

    resultados = []
    print("\nIniciando geocodificação via BrasilAPI + Fallback...")
    for _, row in tqdm(df.iterrows(), total=len(df), desc="Progresso"):
        logradouro = row.get("Logradouro", "")
        cep = row.get("CEP", "")
        num = extrair_numero(logradouro)

        lat, lon, origem = geocodificar_por_cep(cep, num, session, geocode_nominatim)
        resultados.append({
            "latitude_teste": lat,
            "longitude_teste": lon,
            "origem_geocodificacao": origem
        })

    # Integra resultados ao DataFrame
    df_res = pd.DataFrame(resultados)
    df["latitude_teste"] = df_res["latitude_teste"].values
    df["longitude_teste"] = df_res["longitude_teste"].values
    df["origem_geocodificacao"] = df_res["origem_geocodificacao"].values

    # Salva arquivo separado para teste/comparação
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, sep=";", index=False, encoding="utf-8")

    # Resumo
    encontrados = df["latitude_teste"].notna().sum()
    print("\n" + "=" * 50)
    print("Resumo da Execução:")
    print(f"Total processado: {len(df)}")
    print(f"Coordenadas obtidas: {encontrados} ({(encontrados / len(df) * 100):.1f}%)")
    print("\nDistribuição por origem:")
    print(df["origem_geocodificacao"].value_counts().to_string())
    print("=" * 50)
    print(f"Arquivo de teste salvo em: {output_path}")


def main():
    default_dir = Path(r"C:\Users\x432601\Documents\GitHub\ETL_wifi_livre_2026\data_manual")
    default_input = default_dir / "pontos_programa_wifi-livre-sp.txt"
    # Arquivo de saída com nome diferenciado para comparação
    default_output = default_dir / "pontos_programa_wifi-livre-sp_teste_brasilapi.csv"

    parser = argparse.ArgumentParser(
        description="Script de teste comparativo: Geocodificação híbrida BrasilAPI v2 + Nominatim."
    )
    parser.add_argument("-i", "--input", type=Path, default=default_input, help="Caminho do arquivo de entrada.")
    parser.add_argument("-o", "--output", type=Path, default=default_output, help="Caminho do CSV de saída de teste.")
    parser.add_argument("-u", "--user-agent", type=str, default="meu_wifi_pwa_test", help="User-Agent para o Nominatim.")
    parser.add_argument("-d", "--delay", type=float, default=1.0, help="Delay mínimo entre requisições ao Nominatim.")
    parser.add_argument("-n", "--amostra", type=int, default=0, help="Quantidade de linhas para testar (padrão: 15). Use 0 para rodar todas.")

    args = parser.parse_args()
    executar_teste_comparacao(
        input_path=args.input,
        output_path=args.output,
        user_agent=args.user_agent,
        delay=args.delay,
        amostra=args.amostra if args.amostra > 0 else None
    )


if __name__ == "__main__":
    main()