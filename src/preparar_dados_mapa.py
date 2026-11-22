from pathlib import Path

import geopandas as gpd
import pandas as pd
import numpy as np

# Localiza a raiz independentemente da pasta de execução do comando.
RAIZ = Path(__file__).resolve().parents[1]

prefeituras = gpd.read_file(
    RAIZ / "dados/brutos/bairros/prefeitura_bairro.gpkg",
    layer="prefeituras_bairro_a",
)

bairros = gpd.read_file(
    RAIZ / "dados/brutos/bairros/lei_9778_2024_bairros_a.gpkg",
    layer="delimitacao_de_bairros_oficial",
)

unidades = gpd.read_file(
    RAIZ / "dados/processados/ubs_usf_salvador.gpkg",
    layer="ubs_usf",
)

indicadores = pd.read_csv(
    RAIZ / "resultados/tabelas/indicadores_por_prefeitura_bairro_revisado.csv",
    sep=";",
    decimal=",",
    encoding="utf-8-sig",
    dtype={"COD_PBR": "string"},
)


def validar_camada(dados, nome, quantidade, identificador, colunas):
    faltantes = set(colunas) - set(dados.columns)
    if faltantes:
        raise ValueError(f"{nome}: colunas ausentes: {sorted(faltantes)}")

    if len(dados) != quantidade:
        raise ValueError(f"{nome}: esperados {quantidade} registros, encontrados {len(dados)}.")

    if dados.crs is None or dados.crs.to_epsg() != 31984:
        raise ValueError(f"{nome}: CRS inesperado: {dados.crs}")

    if dados[identificador].isna().any() or dados[identificador].duplicated().any():
        raise ValueError(f"{nome}: identificadores ausentes ou duplicados.")

    geometria = dados.geometry
    if geometria.isna().any() or geometria.is_empty.any() or (~geometria.is_valid).any():
        raise ValueError(f"{nome}: há geometrias ausentes, vazias ou inválidas.")

    print(f"{nome}: {len(dados)} registros validados.")


validar_camada(
    prefeituras, "Prefeituras-Bairro", 10, "COD_PBR",
    ["COD_PBR", "PREF_BAIRR", "QTD_BAIRRO", "geometry"],
)
validar_camada(
    bairros, "Bairros", 171, "ID",
    ["ID", "NOME_BAIRRO", "geometry"],
)
validar_camada(
    unidades, "Unidades", 142, "tipo",
    ["tipo", "unidade", "tipo_tratado", "geometry"],
)

tipos = unidades["tipo_tratado"].value_counts().to_dict()
if tipos != {"USF": 97, "UBS": 45}:
    raise ValueError(f"Contagem inesperada de unidades: {tipos}")

print("Unidades: 45 UBS e 97 USF.")
print("Tabela de indicadores:", len(indicadores), "registros carregados.")



colunas_numericas = [
    "qtd_bairros", "pop_estimada", "UBS", "USF", "total_ubs_usf",
    "ubs_usf_por_10_mil", "mediana_ponderada_m", "p90_ponderado_m",
    "pct_ate_500m", "pct_500m_a_1km", "pct_1km_a_1333m",
    "pct_acima_1333m", "pct_sem_rota", "pct_ate_20",
    "pop_sem_rota", "rendimento_setorial_ponderado_rs",
]

faltantes = set(["COD_PBR", *colunas_numericas]) - set(indicadores.columns)
if faltantes:
    raise ValueError(f"Indicadores: colunas ausentes: {sorted(faltantes)}")

codigos = indicadores["COD_PBR"]
if codigos.isna().any() or codigos.duplicated().any():
    raise ValueError("Indicadores: códigos regionais ausentes ou duplicados.")

if set(codigos) != set(prefeituras["COD_PBR"]):
    raise ValueError("Os códigos do CSV não correspondem aos limites regionais.")

