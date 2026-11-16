import argparse
import sys
from pathlib import Path
import pandas as pd
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter
from tqdm import tqdm


def processar_geocodificacao(input_path: Path, output_path: Path, user_agent: str, delay: float):
    if not input_path.exists():
        print(f"Erro: O arquivo de entrada '{input_path}' não foi encontrado.", file=sys.stderr)
        sys.exit(1)

    print(f"Lendo dados de: {input_path}")
    df = pd.read_csv(input_path, sep=";", encoding="utf-8")

    # Padronização de campos fixos
    df["Cidade"] = "São Paulo"
    df["Estado"] = "SP"
    df["Pais"] = "Brasil"

    # Remoção de duplicatas
    tamanho_original = len(df)
    df = df.drop_duplicates(subset=["Logradouro", "CEP"]).copy()
    print(f"Removidas {tamanho_original - len(df)} linhas duplicadas. Total a processar: {len(df)}")

    # Configuração do Nominatim com RateLimiter
    geolocator = Nominatim(user_agent=user_agent)
    geocode_com_delay = RateLimiter(
        geolocator.geocode,
        min_delay_seconds=delay,
        max_retries=2,
        error_wait_seconds=5.0
    )

    def buscar_coordenadas(row):
        query = {
            "street": str(row["Logradouro"]),
            "postalcode": str(row["CEP"]),
            "city": str(row["Cidade"]),
            "state": str(row["Estado"]),
            "country": str(row["Pais"])
        }
        # Remove chaves vazias ou 'nan'
        query = {k: v for k, v in query.items() if v and v.strip().lower() != "nan"}
        
        try:
            return geocode_com_delay(query)
        except Exception:
            return None

    # Habilita barra de progresso no pandas
    tqdm.pandas(desc="Geocodificando")
    print("Iniciando requisições...")
    df["geolocalizacao"] = df.progress_apply(buscar_coordenadas, axis=1)

    # Extrai coordenadas numéricas
    df["latitude"] = df["geolocalizacao"].apply(lambda loc: loc.latitude if loc else None)
    df["longitude"] = df["geolocalizacao"].apply(lambda loc: loc.longitude if loc else None)

    # Garante que a pasta de destino existe e salva
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, sep=";", index=False, encoding="utf-8")
    
    encontrados = df["latitude"].notna().sum()
    print(f"\nConcluído com sucesso!")
    print(f"Coordenadas encontradas: {encontrados}/{len(df)} ({(encontrados / len(df) * 100):.1f}%)")
    print(f"Arquivo salvo em: {output_path}")


def main():
    default_dir = Path(r"C:\Users\x432601\Documents\GitHub\ETL_wifi_livre_2026\data_manual")
    default_input = default_dir / "pontos_programa_wifi-livre-sp.txt"
    default_output = default_dir / "pontos_programa_wifi-livre-sp_geolocalizado.csv"

    parser = argparse.ArgumentParser(
        description="Script CLI para geocodificação estruturada de pontos Wi-Fi via Nominatim."
    )
    parser.add_argument(
        "-i", "--input",
        type=Path,
        default=default_input,
        help=f"Caminho do arquivo de entrada TXT/CSV (Padrão: {default_input})"
    )
    parser.add_argument(
        "-o", "--output",
        type=Path,
        default=default_output,
        help=f"Caminho do arquivo CSV de saída (Padrão: {default_output})"
    )
    parser.add_argument(
        "-u", "--user-agent",
        type=str,
        default="wifi_livre_2026",
        help="Identificador do User-Agent exigido pela política de uso do Nominatim."
    )
    parser.add_argument(
        "-d", "--delay",
        type=float,
        default=1.0,
        help="Intervalo mínimo em segundos entre chamadas (Padrão: 1.0)."
    )

    args = parser.parse_args()
    processar_geocodificacao(args.input, args.output, args.user_agent, args.delay)


if __name__ == "__main__":
    main()