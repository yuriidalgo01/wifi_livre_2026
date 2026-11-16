import argparse
import json
import sys
from pathlib import Path
import pandas as pd


def solicitar_nome_arquivo(mensagem: str, padrao: str) -> str:
    """Exibe um prompt no terminal permitindo aceitar o padrão ou digitar um novo nome."""
    entrada = input(f"{mensagem} [{padrao}]: ").strip()
    return entrada if entrada else padrao


def converter_csv_para_geojson(arquivo_csv: Path, arquivo_geojson: Path):
    if not arquivo_csv.exists():
        print(f"\nErro: O arquivo de entrada '{arquivo_csv}' não existe.", file=sys.stderr)
        sys.exit(1)

    print(f"\nLendo dados de: {arquivo_csv}")
    df = pd.read_csv(arquivo_csv, sep=";", encoding="utf-8")

    # 1. Filtra registros com coordenadas válidas
    total_original = len(df)
    df_validos = df.dropna(subset=["latitude", "longitude"]).copy()
    print(f"Linhas válidas com coordenadas: {len(df_validos)}/{total_original}")

    # 2. Converte nulos para string vazia
    df_validos = df_validos.fillna("")

    # 3. Remove duplicados (usa 'localizacao_standard' se existir, ou 'Logradouro' e 'CEP')
    coluna_dedup = "localizacao_standard" if "localizacao_standard" in df_validos.columns else ["Logradouro", "CEP"]
    df_validos = df_validos.drop_duplicates(subset=coluna_dedup)

    # 4. Estrutura os pontos em GeoJSON
    features = []
    for _, row in df_validos.iterrows():
        try:
            lon = float(str(row["longitude"]).replace(",", "."))
            lat = float(str(row["latitude"]).replace(",", "."))
        except ValueError:
            continue

        feature = {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [lon, lat]
            },
            "properties": {
                "tipo_localidade": row.get("Tipo de Localidade", ""),
                "logradouro": row.get("Logradouro", ""),
                "bairro": row.get("Bairro", ""),
                "cep": str(row.get("CEP", "")),
                "regiao": row.get("Região", ""),
                "pontos_acesso": row.get("Pontos de Acesso ", row.get("Pontos de Acesso", "")),
                "cidade": row.get("Cidade", "São Paulo"),
                "estado": row.get("Estado", "SP"),
                "pais": row.get("Pais", "Brasil"),
                "localizacao_standard": row.get("localizacao_standard", "")
            }
        }
        features.append(feature)

    geojson_data = {
        "type": "FeatureCollection",
        "features": features
    }

    # 5. Salva o arquivo de saída
    arquivo_geojson.parent.mkdir(parents=True, exist_ok=True)
    with open(arquivo_geojson, "w", encoding="utf-8") as f:
        json.dump(geojson_data, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 50)
    print("Processamento concluído com sucesso!")
    print(f"Features geradas no GeoJSON: {len(features)}")
    print(f"Arquivo salvo em: {arquivo_geojson.resolve()}")
    print("=" * 50)


def main():
    diretorio_base = Path(r"C:\Users\x432601\Documents\GitHub\ETL_wifi_livre_2026\data_manual")
    padrao_entrada = "pontos_programa_wifi-livre-sp_geolocalizado.csv"
    padrao_saida = "pontos_wifi.geojson"

    parser = argparse.ArgumentParser(description="Conversor de CSV geolocalizado para GeoJSON FeatureCollection.")
    parser.add_argument("-i", "--input", type=str, help="Nome ou caminho do arquivo CSV de entrada.")
    parser.add_argument("-o", "--output", type=str, help="Nome ou caminho do arquivo GeoJSON de saída.")
    parser.add_argument("--sem-prompt", action="store_true", help="Usa valores padrão sem exibir perguntas no terminal.")

    args = parser.parse_args()

    # Se os argumentos não forem fornecidos via CLI e a flag --sem-prompt não estiver ativa, pergunta ao usuário
    if not args.sem_prompt:
        nome_in = args.input or solicitar_nome_arquivo("Informe o nome/caminho do arquivo CSV de entrada", padrao_entrada)
        nome_out = args.output or solicitar_nome_arquivo("Informe o nome/caminho do arquivo GeoJSON de saída", padrao_saida)
    else:
        nome_in = args.input or padrao_entrada
        nome_out = args.output or padrao_saida

    # Garante a extensão .geojson no nome de saída
    if not nome_out.lower().endswith(".geojson"):
        nome_out += ".geojson"

    # Resolve caminhos relativos ao diretório padrão caso não seja fornecido caminho absoluto
    caminho_in = Path(nome_in) if Path(nome_in).is_absolute() else diretorio_base / nome_in
    caminho_out = Path(nome_out) if Path(nome_out).is_absolute() else diretorio_base / nome_out

    converter_csv_para_geojson(caminho_in, caminho_out)


if __name__ == "__main__":
    main()