valores = indicadores[colunas_numericas].apply(pd.to_numeric, errors="coerce")
if not np.isfinite(valores.to_numpy(dtype=float)).all() or valores.lt(0).any().any():
    raise ValueError("Indicadores: há valores ausentes, não numéricos ou negativos.")

indicadores[colunas_numericas] = valores

if not indicadores["total_ubs_usf"].eq(indicadores["UBS"] + indicadores["USF"]).all():
    raise ValueError("O total regional de unidades difere da soma de UBS e USF.")

if indicadores[["UBS", "USF"]].sum().to_dict() != {"UBS": 45, "USF": 97}:
    raise ValueError("As contagens regionais não somam 45 UBS e 97 USF.")

if not indicadores["p90_ponderado_m"].ge(indicadores["mediana_ponderada_m"]).all():
    raise ValueError("Há região com P90 menor que a mediana.")

faixas = [
    "pct_ate_500m", "pct_500m_a_1km", "pct_1km_a_1333m",
    "pct_acima_1333m", "pct_sem_rota",
]

if indicadores[faixas + ["pct_ate_20"]].gt(100).any().any():
    raise ValueError("Há percentual acima de 100%.")

if not np.allclose(indicadores[faixas].sum(axis=1), 100, atol=0.01, rtol=0):
    raise ValueError("As faixas de distância não somam 100% por região.")

if not np.allclose(
    indicadores[faixas[:3]].sum(axis=1),
    indicadores["pct_ate_20"],
    atol=0.01,
    rtol=0,
):
    raise ValueError("O percentual até aproximadamente 1,33 km está inconsistente.")

print("Indicadores: códigos, valores, contagens e percentuais validados.")
print(f"População regional somada: {indicadores['pop_estimada'].sum():,.2f}")


unidades_com_pb = gpd.sjoin(
    unidades,
    prefeituras[["COD_PBR", "geometry"]],
    how="left",
    predicate="intersects",
)

if unidades_com_pb["tipo"].duplicated().any():
    raise ValueError("Há unidade associada a mais de uma Prefeitura-Bairro.")

if unidades_com_pb["COD_PBR"].isna().any():
    raise ValueError("Há unidade sem Prefeitura-Bairro correspondente.")

contagem_espacial = (
    unidades_com_pb.groupby(["COD_PBR", "tipo_tratado"])
    .size()
    .unstack(fill_value=0)
    .reindex(
        index=indicadores["COD_PBR"],
        columns=["UBS", "USF"],
        fill_value=0,
    )
)

contagem_csv = indicadores.set_index("COD_PBR")[["UBS", "USF"]]

if not contagem_espacial.eq(contagem_csv).all().all():
    raise ValueError("A contagem espacial de unidades diverge do CSV regional.")

print("Unidades associadas a exatamente uma Prefeitura-Bairro:", len(unidades_com_pb))
print("Contagens espaciais iguais às do CSV.")
print(contagem_espacial.to_string())


sobreposicoes = gpd.overlay(
    bairros[["ID", "geometry"]],
    prefeituras[["COD_PBR", "geometry"]],
    how="intersection",
    keep_geom_type=True,
)

sobreposicoes["area_intersecao_m2"] = sobreposicoes.geometry.area

areas_por_par = (
    sobreposicoes.groupby(["ID", "COD_PBR"], as_index=False)
    ["area_intersecao_m2"].sum()
)
areas_por_par = areas_por_par.loc[
    areas_por_par["area_intersecao_m2"].gt(0)
]

# Mantém a região com a maior sobreposição para cada bairro.
associacao = (
    areas_por_par.sort_values(
        ["ID", "area_intersecao_m2", "COD_PBR"],
        ascending=[True, False, True],
    )
    .drop_duplicates("ID")
)

bairros_com_pb = bairros.merge(
    associacao,
    on="ID",
    how="left",
    validate="one_to_one",
)

if bairros_com_pb["COD_PBR"].isna().any():
    raise ValueError("Há bairro sem sobreposição positiva com as Prefeituras-Bairro.")

