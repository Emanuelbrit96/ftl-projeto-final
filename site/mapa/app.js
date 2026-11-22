const statusMapa = document.querySelector("#status");
const botaoVerTudo = document.querySelector("#ver-tudo");

async function iniciarMapa() {
  try {
    const resposta = await fetch("./dados/pref_bairros.geojson");
    if (!resposta.ok) {
      throw new Error(
        `Não foi possível carregar as regiões: HTTP ${resposta.status}`
      );
    }
    const dados = await resposta.json();

    const respostaIndicadores = await fetch("./dados/indicadores.json");
    if (!respostaIndicadores.ok) {
      throw new Error(
        `Erro ao carregar indicadores: HTTP ${respostaIndicadores.status}`
      );
    }
    const indicadores = await respostaIndicadores.json();
    const painelRegiao = document.querySelector("#painel-regiao");

    function mostrarRegiao(feature) {
      const registro = indicadores.regioes[feature.properties.cod_pbr];
      if (!registro) {
        throw new Error(
          `Região sem indicadores: ${feature.properties.cod_pbr}`
        );
      }

      const inteiro = new Intl.NumberFormat("pt-BR", {
        maximumFractionDigits: 0
      });
      const decimal = new Intl.NumberFormat("pt-BR", {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
      });
      const moeda = new Intl.NumberFormat("pt-BR", {
        style: "currency",
        currency: "BRL"
      });

      const titulo = document.createElement("h2");
      titulo.textContent = feature.properties.nome;

      const lista = document.createElement("dl");
      const campos = [
        ["População estimada", inteiro.format(registro.pop_estimada)],
        ["Bairros", inteiro.format(registro.qtd_bairros)],
        ["UBS", inteiro.format(registro.qtd_ubs)],
        ["USF", inteiro.format(registro.qtd_usf)],
        ["Total de unidades", inteiro.format(registro.total_unidades)],
        [
          "Unidades por 10 mil habitantes",
          decimal.format(registro.unidades_por_10_mil)
        ],
        ["Distância mediana", `${inteiro.format(registro.mediana_m)} m`],
        ["P90 da distância", `${inteiro.format(registro.p90_m)} m`],
        [
          "População a até 1 km",
          `${decimal.format(registro.pct_ate_1km)}%`
        ],
        [
          "População a até ≈ 1,33 km",
          `${decimal.format(registro.pct_ate_1333m)}%`
        ],
        [
          "Sem rota no modelo",
          `${inteiro.format(registro.pop_sem_rota)} pessoas estimadas ` +
          `(${decimal.format(registro.pct_sem_rota)}%)`
        ],
        [
          "Rendimento setorial ponderado — indicador aproximado",
          moeda.format(registro.rendimento_setorial_ponderado_rs)
        ]
      ];

      for (const [rotulo, valor] of campos) {
        const termo = document.createElement("dt");
        termo.textContent = rotulo;

        const descricao = document.createElement("dd");
        descricao.textContent = valor;

        lista.append(termo, descricao);
      }

      const notas = document.createElement("details");
      const resumo = document.createElement("summary");
      resumo.textContent = "Como interpretar estes indicadores";
      notas.append(resumo);

      const explicacoes = [
        "O P90 é a distância até a qual se encontra pelo menos 90% da população estimada com rota.",
        indicadores.metadados.aviso_percentis,
        indicadores.metadados.aviso_distancias,
        indicadores.metadados.aviso_unidades,
        indicadores.metadados.aviso_rendimento
      ];

      for (const texto of explicacoes) {
        const paragrafo = document.createElement("p");
        paragrafo.textContent = texto;
        notas.append(paragrafo);
      }

      painelRegiao.replaceChildren(titulo, lista, notas);
    }

   const mapa = L.map("mapa", { maxZoom: 19 });

        mapa.createPane("unidades");
        mapa.getPane("unidades").style.zIndex = "450";

        mapa.createPane("bairros");
        mapa.getPane("bairros").style.zIndex = "425";

        // Novo: nomes das Prefeituras-Bairro.
        mapa.createPane("rotulos");
        mapa.getPane("rotulos").style.zIndex = "430";
        mapa.getPane("rotulos").style.pointerEvents = "none";

    mapa.attributionControl.addAttribution(
      "Limites: Salvador Dados / FMLF"
    );

    const coresRegioes = {
        I: "#66c2a5",
        II: "#8da0cb",
        III: "#fc8d62",
        IV: "#e5c494",
        V: "#a6d854",
        VI: "#e78ac3",
        VII: "#ffd92f",
        VIII: "#80b1d3",
        IX: "#b3a2ce",
        X: "#b3b3b3"
    };

    function estiloPadrao(feature) {
        return {
            color: "#3f3737",
            weight: 1.5,
            fillColor: coresRegioes[feature.properties.cod_pbr] ?? "#cccccc",
            fillOpacity: 0.65
        };
    }

    const regioes = L.geoJSON(dados, {
      style: estiloPadrao,

      onEachFeature(feature, camada) {
        const nome = document.createElement("span");

            // Remove somente o prefixo "Prefeitura-bairro ... - ".
            const nomeCurto = feature.properties.nome.split(" - ").slice(1).join(" - ");
            nome.textContent = nomeCurto || feature.properties.nome;

            camada.bindTooltip(nome, {
            permanent: true,
            direction: "center",
            className: "rotulo-regiao",
            pane: "rotulos",
            interactive: false
        });

        camada.on("click", () => {
          regioes.resetStyle();

          camada.setStyle({
            color: "#9b4817",
            weight: 3,
            fillColor: "#f5ba76",
            fillOpacity: 0.7
          });

          camada.bringToFront();
          mapa.fitBounds(camada.getBounds(), {
            padding: [24, 24]
          });

          statusMapa.textContent = feature.properties.nome;
          mostrarRegiao(feature);
        });
      }
    }).addTo(mapa);

    function verTudo() {
      regioes.resetStyle();
      mapa.closePopup();
      mapa.fitBounds(regioes.getBounds(), {
        padding: [24, 24]
      });

      statusMapa.textContent =
        "Selecione uma das dez Prefeituras-Bairro.";

      const titulo = document.createElement("h2");
      titulo.textContent = "Região selecionada";

      const instrucao = document.createElement("p");
      instrucao.textContent =
        "Clique em uma Prefeitura-Bairro para consultar os indicadores.";

      painelRegiao.replaceChildren(titulo, instrucao);
    }

    botaoVerTudo.addEventListener("click", verTudo);
    botaoVerTudo.disabled = false;
    verTudo();

    const respostaUnidades = await fetch("./dados/unidades_saude.geojson");
    if (!respostaUnidades.ok) {
      throw new Error(
        `Erro ao carregar unidades: HTTP ${respostaUnidades.status}`
      );
    }
    const dadosUnidades = await respostaUnidades.json();

    const nomesRegioes = new Map(
      dados.features.map(feature => [
        feature.properties.cod_pbr,
        feature.properties.nome
      ])
    );

    const gruposUnidades = {
      UBS: L.layerGroup().addTo(mapa),
      USF: L.layerGroup().addTo(mapa)
    };

    const coresUnidades = {
      UBS: "#174a7e",
      USF: "#982b5c"
    };
    function raioUnidade() {
        const zoom = mapa.getZoom();

        if (zoom <= 11) return 4;
        if (zoom <= 12) return 5;
        if (zoom <= 13) return 6;
        if (zoom <= 14) return 7;
        return 9;
    }
    function iconeUnidade(tipo) {
        const tamanho = 2 * raioUnidade() + 4;
        const categoria = tipo.trim().toLowerCase();

        return L.divIcon({
            className: "marcador-saude",
            html: `<span class="simbolo-saude simbolo-${categoria}"></span>`,
            iconSize: [tamanho, tamanho],
            iconAnchor: [tamanho / 2, tamanho / 2],
            popupAnchor: [0, -tamanho / 2]
        });
    }

    for (const feature of dadosUnidades.features) {
      const unidade = feature.properties;

      if (!gruposUnidades[unidade.tipo]) {
        throw new Error(
          `Tipo de unidade inesperado: ${unidade.tipo}`
        );
      }

      const [longitude, latitude] = feature.geometry.coordinates;

      const marcador = L.marker([latitude, longitude], {
            pane: "unidades",
            icon: iconeUnidade(unidade.tipo),
            title: `${unidade.tipo} — ${unidade.nome}`,
            riseOnHover: true,
            bubblingMouseEvents: false
      });

      const popup = document.createElement("div");
      const nome = document.createElement("strong");
      nome.textContent = unidade.nome;
      popup.append(nome);

      const informacoes = [
        `Tipo: ${unidade.tipo}`,
        nomesRegioes.get(unidade.cod_pbr) ?? "Região não identificada",
        indicadores.metadados.aviso_unidades
      ];

      for (const texto of informacoes) {
        const paragrafo = document.createElement("p");
        paragrafo.textContent = texto;
        popup.append(paragrafo);
      }

      marcador.bindPopup(popup);
      marcador.addTo(gruposUnidades[unidade.tipo]);
    }
    
    mapa.on("zoomend", () => {
        for (const [tipo, grupo] of Object.entries(gruposUnidades)) {
        grupo.eachLayer(marcador => {
        marcador.setIcon(iconeUnidade(tipo));
        });
  }
    });


    const controleCamadas = L.control.layers(
        null,
        {
            "UBS — azul": gruposUnidades.UBS,
            "USF — roxo": gruposUnidades.USF
        },
        { collapsed: false }
    ).addTo(mapa);

    const respostaBairros = await fetch("./dados/bairros.geojson");
    if (!respostaBairros.ok) {
        throw new Error(
            `Erro ao carregar bairros: HTTP ${respostaBairros.status}`
        );
        }
    const dadosBairros = await respostaBairros.json();

    const camadaBairros = L.geoJSON(dadosBairros, {
        pane: "bairros",
        style: {
            color: "#555555",
            weight: 1,
            fillOpacity: 0,
            dashArray: "3 3"
        },

        onEachFeature(feature, camada) {
            const bairro = feature.properties;
            const popup = document.createElement("div");

            const titulo = document.createElement("strong");
            titulo.textContent = bairro.nome;
            popup.append(titulo);

            for (const texto of [
            nomesRegioes.get(bairro.cod_pbr) ?? "Região não identificada",
            indicadores.metadados.aviso_bairros
            ]) {
            const paragrafo = document.createElement("p");
            paragrafo.textContent = texto;
            popup.append(paragrafo);
            }

            camada.bindPopup(popup);
        }
    });

        // Registra no controle, sem ativar a camada inicialmente.
        controleCamadas.addOverlay(camadaBairros, "Limites dos bairros");

        const respostaSedes = await fetch("./dados/sedes_prefeituras.geojson");
        if (!respostaSedes.ok) {
        throw new Error(
            `Erro ao carregar sedes: HTTP ${respostaSedes.status}`
        );
        }
        const dadosSedes = await respostaSedes.json();

        function criarIconeSede() {
        const tamanho = 3 * raioUnidade() + 4;

        return L.divIcon({
            className: "marcador-sede",
            html: `
            <div class="simbolo-sede" aria-hidden="true">
                <svg viewBox="0 0 24 24" fill="none"
                    stroke="currentColor" stroke-width="1.8">
                <path d="M3 9 12 4l9 5H3Z"/>
                <path d="M5 10v9m5-9v9m4-9v9m5-9v9M3 20h18"/>
                </svg>
            </div>
            `,
            iconSize: [tamanho, tamanho],
            iconAnchor: [tamanho / 2, tamanho / 2],
            popupAnchor: [0, -tamanho / 2]
        });
        }

        const camadaSedes = L.geoJSON(dadosSedes, {
        pointToLayer(feature, latlng) {
            return L.marker(latlng, {
            icon: criarIconeSede(),
            title: feature.properties.nome,
            riseOnHover: true
            });
        },

        onEachFeature(feature, camada) {
            const sede = feature.properties;
            const popup = document.createElement("div");

            const titulo = document.createElement("strong");
            titulo.textContent = sede.nome;
            popup.append(titulo);

            const campos = [
            ["Logradouro", sede.logradouro],
            ["Número informado", sede.numero],
            ["Complemento", sede.complemento],
            ["Bairro", sede.bairro],
            ["Observação", sede.observacao],
            ["Fonte", sede.fonte]
            ];

            for (const [rotulo, valor] of campos) {
            if (!valor) continue;

            const paragrafo = document.createElement("p");
            paragrafo.textContent = `${rotulo}: ${valor}`;
            popup.append(paragrafo);
            }

            camada.bindPopup(popup);
        }
        });

        // Disponibiliza o filtro; as sedes começam desativadas.
        controleCamadas.addOverlay(
        camadaSedes,
        "Sedes das Prefeituras-Bairro"
        );
        
        const legendaIcones = L.control({ position: "bottomleft" });
        legendaIcones.onAdd = function () {
        const caixa = L.DomUtil.create("div", "legenda-icones");

        caixa.innerHTML = `
            <strong>Símbolos</strong>

            <div class="item-legenda">
            <span class="simbolo-saude simbolo-ubs" aria-hidden="true"></span>
            <span>UBS — Unidade Básica de Saúde</span>
            </div>

            <div class="item-legenda">
            <span class="simbolo-saude simbolo-usf" aria-hidden="true"></span>
            <span>USF — Unidade de Saúde da Família</span>
            </div>

            <div class="item-legenda">
            <span class="simbolo-sede" aria-hidden="true">
                <svg viewBox="0 0 24 24" fill="none"
                    stroke="currentColor" stroke-width="1.8">
                <path d="M3 9 12 4l9 5H3Z"/>
                <path d="M5 10v9m5-9v9m4-9v9m5-9v9M3 20h18"/>
                </svg>
            </span>
            <span>Sede da Prefeitura-Bairro</span>
            </div>
        `;

        L.DomEvent.disableClickPropagation(caixa);
        L.DomEvent.disableScrollPropagation(caixa);

        return caixa;
        };

        legendaIcones.addTo(mapa);


        mapa.on("zoomend", () => {
        camadaSedes.eachLayer(marcador => {
            marcador.setIcon(criarIconeSede());
        });
        });

  } catch (erro) {
    console.error(erro);
    statusMapa.textContent =
      `Erro ao abrir o mapa: ${erro.message}`;
  }
}

iniciarMapa();