bairros_com_pb["pct_area_na_pb"] = (
    100 * bairros_com_pb["area_intersecao_m2"]
    / bairros_com_pb.geometry.area
)
bairros_com_pb["associacao_pb"] = "maior_area_de_sobreposicao"

print("Bairros associados:", len(bairros_com_pb))
print("\nCinco menores percentuais na região atribuída:")
print(
    bairros_com_pb.nsmallest(5, "pct_area_na_pb")[
        ["NOME_BAIRRO", "COD_PBR", "pct_area_na_pb"]
    ].round(2).to_string(index=False)
)


pasta_saida = RAIZ / "site/mapa/dados"
pasta_saida.mkdir(parents=True, exist_ok=True)

pref_mapa = (
    prefeituras[["COD_PBR", "PREF_BAIRR", "geometry"]]
    .rename(columns={"COD_PBR": "cod_pbr", "PREF_BAIRR": "nome"})
    .to_crs(epsg=4326)
)

arquivo_pref = pasta_saida / "pref_bairros.geojson"

arquivo_pref.write_text(
    pref_mapa.to_json(drop_id=True),
    encoding="utf-8",
)

# Reabre o arquivo para conferir o resultado da exportação.
pref_exportadas = gpd.read_file(arquivo_pref)

if pref_exportadas.crs.to_epsg() != 4326:
    raise ValueError("GeoJSON exportado com CRS inesperado.")

if (
    len(pref_exportadas) != 10
    or pref_exportadas["cod_pbr"].duplicated().any()
    or set(pref_exportadas["cod_pbr"]) != set(pref_mapa["cod_pbr"])
):
    raise ValueError("A exportação alterou os registros regionais.")

if (
    pref_exportadas.geometry.isna().any()
    or pref_exportadas.geometry.is_empty.any()
    or (~pref_exportadas.geometry.is_valid).any()
):
    raise ValueError("Há geometrias problemáticas no GeoJSON exportado.")

print("\nPrefeituras-Bairro exportadas:", len(pref_exportadas))
print("CRS exportado:", pref_exportadas.crs)
print(f"Tamanho: {arquivo_pref.stat().st_size / 1024:.1f} KiB")
print("Campos:", pref_exportadas.columns.tolist())

unidades_mapa = (
    unidades_com_pb[["tipo", "unidade", "tipo_tratado", "COD_PBR", "geometry"]]
    .rename(columns={
        "tipo": "id_unidade",
        "unidade": "nome",
        "tipo_tratado": "tipo",
        "COD_PBR": "cod_pbr",
    })
    .copy()
)

# O campo original é numérico: confirme antes de convertê-lo em ID textual.
ids = pd.to_numeric(unidades_mapa["id_unidade"], errors="raise")
if not np.equal(ids, np.floor(ids)).all():
    raise ValueError("Há identificador de unidade que não é inteiro.")

unidades_mapa["id_unidade"] = ids.astype("int64").astype("string")
unidades_mapa = unidades_mapa.to_crs(epsg=4326)

arquivo_unidades = pasta_saida / "unidades_saude.geojson"
arquivo_unidades.write_text(
    unidades_mapa.to_json(drop_id=True),
    encoding="utf-8",
)

# Releitura para validar o arquivo que o navegador receberá.
unidades_exportadas = gpd.read_file(arquivo_unidades)

if len(unidades_exportadas) != 142:
    raise ValueError("A quantidade de unidades mudou na exportação.")

if (
    unidades_exportadas["id_unidade"].isna().any()
    or unidades_exportadas["id_unidade"].duplicated().any()
    or set(unidades_exportadas["id_unidade"])
    != set(unidades_mapa["id_unidade"])
):
    raise ValueError("Identificadores inconsistentes após a exportação.")

if unidades_exportadas["tipo"].value_counts().to_dict() != {"USF": 97, "UBS": 45}:
    raise ValueError("A contagem de UBS e USF mudou na exportação.")

if (
    unidades_exportadas.crs.to_epsg() != 4326
    or unidades_exportadas.geometry.isna().any()
    or unidades_exportadas.geometry.is_empty.any()
    or (~unidades_exportadas.geometry.is_valid).any()
    or not unidades_exportadas.geometry.geom_type.eq("Point").all()
):
    raise ValueError("CRS ou geometrias inconsistentes após a exportação.")

originais = unidades_mapa.set_index("id_unidade").sort_index()
exportadas = unidades_exportadas.set_index("id_unidade").sort_index()

for coluna in ["nome", "tipo", "cod_pbr"]:
    if not originais[coluna].eq(exportadas[coluna]).all():
        raise ValueError(f"O campo {coluna} mudou na exportação.")

print("\nUnidades exportadas:", len(unidades_exportadas))
print("Tipos:", unidades_exportadas["tipo"].value_counts().to_dict())
print(f"Tamanho: {arquivo_unidades.stat().st_size / 1024:.1f} KiB")
print("Campos:", unidades_exportadas.columns.tolist())

bairros_mapa = (
    bairros_com_pb[
        ["ID", "NOME_BAIRRO", "COD_PBR", "associacao_pb", "geometry"]
    ]
    .rename(columns={
        "ID": "id_bairro",
        "NOME_BAIRRO": "nome",
        "COD_PBR": "cod_pbr",
    })
    .copy()
)

ids = pd.to_numeric(bairros_mapa["id_bairro"], errors="raise")
if not np.equal(ids, np.floor(ids)).all():
    raise ValueError("Há identificador de bairro que não é inteiro.")

bairros_mapa["id_bairro"] = ids.astype("int64").astype("string")
bairros_mapa = bairros_mapa.to_crs(epsg=4326)
# O mapa utiliza apenas longitude e latitude.
bairros_mapa["geometry"] = bairros_mapa.geometry.force_2d()

arquivo_bairros = pasta_saida / "bairros.geojson"
arquivo_bairros.write_text(
    bairros_mapa.to_json(drop_id=True),
    encoding="utf-8",
)

bairros_exportados = gpd.read_file(arquivo_bairros)

from shapely.validation import explain_validity

print("\nDiagnóstico dos bairros:")
print("CRS após exportação:", bairros_exportados.crs)
print("Tipos:", bairros_exportados.geometry.geom_type.value_counts().to_dict())
print("Ausentes:", bairros_exportados.geometry.isna().sum())
print("Vazias:", bairros_exportados.geometry.is_empty.sum())
print("Inválidas antes da reprojeção:", (~bairros_com_pb.geometry.is_valid).sum())
print("Inválidas após reprojeção:", (~bairros_mapa.geometry.is_valid).sum())
print("Inválidas após exportação:", (~bairros_exportados.geometry.is_valid).sum())

for bairro in bairros_exportados.loc[
    ~bairros_exportados.geometry.is_valid
].itertuples():
    print(
        f"ID={bairro.id_bairro} | {bairro.nome} | "
        f"{explain_validity(bairro.geometry)}"
    )

if (
    len(bairros_exportados) != 171
    or bairros_exportados["id_bairro"].isna().any()
    or bairros_exportados["id_bairro"].duplicated().any()
    or set(bairros_exportados["id_bairro"]) != set(bairros_mapa["id_bairro"])
):
    raise ValueError("Registros de bairros inconsistentes após a exportação.")

if (
    bairros_exportados.crs.to_epsg() != 4326
    or bairros_exportados.geometry.isna().any()
    or bairros_exportados.geometry.is_empty.any()
    or (~bairros_exportados.geometry.is_valid).any()
    or not bairros_exportados.geometry.geom_type.isin(
        ["Polygon", "MultiPolygon"]
    ).all()
):
    raise ValueError("CRS ou geometrias de bairros inconsistentes.")

originais = bairros_mapa.set_index("id_bairro").sort_index()
exportados = bairros_exportados.set_index("id_bairro").sort_index()

for coluna in ["nome", "cod_pbr", "associacao_pb"]:
    if not originais[coluna].eq(exportados[coluna]).all():
        raise ValueError(f"O campo {coluna} mudou na exportação.")

print("\nBairros exportados:", len(bairros_exportados))
print("CRS exportado:", bairros_exportados.crs)
print(f"Tamanho: {arquivo_bairros.stat().st_size / 1024:.1f} KiB")
print("Campos:", bairros_exportados.columns.tolist())


import json

campos_indicadores = {
    "qtd_bairros": "qtd_bairros",
    "pop_estimada": "pop_estimada",
    "UBS": "qtd_ubs",
    "USF": "qtd_usf",
    "total_ubs_usf": "total_unidades",
    "ubs_usf_por_10_mil": "unidades_por_10_mil",
    "mediana_ponderada_m": "mediana_m",
    "p90_ponderado_m": "p90_m",
    "pct_ate_20": "pct_ate_1333m",
    "pop_sem_rota": "pop_sem_rota",
    "pct_sem_rota": "pct_sem_rota",
    "rendimento_setorial_ponderado_rs": "rendimento_setorial_ponderado_rs",
}

tabela_mapa = indicadores[
    ["COD_PBR", *campos_indicadores]
].rename(columns={"COD_PBR": "cod_pbr", **campos_indicadores}).copy()

tabela_mapa["pct_ate_1km"] = (
    indicadores["pct_ate_500m"] + indicadores["pct_500m_a_1km"]
)

for coluna in ["qtd_bairros", "qtd_ubs", "qtd_usf", "total_unidades"]:
    if not tabela_mapa[coluna].eq(np.floor(tabela_mapa[coluna])).all():
        raise ValueError(f"{coluna}: contagens não inteiras.")
    tabela_mapa[coluna] = tabela_mapa[coluna].astype("int64")

# Converte os valores do pandas para tipos compatíveis com JSON.
regioes = json.loads(tabela_mapa.set_index("cod_pbr").to_json(orient="index"))

conteudo = {
    "versao_contrato": 1,
    "metadados": {
        "unidade_distancia": "metro",
        "unidade_percentual": "0 a 100",
        "limite_1333m_exato": 4_000 * 20 / 60,
        "aviso_distancias": (
            "Percursos estimados pela rede de pedestres, incluindo ligações "
            "em linha reta entre os pontos e a rede. Não medem acesso ao atendimento."
        ),
        "aviso_percentis": (
            "Mediana e P90 ponderados pela população estimada com rota. "
            "Percentuais por distância usam toda a população estimada da região."
        ),
        "aviso_unidades": (
            "Camada do portal Salvador Dados com metadados de 2021. "
            "O funcionamento atual das unidades não foi verificado."
        ),
        "aviso_rendimento": (
            "Indicador aproximado: médias setoriais dos responsáveis com rendimento "
            "ponderadas pelo total de responsáveis e pela fração territorial do setor. "
            "Não equivale à média regional exata nem à renda domiciliar per capita. "
            "Valores em reais de 2022."
        ),
        "aviso_bairros": (
            "Associação à Prefeitura-Bairro pela maior área de sobreposição. "
            "Não foram calculados indicadores por bairro."
        ),
    },
    "regioes": regioes,
}

arquivo_indicadores = pasta_saida / "indicadores.json"
arquivo_indicadores.write_text(
    json.dumps(conteudo, ensure_ascii=False, allow_nan=False, indent=2),
    encoding="utf-8",
)

exportado = json.loads(arquivo_indicadores.read_text(encoding="utf-8"))
regioes_exportadas = exportado["regioes"]

if set(regioes_exportadas) != set(pref_mapa["cod_pbr"]):
    raise ValueError("Códigos regionais inconsistentes no JSON.")

for linha in tabela_mapa.to_dict(orient="records"):
    registro = regioes_exportadas[linha["cod_pbr"]]
    for campo, valor in linha.items():
        if campo != "cod_pbr" and not np.isclose(
            registro[campo], valor, atol=1e-7, rtol=0
        ):
            raise ValueError(f"Valor alterado na exportação: {campo}")

print("\nRegiões no JSON:", len(regioes_exportadas))
print("Indicadores preservados após exportação.")
print(f"Tamanho: {arquivo_indicadores.stat().st_size / 1024:.1f} KiB")


sedes = gpd.read_file(
    RAIZ / "dados/brutos/prefeitura/sedes_das_prefeituras_bairro_v1_p.gpkg",
    layer="sedes_das_prefeituras_bairro_v1_p",
)

siglas = sedes["sigla"].astype("string").str.strip().str.upper()
sedes_mapa = sedes.loc[
    siglas.str.fullmatch(r"PREFEITURA BAIRRO [IVX]+", na=False),
    ["sigla", "nome", "logradouro", "num_porta", "complement", "bairro", "geometry"],
].copy()

sedes_mapa["cod_pbr"] = (
    sedes_mapa["sigla"].astype("string").str.strip().str.upper()
    .str.extract(r"PREFEITURA BAIRRO ([IVX]+)$", expand=False)
)

if (
    len(sedes_mapa) != 10
    or sedes_mapa["cod_pbr"].isna().any()
    or sedes_mapa["cod_pbr"].duplicated().any()
    or set(sedes_mapa["cod_pbr"]) != set(prefeituras["COD_PBR"])
):
    raise ValueError("Sedes: códigos regionais inconsistentes.")

if sedes_mapa.crs is None:
    raise ValueError("Sedes: CRS não informado.")

if (
    sedes_mapa.geometry.isna().any()
    or sedes_mapa.geometry.is_empty.any()
    or (~sedes_mapa.geometry.is_valid).any()
    or not sedes_mapa.geometry.geom_type.eq("Point").all()
):
    raise ValueError("Sedes: geometrias inconsistentes.")

sedes_mapa = sedes_mapa.drop(columns="sigla").rename(columns={
    "num_porta": "numero",
    "complement": "complemento",
})

for coluna in ["nome", "logradouro", "numero", "complemento", "bairro"]:
    sedes_mapa[coluna] = (
        sedes_mapa[coluna].astype("string").fillna("").str.strip()
    )

sedes_mapa["observacao"] = ""
sedes_mapa.loc[sedes_mapa["cod_pbr"].eq("VII"), "observacao"] = (
    "A base apresenta números diferentes no logradouro e no campo número. "
    "Endereço pendente de confirmação."
)
sedes_mapa["fonte"] = "Salvador Dados — Sedes das Prefeituras-Bairro"

sedes_mapa = sedes_mapa.to_crs(epsg=4326)
sedes_mapa["geometry"] = sedes_mapa.geometry.force_2d()

arquivo_sedes = pasta_saida / "sedes_prefeituras.geojson"
arquivo_sedes.write_text(
    sedes_mapa.to_json(drop_id=True),
    encoding="utf-8",
)

sedes_exportadas = gpd.read_file(arquivo_sedes)

if (
    len(sedes_exportadas) != 10
    or sedes_exportadas["cod_pbr"].duplicated().any()
    or set(sedes_exportadas["cod_pbr"]) != set(sedes_mapa["cod_pbr"])
    or sedes_exportadas.crs.to_epsg() != 4326
    or sedes_exportadas.geometry.isna().any()
    or sedes_exportadas.geometry.is_empty.any()
    or (~sedes_exportadas.geometry.is_valid).any()
    or not sedes_exportadas.geometry.geom_type.eq("Point").all()
):
    raise ValueError("Sedes: falha na conferência do GeoJSON.")

print("\nSedes exportadas:", len(sedes_exportadas))
print("CRS exportado:", sedes_exportadas.crs)
print(f"Tamanho: {arquivo_sedes.stat().st_size / 1024:.1f} KiB")
print("Campos:", sedes_exportadas.columns.tolist())