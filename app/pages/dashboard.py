from __future__ import annotations

import pandas as pd
import streamlit as st

from auth.auth_service import current_user, require_login
from domain.design_tokens import CHART_PALETTE_CATEGORICAL, CHART_PALETTE_SEQUENTIAL, COLORS
from domain.contracts import SMALL_BASE_THRESHOLD_DAYS
from services.actions_log import get_pendentes, registrar_acao
from services.exporter import (
    csv_filename,
    excel_filename,
    export_filtered_csv,
    export_filtered_excel,
)
from services.alerts import gerar_alertas
from services.data_loader import (
    get_categorias,
    get_clientes,
    get_date_range,
    get_dias_semana,
    get_metodos_pagamento,
    get_periodos,
    get_produtos,
    load_data,
)
from services.filters import apply_filters
from services.metrics import (
    faturamento_por_dia,
    faturamento_por_dia_semana,
    faturamento_por_hora,
    faturamento_por_periodo,
    heatmap_hora_dia,
    kpis_gerais,
    metricas_bandeira,
    metricas_pagamento,
    pareto_produtos,
    participacao_categorias,
    produtos_baixa_saida,
    ranking_clientes,
    ranking_produtos,
)
from services.recommendations import generate_recommendations
from services.intelligence import (
    detect_anomalies,
    forecast_next_days,
    get_hour_pattern,
    get_revenue_trend,
    get_weekday_pattern,
)
from services.finance import (
    get_cobertura_custo,
    get_margin,
    get_profit_by_unit,
    get_top_profit_products,
    get_total_profit,
    get_worst_profit_products,
)
from services.simulator import (
    simular_ajuste_preco,
    simular_crescimento_cliente,
    simular_pix,
    simular_projecao_mensal,
    simular_reducao_custo,
    simular_remocao_baixa_saida,
)

# ---------------------------------------------------------------------------
# Helpers de formatação
# ---------------------------------------------------------------------------
def _brl(valor: float) -> str:
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _pct(valor: float) -> str:
    return f"{valor:.1f}%"


_PRIORITY_COLOR = {
    "alta":  ("#ff4b4b", "🔴"),
    "media": ("#ffa500", "🟡"),
    "baixa": ("#21c354", "🟢"),
}


# ---------------------------------------------------------------------------
# Persistência de filtros — chaves no session_state
# ---------------------------------------------------------------------------
_F = "f_"  # prefixo para chaves de filtro


def _ss_get(key: str, default):
    return st.session_state.get(f"{_F}{key}", default)


def _ss_set(key: str, value) -> None:
    st.session_state[f"{_F}{key}"] = value


# ---------------------------------------------------------------------------
# Bloco: Filtros na sidebar (com persistência)
# ---------------------------------------------------------------------------
def _render_filtros(df_full: pd.DataFrame) -> pd.DataFrame:
    st.sidebar.markdown("---")
    st.sidebar.caption("FILTROS")

    data_min, data_max = get_date_range(df_full)

    data_ini = st.sidebar.date_input(
        "De",
        value=_ss_get("data_ini", data_min),
        min_value=data_min, max_value=data_max,
        key="f_data_ini",
    )
    data_fim = st.sidebar.date_input(
        "Até",
        value=_ss_get("data_fim", data_max),
        min_value=data_min, max_value=data_max,
        key="f_data_fim",
    )

    clientes_sel = st.sidebar.multiselect(
        "Clientes", options=get_clientes(df_full),
        default=_ss_get("clientes", []), key="f_clientes",
    )
    categorias_sel = st.sidebar.multiselect(
        "Categorias", options=get_categorias(df_full),
        default=_ss_get("categorias", []), key="f_categorias",
    )
    metodos_sel = st.sidebar.multiselect(
        "Método de pagamento", options=get_metodos_pagamento(df_full),
        default=_ss_get("metodos", []), key="f_metodos",
    )
    periodos_sel = st.sidebar.multiselect(
        "Período do dia", options=get_periodos(df_full),
        default=_ss_get("periodos", []), key="f_periodos",
    )
    dias_sel = st.sidebar.multiselect(
        "Dia da semana", options=get_dias_semana(df_full),
        default=_ss_get("dias", []), key="f_dias",
    )

    df_para_prod = df_full if not categorias_sel else df_full[df_full["categoria"].isin(categorias_sel)]
    # Limpar produtos salvos se categoria mudou
    saved_produtos = [p for p in _ss_get("produtos", []) if p in get_produtos(df_para_prod)]
    produtos_sel = st.sidebar.multiselect(
        "Produtos", options=get_produtos(df_para_prod),
        default=saved_produtos, key="f_produtos",
    )

    # Nota: session_state já é persistido automaticamente via key= de cada widget.
    # Chamar _ss_set após o widget causa StreamlitAPIException em Streamlit 1.35+.

    if st.sidebar.button("Limpar filtros", use_container_width=True):
        for k in ["data_ini","data_fim","clientes","categorias","metodos","periodos","dias","produtos"]:
            st.session_state.pop(f"{_F}{k}", None)
        st.rerun()

    return apply_filters(
        df_full,
        data_inicio=data_ini,
        data_fim=data_fim,
        clientes=clientes_sel or None,
        categorias=categorias_sel or None,
        produtos=produtos_sel or None,
        metodos_pagamento=metodos_sel or None,
        periodos=periodos_sel or None,
        dias_semana=dias_sel or None,
    )


# ---------------------------------------------------------------------------
# Bloco: KPIs
# ---------------------------------------------------------------------------
def _render_kpis(df: pd.DataFrame) -> dict:
    kpis = kpis_gerais(df)
    cols = st.columns(6)
    dados = [
        ("Faturamento",  _brl(kpis["faturamento"]),      "💰"),
        ("Transações",   f'{kpis["n_transacoes"]:,}',    "🧾"),
        ("Itens",        f'{kpis["n_itens"]:,}',         "📦"),
        ("Produtos",     str(kpis["n_produtos"]),         "🏷️"),
        ("Clientes",     str(kpis["n_clientes"]),         "🏢"),
        ("Ticket Médio", _brl(kpis["ticket_medio"]),     "🎫"),
    ]
    for col, (label, valor, icone) in zip(cols, dados):
        col.metric(f"{icone} {label}", valor)
    return kpis


# ---------------------------------------------------------------------------
# Bloco: Alertas
# ---------------------------------------------------------------------------
def _render_alertas(df: pd.DataFrame) -> list:
    alertas = gerar_alertas(df)
    if not alertas:
        return alertas

    with st.expander(f"⚠️ Alertas automáticos ({len(alertas)})", expanded=True):
        for alerta in alertas:
            msg = f"**{alerta.titulo}** — {alerta.mensagem}  \n*Ação:* {alerta.acao}"
            if alerta.severity == "error":
                st.error(msg)
            elif alerta.severity == "warning":
                st.warning(msg)
            else:
                st.info(msg)
    return alertas


# ---------------------------------------------------------------------------
# Bloco: Recomendações do Sistema (FASE 6)
# ---------------------------------------------------------------------------
def _render_recomendacoes(df: pd.DataFrame, kpis: dict, alertas: list) -> None:
    recs = generate_recommendations(df, kpis, alertas)

    if not recs:
        st.success("Nenhuma recomendação crítica no período selecionado.")
        return

    st.markdown(f"**{len(recs)} recomendação(ões) gerada(s) — ordenadas por prioridade**")

    for rec in recs:
        cor, icone = _PRIORITY_COLOR.get(rec.prioridade, ("#cccccc", "⚪"))

        st.markdown(
            f"""
            <div style="
                border-left: 5px solid {cor};
                background: #fafafa;
                border-radius: 6px;
                padding: 12px 16px;
                margin-bottom: 10px;
            ">
                <div style="font-size:0.8rem; color:{cor}; font-weight:700; text-transform:uppercase; margin-bottom:4px;">
                    {icone} Prioridade {rec.prioridade.upper()} &nbsp;·&nbsp; {rec.tipo.upper()}
                </div>
                <div style="font-size:1rem; font-weight:700; margin-bottom:6px;">{rec.titulo}</div>
                <div style="font-size:0.9rem; color:#333; margin-bottom:6px;">{rec.descricao}</div>
                <div style="font-size:0.85rem; color:#555; background:#f0f4ff;
                            padding:6px 10px; border-radius:4px;">
                    📈 <strong>Impacto estimado:</strong> {rec.impacto_estimado}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Botão para registrar ação tomada
        btn_key = f"acao_{rec.tipo}_{rec.titulo[:20]}"
        if st.button(f"✅ Registrar ação tomada", key=btn_key):
            registrar_acao(
                tipo=rec.tipo,
                titulo=rec.titulo,
                descricao=rec.descricao,
                usuario=current_user() or "sistema",
            )
            st.success("Ação registrada no log.")

    # Ações pendentes
    pendentes = get_pendentes()
    if pendentes:
        with st.expander(f"📋 Ações pendentes registradas ({len(pendentes)})", expanded=False):
            for p in pendentes:
                st.markdown(
                    f"- **{p['data'][:10]}** | `{p['tipo']}` | {p['titulo']} → _{p['resultado']}_"
                )


# ---------------------------------------------------------------------------
# Bloco: Simulações (FASE 7)
# ---------------------------------------------------------------------------
def _render_simulacoes(df: pd.DataFrame) -> None:
    st.markdown("### 🧮 Simulações Financeiras")
    st.caption("Modele cenários e veja o impacto antes de decidir.")

    tab_pix, tab_mix, tab_cliente, tab_proj = st.tabs([
        "Adesão ao PIX", "Mix de Produtos", "Crescimento de Cliente", "Projeção Mensal"
    ])

    with tab_pix:
        col1, col2 = st.columns(2)
        with col1:
            meta_pix = st.slider("Meta de adesão ao PIX (%)", 10, 80, 20, key="sim_pix_meta")
        with col2:
            taxa_cartao = st.slider("Taxa média do cartão (%)", 1.0, 5.0, 2.5, step=0.1, key="sim_pix_taxa")

        res = simular_pix(df, meta_pix_pct=meta_pix, taxa_cartao_pct=taxa_cartao)
        _render_sim_result(res)

    with tab_mix:
        reposicao = st.slider(
            "Fator de reposição — % do faturamento perdido recuperado com substitutos",
            0, 100, 50, key="sim_mix_repo"
        )
        res = simular_remocao_baixa_saida(df, reposicao_fator=reposicao / 100)
        _render_sim_result(res)

    with tab_cliente:
        clientes_disponiveis = sorted(df["cliente"].unique().tolist())
        if clientes_disponiveis:
            cliente_sel = st.selectbox("Cliente", options=clientes_disponiveis, key="sim_cli_sel")
            meta_pct    = st.slider("Meta: % da média do grupo", 50, 100, 80, key="sim_cli_meta")
            res = simular_crescimento_cliente(df, cliente=cliente_sel, meta_pct_media=float(meta_pct))
            _render_sim_result(res)
        else:
            st.info("Nenhum cliente disponível para simulação.")

    with tab_proj:
        n_dias = df["data"].nunique()
        st.info(f"Base atual: **{n_dias} dia(s)**. Extrapolando para 30 dias.")
        res = simular_projecao_mensal(df)
        _render_sim_result(res)


def _render_sim_result(res) -> None:
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"**Cenário atual**  \n{res.cenario_atual}")
    with col2:
        st.markdown(f"**Cenário simulado**  \n{res.cenario_simulado}")

    cor  = "#21c354" if res.impacto_financeiro >= 0 else "#ff4b4b"
    sinal = "+" if res.impacto_financeiro >= 0 else ""
    st.markdown(
        f"""
        <div style="background:#f0f4ff; border-radius:8px; padding:12px 16px; margin-top:8px;">
            <span style="font-size:1.4rem; font-weight:700; color:{cor};">
                {sinal}{_brl(res.impacto_financeiro)}
            </span><br>
            <span style="font-size:0.9rem; color:#333;">{res.impacto_descricao}</span><br>
            <span style="font-size:0.8rem; color:#777; margin-top:4px; display:block;">
                ⚠️ <em>Premissas: {res.premissas}</em>
            </span>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Bloco: Clientes
# ---------------------------------------------------------------------------
def _render_clientes(df: pd.DataFrame) -> None:
    st.subheader("🏢 Clientes")
    st.caption("Ranking por faturamento, ticket médio e participação no total.")
    rank = ranking_clientes(df)
    if rank.empty:
        st.info("Sem dados para exibir.")
        return

    n_clientes = len(rank)

    try:
        import plotly.express as px
        HAS_PLOTLY = True
    except ImportError:
        HAS_PLOTLY = False

    if n_clientes <= 4 and HAS_PLOTLY:
        # Rosca — poucos clientes
        col1, col2 = st.columns([1, 1.6])
        with col1:
            fig = px.pie(
                rank, names="cliente", values="faturamento", hole=0.4,
                color_discrete_sequence=CHART_PALETTE_CATEGORICAL,
            )
            fig.update_traces(
                textposition="outside", textinfo="percent+label",
                textfont_size=12, pull=[0.03] * n_clientes,
            )
            fig.update_layout(
                showlegend=False,
                margin=dict(t=20, b=20, l=10, r=10), height=280,
                paper_bgcolor=COLORS["surface"],
                font=dict(family="sans-serif", size=12, color=COLORS["text_primary"]),
            )
            st.plotly_chart(fig, use_container_width=True)
        with col2:
            display = rank[["cliente", "faturamento", "participacao_pct", "transacoes", "ticket_medio"]].copy()
            display.columns = ["Cliente", "Faturamento (R$)", "% Total", "Transações", "Ticket Médio"]
            display["Faturamento (R$)"] = display["Faturamento (R$)"].apply(_brl)
            display["% Total"]          = display["% Total"].apply(_pct)
            display["Ticket Médio"]     = display["Ticket Médio"].apply(_brl)
            st.dataframe(display, use_container_width=True, hide_index=True)
    else:
        # Barra horizontal — muitos clientes
        col1, col2 = st.columns([1.6, 1])
        with col1:
            if HAS_PLOTLY:
                fig = px.bar(
                    rank, x="faturamento", y="cliente",
                    orientation="h",
                    color="faturamento",
                    color_continuous_scale=CHART_PALETTE_SEQUENTIAL,
                    text="faturamento",
                )
                fig.update_traces(
                    texttemplate="R$ %{x:,.0f}",
                    textposition="outside",
                )
                fig.update_layout(
                    coloraxis_showscale=False, showlegend=False,
                    margin=dict(t=20, b=20, l=10, r=10),
                    height=max(280, n_clientes * 32),
                    yaxis=dict(autorange="reversed"),
                    plot_bgcolor=COLORS["surface"],
                    paper_bgcolor=COLORS["surface"],
                    xaxis_title="", yaxis_title="",
                    font=dict(family="sans-serif", size=12, color=COLORS["text_primary"]),
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.bar_chart(rank.set_index("cliente")["faturamento"])
        with col2:
            display = rank[["cliente", "faturamento", "participacao_pct", "transacoes", "ticket_medio"]].copy()
            display.columns = ["Cliente", "Faturamento (R$)", "% Total", "Transações", "Ticket Médio"]
            display["Faturamento (R$)"] = display["Faturamento (R$)"].apply(_brl)
            display["% Total"]          = display["% Total"].apply(_pct)
            display["Ticket Médio"]     = display["Ticket Médio"].apply(_brl)
            st.dataframe(display, use_container_width=True, hide_index=True)

    top = rank.iloc[0]
    st.caption(
        f"💡 **{top['cliente']}** lidera com {_brl(top['faturamento'])} "
        f"({top['participacao_pct']:.1f}% do total)."
    )


# ---------------------------------------------------------------------------
# Bloco: Categorias
# ---------------------------------------------------------------------------
def _render_categorias(df: pd.DataFrame) -> None:
    st.subheader("📦 Categorias")
    st.caption("Participação por categoria no faturamento total.")
    cat = participacao_categorias(df)
    if cat.empty:
        st.info("Sem dados para exibir.")
        return

    n_cat = len(cat)

    try:
        import plotly.express as px
        HAS_PLOTLY = True
    except ImportError:
        HAS_PLOTLY = False

    if n_cat <= 4 and HAS_PLOTLY:
        col1, col2 = st.columns([1, 1.6])
        with col1:
            fig = px.pie(
                cat, names="categoria", values="faturamento", hole=0.4,
                color_discrete_sequence=CHART_PALETTE_CATEGORICAL,
            )
            fig.update_traces(
                textposition="outside", textinfo="percent+label",
                textfont_size=12, pull=[0.03] * n_cat,
            )
            fig.update_layout(
                showlegend=False,
                margin=dict(t=20, b=20, l=10, r=10), height=280,
                paper_bgcolor=COLORS["surface"],
                font=dict(family="sans-serif", size=12, color=COLORS["text_primary"]),
            )
            st.plotly_chart(fig, use_container_width=True)
        with col2:
            display = cat[["categoria", "faturamento", "participacao_pct", "itens", "produtos"]].copy()
            display.columns = ["Categoria", "Faturamento (R$)", "% Total", "Itens", "Produtos"]
            display["Faturamento (R$)"] = display["Faturamento (R$)"].apply(_brl)
            display["% Total"]          = display["% Total"].apply(_pct)
            st.dataframe(display, use_container_width=True, hide_index=True)
    else:
        # Barra horizontal — muitas categorias
        col1, col2 = st.columns([1.6, 1])
        with col1:
            if HAS_PLOTLY:
                fig = px.bar(
                    cat, x="faturamento", y="categoria",
                    orientation="h",
                    color="faturamento",
                    color_continuous_scale=CHART_PALETTE_SEQUENTIAL,
                    text="faturamento",
                )
                fig.update_traces(
                    texttemplate="R$ %{x:,.0f}",
                    textposition="outside",
                )
                fig.update_layout(
                    coloraxis_showscale=False, showlegend=False,
                    margin=dict(t=20, b=20, l=10, r=10),
                    height=max(280, n_cat * 32),
                    yaxis=dict(autorange="reversed"),
                    plot_bgcolor=COLORS["surface"],
                    paper_bgcolor=COLORS["surface"],
                    xaxis_title="", yaxis_title="",
                    font=dict(family="sans-serif", size=12, color=COLORS["text_primary"]),
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.bar_chart(cat.set_index("categoria")["faturamento"])
        with col2:
            display = cat[["categoria", "faturamento", "participacao_pct", "itens", "produtos"]].copy()
            display.columns = ["Categoria", "Faturamento (R$)", "% Total", "Itens", "Produtos"]
            display["Faturamento (R$)"] = display["Faturamento (R$)"].apply(_brl)
            display["% Total"]          = display["% Total"].apply(_pct)
            st.dataframe(display, use_container_width=True, hide_index=True)

    top_c = cat.iloc[0]
    st.caption(
        f"💡 **{top_c['categoria']}** é a categoria líder com {_brl(top_c['faturamento'])} "
        f"({top_c['participacao_pct']:.1f}% do total)."
    )


# ---------------------------------------------------------------------------
# Bloco: Produtos
# ---------------------------------------------------------------------------
def _render_produtos(df: pd.DataFrame) -> None:
    st.subheader("🏷️ Produtos")
    st.caption("Ranking por faturamento, análise de Pareto e itens de baixa saída.")

    tab_top, tab_pareto, tab_baixa = st.tabs(["🏆 Top 20", "📊 Pareto", "⚠️ Baixa saída"])

    with tab_top:
        top = ranking_produtos(df, top_n=20)
        if top.empty:
            st.info("Sem dados para exibir.")
        else:
            try:
                import plotly.express as px
                fig = px.bar(
                    top.head(15), x="faturamento", y="produto", orientation="h",
                    color="categoria",
                    color_discrete_sequence=CHART_PALETTE_CATEGORICAL,
                    labels={"faturamento": "Faturamento (R$)", "produto": ""},
                    height=max(280, min(15, len(top)) * 36),
                )
                fig.update_layout(
                    legend_title_text="Categoria",
                    margin=dict(l=10, r=10, t=10, b=10),
                    plot_bgcolor=COLORS["surface"],
                    paper_bgcolor=COLORS["surface"],
                    font=dict(family="sans-serif", size=12, color=COLORS["text_primary"]),
                    yaxis=dict(autorange="reversed"),
                )
                st.plotly_chart(fig, use_container_width=True)
                top1 = top.iloc[0]
                st.caption(f"💡 **{top1['produto']}** lidera com {_brl(top1['faturamento'])} ({top1['participacao_pct']:.1f}% do total).")
            except ImportError:
                pass

        display = top[["produto", "categoria", "faturamento", "participacao_pct", "itens", "n_clientes", "preco_medio"]].copy()
        display.columns = ["Produto", "Categoria", "Faturamento (R$)", "% Total", "Itens", "# Clientes", "Preço Médio"]
        display["Faturamento (R$)"] = display["Faturamento (R$)"].apply(_brl)
        display["% Total"]          = display["% Total"].apply(_pct)
        display["Preço Médio"]      = display["Preço Médio"].apply(_brl)
        st.dataframe(display, use_container_width=True, hide_index=True)

    with tab_pareto:
        pareto = pareto_produtos(df)
        col1, col2, col3 = st.columns(3)
        col1.metric("Produtos que geram 80% do fat.", str(pareto["n_pareto_80"]))
        col2.metric("Total de produtos", str(pareto["total_produtos"]))
        col3.metric("% do catálogo", _pct(pareto["pct_catalogo"]))
        st.info(
            f"**Regra 80/20:** apenas {pareto['n_pareto_80']} produtos "
            f"({pareto['pct_catalogo']}% do catálogo) geram 80% do faturamento."
        )

    with tab_baixa:
        baixa = produtos_baixa_saida(df, max_vendas=1)
        st.metric("Produtos com ≤ 1 venda", len(baixa))
        if not baixa.empty:
            st.dataframe(
                baixa[["produto", "categoria", "itens", "faturamento"]].rename(
                    columns={"produto": "Produto", "categoria": "Categoria",
                             "itens": "Itens vendidos", "faturamento": "Faturamento (R$)"}
                ),
                use_container_width=True, hide_index=True,
            )


# ---------------------------------------------------------------------------
# Bloco: Temporal
# ---------------------------------------------------------------------------
def _render_temporal(df: pd.DataFrame) -> None:
    st.subheader("📅 Análise Temporal")
    st.caption("Faturamento diário, por dia da semana, hora, heatmap e período do dia.")

    tab_diario, tab_semana, tab_hora, tab_heatmap, tab_periodo = st.tabs(
        ["📅 Diário", "📆 Semana", "🕐 Hora", "🌡️ Heatmap", "🌤️ Período"]
    )

    try:
        import plotly.express as px
        import plotly.graph_objects as go
        HAS_PLOTLY = True
    except ImportError:
        HAS_PLOTLY = False

    with tab_diario:
        dia = faturamento_por_dia(df)
        if dia.empty:
            st.info("Sem dados.")
        elif HAS_PLOTLY:
            fig = px.bar(
                dia, x="data", y="faturamento", color="dia_semana",
                labels={"faturamento": "Faturamento (R$)", "data": "Data"},
                color_discrete_sequence=CHART_PALETTE_CATEGORICAL,
                height=350,
            )
            fig.update_layout(
                legend_title_text="Dia",
                margin=dict(t=10, b=10),
                plot_bgcolor=COLORS["surface"],
                paper_bgcolor=COLORS["surface"],
                font=dict(family="sans-serif", size=12, color=COLORS["text_primary"]),
            )
            st.plotly_chart(fig, use_container_width=True)
            melhor = dia.loc[dia["faturamento"].idxmax()]
            st.caption(f"💡 Melhor dia: **{melhor['data']}** ({melhor.get('dia_semana','')}) — {_brl(melhor['faturamento'])}")
        else:
            st.bar_chart(dia.set_index("data")["faturamento"])

    with tab_semana:
        sem = faturamento_por_dia_semana(df)
        if sem.empty:
            st.info("Sem dados.")
        elif HAS_PLOTLY:
            fig = px.bar(
                sem, x="dia_semana", y="faturamento",
                labels={"faturamento": "Faturamento (R$)", "dia_semana": ""},
                color="faturamento", color_continuous_scale=CHART_PALETTE_SEQUENTIAL,
                height=350,
            )
            fig.update_layout(
                coloraxis_showscale=False, margin=dict(t=10, b=10),
                plot_bgcolor=COLORS["surface"], paper_bgcolor=COLORS["surface"],
                font=dict(family="sans-serif", size=12, color=COLORS["text_primary"]),
            )
            st.plotly_chart(fig, use_container_width=True)
            top_dia = sem.loc[sem["faturamento"].idxmax()]
            st.caption(f"💡 Dia mais forte da semana: **{top_dia['dia_semana']}** — {_brl(top_dia['faturamento'])}")
        else:
            st.bar_chart(sem.set_index("dia_semana")["faturamento"])

    with tab_hora:
        hora = faturamento_por_hora(df)
        if hora.empty:
            st.info("Sem dados.")
        elif HAS_PLOTLY:
            fig = px.line(
                hora, x="hora", y="faturamento", markers=True,
                labels={"faturamento": "Faturamento (R$)", "hora": "Hora"},
                height=350,
                color_discrete_sequence=[COLORS["primary"]],
            )
            fig.update_layout(
                margin=dict(t=10, b=10),
                plot_bgcolor=COLORS["surface"], paper_bgcolor=COLORS["surface"],
                font=dict(family="sans-serif", size=12, color=COLORS["text_primary"]),
            )
            st.plotly_chart(fig, use_container_width=True)
            top_h = hora.loc[hora["faturamento"].idxmax()]
            st.caption(f"💡 Pico de faturamento: **{int(top_h['hora'])}h** — {_brl(top_h['faturamento'])}")
        else:
            st.line_chart(hora.set_index("hora")["faturamento"])

    with tab_heatmap:
        pivot = heatmap_hora_dia(df)
        if HAS_PLOTLY and not pivot.empty:
            fig = go.Figure(data=go.Heatmap(
                z=pivot.values, x=pivot.columns.tolist(), y=pivot.index.tolist(),
                colorscale=CHART_PALETTE_SEQUENTIAL, colorbar=dict(title="R$"),
            ))
            fig.update_layout(
                xaxis_title="Dia da Semana", yaxis_title="Hora",
                height=500, margin=dict(t=10, b=10),
                paper_bgcolor=COLORS["surface"],
                font=dict(family="sans-serif", size=12, color=COLORS["text_primary"]),
            )
            st.plotly_chart(fig, use_container_width=True)
            st.caption("💡 Células mais escuras = maior concentração de faturamento naquele horário e dia.")
        else:
            st.dataframe(pivot, use_container_width=True)

    with tab_periodo:
        per = faturamento_por_periodo(df)
        if per.empty:
            st.info("Sem dados.")
        else:
            n_per = len(per)
            col1, col2 = st.columns([1, 1])
            with col1:
                st.dataframe(
                    per.rename(columns={
                        "periodo": "Período", "faturamento": "Faturamento (R$)",
                        "transacoes": "Transações", "participacao_pct": "% Total",
                    }),
                    use_container_width=True, hide_index=True,
                )
            with col2:
                if HAS_PLOTLY:
                    if n_per <= 4:
                        fig = px.pie(
                            per, names="periodo", values="faturamento", hole=0.4,
                            color_discrete_sequence=CHART_PALETTE_CATEGORICAL,
                            height=280,
                        )
                        fig.update_traces(
                            textposition="outside", textinfo="percent+label",
                            textfont_size=12, pull=[0.03] * n_per,
                        )
                        fig.update_layout(
                            showlegend=False,
                            margin=dict(t=20, b=20, l=10, r=10),
                            paper_bgcolor=COLORS["surface"],
                            font=dict(family="sans-serif", size=12, color=COLORS["text_primary"]),
                        )
                    else:
                        fig = px.bar(
                            per, x="faturamento", y="periodo", orientation="h",
                            color="faturamento", color_continuous_scale=CHART_PALETTE_SEQUENTIAL,
                            text="faturamento", height=max(280, n_per * 40),
                        )
                        fig.update_traces(texttemplate="R$ %{x:,.0f}", textposition="outside")
                        fig.update_layout(
                            coloraxis_showscale=False, showlegend=False,
                            margin=dict(t=20, b=20, l=10, r=10),
                            plot_bgcolor=COLORS["surface"], paper_bgcolor=COLORS["surface"],
                            xaxis_title="", yaxis_title="",
                        )
                    st.plotly_chart(fig, use_container_width=True)
            top_per = per.iloc[0]
            st.caption(f"💡 Período mais forte: **{top_per['periodo']}** — {_brl(top_per['faturamento'])} ({top_per['participacao_pct']:.1f}%)")


# ---------------------------------------------------------------------------
# Bloco: Pagamentos
# ---------------------------------------------------------------------------
def _render_pagamentos(df: pd.DataFrame) -> None:
    st.subheader("💳 Pagamentos")
    st.caption("Distribuição por método e bandeira de cartão.")

    try:
        import plotly.express as px
        HAS_PLOTLY = True
    except ImportError:
        HAS_PLOTLY = False

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Por método**")
        pgto = metricas_pagamento(df)
        if not pgto.empty and HAS_PLOTLY:
            n_met = len(pgto)
            if n_met <= 4:
                fig = px.pie(
                    pgto, names="metodo_pagamento", values="faturamento", hole=0.4,
                    color_discrete_sequence=CHART_PALETTE_CATEGORICAL,
                )
                fig.update_traces(
                    textposition="outside", textinfo="percent+label",
                    textfont_size=12, pull=[0.03] * n_met,
                )
                fig.update_layout(
                    showlegend=False,
                    margin=dict(t=20, b=20, l=10, r=10), height=280,
                    paper_bgcolor=COLORS["surface"],
                    font=dict(family="sans-serif", size=12, color=COLORS["text_primary"]),
                )
            else:
                fig = px.bar(
                    pgto, x="faturamento", y="metodo_pagamento", orientation="h",
                    color="faturamento", color_continuous_scale=CHART_PALETTE_SEQUENTIAL,
                    text="faturamento",
                )
                fig.update_traces(texttemplate="R$ %{x:,.0f}", textposition="outside")
                fig.update_layout(
                    coloraxis_showscale=False, showlegend=False,
                    margin=dict(t=20, b=20, l=10, r=10),
                    height=max(280, n_met * 40),
                    plot_bgcolor=COLORS["surface"], paper_bgcolor=COLORS["surface"],
                    xaxis_title="", yaxis_title="",
                )
            st.plotly_chart(fig, use_container_width=True)

        display = pgto[["metodo_pagamento","faturamento","participacao_pct","transacoes","ticket_medio"]].copy()
        display.columns = ["Método","Faturamento (R$)","% Total","Transações","Ticket Médio"]
        display["Faturamento (R$)"] = display["Faturamento (R$)"].apply(_brl)
        display["% Total"]          = display["% Total"].apply(_pct)
        display["Ticket Médio"]     = display["Ticket Médio"].apply(_brl)
        st.dataframe(display, use_container_width=True, hide_index=True)

        if not pgto.empty:
            top_pgto = pgto.iloc[0]
            st.caption(
                f"💡 **{top_pgto['metodo_pagamento']}** é o método predominante "
                f"({top_pgto['participacao_pct']:.1f}% do faturamento)."
            )

    with col2:
        st.markdown("**Por bandeira de cartão**")
        band = metricas_bandeira(df)
        if band.empty:
            st.info("Nenhuma transação com cartão no período selecionado.")
        else:
            n_band = len(band)
            if HAS_PLOTLY:
                if n_band <= 4:
                    fig = px.pie(
                        band, names="bandeira", values="faturamento", hole=0.4,
                        color_discrete_sequence=CHART_PALETTE_CATEGORICAL,
                    )
                    fig.update_traces(
                        textposition="outside", textinfo="percent+label",
                        textfont_size=12, pull=[0.03] * n_band,
                    )
                    fig.update_layout(
                        showlegend=False,
                        margin=dict(t=20, b=20, l=10, r=10), height=280,
                        paper_bgcolor=COLORS["surface"],
                        font=dict(family="sans-serif", size=12, color=COLORS["text_primary"]),
                    )
                else:
                    fig = px.bar(
                        band, x="faturamento", y="bandeira", orientation="h",
                        color="faturamento", color_continuous_scale=CHART_PALETTE_SEQUENTIAL,
                        text="faturamento",
                    )
                    fig.update_traces(texttemplate="R$ %{x:,.0f}", textposition="outside")
                    fig.update_layout(
                        coloraxis_showscale=False, showlegend=False,
                        margin=dict(t=20, b=20, l=10, r=10),
                        height=max(280, n_band * 40),
                        plot_bgcolor=COLORS["surface"], paper_bgcolor=COLORS["surface"],
                        xaxis_title="", yaxis_title="",
                    )
                st.plotly_chart(fig, use_container_width=True)

            display = band[["bandeira","faturamento","participacao_pct","transacoes"]].copy()
            display.columns = ["Bandeira","Faturamento (R$)","% Cartões","Transações"]
            display["Faturamento (R$)"] = display["Faturamento (R$)"].apply(_brl)
            display["% Cartões"]        = display["% Cartões"].apply(_pct)
            st.dataframe(display, use_container_width=True, hide_index=True)


# ---------------------------------------------------------------------------
# Bloco: Comparativos
# ---------------------------------------------------------------------------
def _render_comparativos(df: pd.DataFrame) -> None:
    st.markdown("### 🔀 Análise Comparativa")
    tab_cli, tab_cat, tab_per = st.tabs(["Clientes", "Categorias", "Períodos"])

    try:
        import plotly.express as px
        HAS_PLOTLY = True
    except ImportError:
        HAS_PLOTLY = False

    with tab_cli:
        st.markdown("**Faturamento, transações e ticket médio por cliente**")
        rank = ranking_clientes(df)
        if HAS_PLOTLY:
            fig = px.bar(
                rank, x="cliente", y="faturamento",
                color="cliente", text="participacao_pct",
                labels={"faturamento": "Faturamento (R$)", "cliente": ""},
                height=320,
            )
            fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
            fig.update_layout(showlegend=False, margin=dict(t=10, b=10))
            st.plotly_chart(fig, use_container_width=True)

        # Comparativo de dois clientes
        clientes_disp = sorted(df["cliente"].unique().tolist())
        if len(clientes_disp) >= 2:
            col1, col2 = st.columns(2)
            cli_a = col1.selectbox("Cliente A", clientes_disp, index=0, key="cmp_cli_a")
            cli_b = col2.selectbox("Cliente B", clientes_disp, index=1, key="cmp_cli_b")

            if cli_a != cli_b:
                df_a = df[df["cliente"] == cli_a]
                df_b = df[df["cliente"] == cli_b]
                kpi_a = kpis_gerais(df_a)
                kpi_b = kpis_gerais(df_b)

                st.markdown("---")
                cols = st.columns(4)
                metricas = [
                    ("Faturamento",  _brl(kpi_a["faturamento"]),  _brl(kpi_b["faturamento"])),
                    ("Transações",   f'{kpi_a["n_transacoes"]:,}',f'{kpi_b["n_transacoes"]:,}'),
                    ("Produtos",     str(kpi_a["n_produtos"]),    str(kpi_b["n_produtos"])),
                    ("Ticket Médio", _brl(kpi_a["ticket_medio"]), _brl(kpi_b["ticket_medio"])),
                ]
                for i, (label, val_a, val_b) in enumerate(metricas):
                    with cols[i]:
                        st.markdown(f"**{label}**")
                        st.markdown(f"`{cli_a}` → {val_a}")
                        st.markdown(f"`{cli_b}` → {val_b}")

    with tab_cat:
        st.markdown("**Faturamento por categoria**")
        cat = participacao_categorias(df)
        if HAS_PLOTLY:
            fig = px.bar(
                cat, x="categoria", y="faturamento",
                color="categoria", text="participacao_pct",
                labels={"faturamento": "Faturamento (R$)", "categoria": ""},
                height=320,
            )
            fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
            fig.update_layout(showlegend=False, margin=dict(t=10, b=10))
            st.plotly_chart(fig, use_container_width=True)

        # Comparativo de duas categorias
        cats_disp = sorted(df["categoria"].unique().tolist())
        if len(cats_disp) >= 2:
            col1, col2 = st.columns(2)
            cat_a = col1.selectbox("Categoria A", cats_disp, index=0, key="cmp_cat_a")
            cat_b = col2.selectbox("Categoria B", cats_disp, index=1, key="cmp_cat_b")

            if cat_a != cat_b:
                df_ca = df[df["categoria"] == cat_a]
                df_cb = df[df["categoria"] == cat_b]
                cols = st.columns(3)
                with cols[0]:
                    st.markdown(f"**{cat_a}**")
                    st.metric("Faturamento", _brl(df_ca["valor_total"].sum()))
                    st.metric("Produtos",    str(df_ca["produto"].nunique()))
                with cols[1]:
                    st.markdown("&nbsp;", unsafe_allow_html=True)
                    st.markdown("<div style='text-align:center; font-size:2rem; padding-top:1rem;'>vs</div>",
                                unsafe_allow_html=True)
                with cols[2]:
                    st.markdown(f"**{cat_b}**")
                    st.metric("Faturamento", _brl(df_cb["valor_total"].sum()))
                    st.metric("Produtos",    str(df_cb["produto"].nunique()))

    with tab_per:
        st.markdown("**Faturamento por período do dia e dia da semana**")
        per  = faturamento_por_periodo(df)
        sem  = faturamento_por_dia_semana(df)

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Período do dia**")
            if HAS_PLOTLY:
                fig = px.bar(
                    per, x="periodo", y="faturamento", color="periodo",
                    text="participacao_pct",
                    labels={"faturamento": "R$", "periodo": ""},
                    color_discrete_sequence=["#1a237e","#1565c0","#1e88e5","#64b5f6"],
                    height=280,
                )
                fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
                fig.update_layout(showlegend=False, margin=dict(t=10, b=10))
                st.plotly_chart(fig, use_container_width=True)

        with col2:
            st.markdown("**Dia da semana**")
            if HAS_PLOTLY:
                fig = px.bar(
                    sem, x="dia_semana", y="faturamento",
                    color="faturamento", color_continuous_scale="Blues",
                    labels={"faturamento": "R$", "dia_semana": ""},
                    height=280,
                )
                fig.update_layout(coloraxis_showscale=False, margin=dict(t=10, b=10))
                st.plotly_chart(fig, use_container_width=True)


# ---------------------------------------------------------------------------
# Bloco: Inteligência
# ---------------------------------------------------------------------------
def _render_inteligencia(df: pd.DataFrame) -> None:
    st.subheader("🧠 Inteligência Analítica")
    st.caption(
        "Padrões de horário & dia da semana  ·  "
        "Detecção de anomalias  ·  "
        "Tendência de receita  ·  "
        "Previsão 7 dias com intervalo de confiança"
    )

    n_dias = df["data"].nunique() if not df.empty else 0
    if n_dias < 2:
        st.info("Base insuficiente para análise de inteligência (mínimo 2 dias).")
        return

    tab_tend, tab_pad, tab_anom, tab_prev = st.tabs([
        "📈 Tendência", "🕐 Padrões", "🚨 Anomalias", "🔮 Previsão"
    ])

    try:
        import plotly.express as px
        import plotly.graph_objects as go
        HAS_PLOTLY = True
    except ImportError:
        HAS_PLOTLY = False

    # --- Tab 1: Tendência ---
    with tab_tend:
        trend = get_revenue_trend(df)
        icons = {"subindo": "📈", "caindo": "📉", "estavel": "➡️"}
        icon  = icons.get(trend["direction"], "➡️")
        cor   = {"subindo": "#21c354", "caindo": "#ff4b4b", "estavel": "#ffa500"}
        bg    = {"subindo": "#f0fdf4", "caindo": "#fff1f2", "estavel": "#fffbeb"}
        bord  = {"subindo": "#86efac", "caindo": "#fca5a5", "estavel": "#fde68a"}
        c_dir = cor.get(trend["direction"], "#888")
        c_bg  = bg.get(trend["direction"], "#f8fafc")
        c_bd  = bord.get(trend["direction"], "#e2e8f0")

        label_dir = {"subindo": "Receita em crescimento", "caindo": "Receita em queda", "estavel": "Receita estável"}
        slope_fmt = f"R$ {trend['slope_diario']:+,.2f}/dia".replace(",", "X").replace(".", ",").replace("X", ".")
        st.info(
            f"{icon} **{label_dir.get(trend['direction'], trend['direction'].title())}** — "
            f"Slope: {slope_fmt} · Variação no período: {trend['pct_variacao']:+.1f}%"
        )

        c1, c2, c3 = st.columns(3)
        c1.metric("Tendência", f"{icon} {trend['direction'].title()}")
        c2.metric("Slope diário", f"R$ {trend['slope_diario']:+,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        c3.metric("Var. período", f"{trend['pct_variacao']:+.1f}%")

        serie = trend["serie"]
        if not serie.empty and HAS_PLOTLY:
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=serie["data"].astype(str), y=serie["faturamento"],
                name="Faturamento diário", marker_color="#1565c0", opacity=0.7,
            ))
            fig.add_trace(go.Scatter(
                x=serie["data"].astype(str), y=serie["media_movel_3d"],
                name="Média móvel 3d", line=dict(color=c_dir, width=2.5, dash="dash"),
            ))
            fig.update_layout(
                height=360, showlegend=True,
                legend=dict(orientation="h", y=1.08),
                margin=dict(t=10, b=10),
                yaxis_title="Faturamento (R$)",
                plot_bgcolor="#f8fafc",
                paper_bgcolor="#f8fafc",
            )
            st.plotly_chart(fig, use_container_width=True)
        elif not serie.empty:
            st.line_chart(serie.set_index("data")[["faturamento", "media_movel_3d"]])

    # --- Tab 2: Padrões ---
    with tab_pad:
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Faturamento por hora do dia**")
            hour = get_hour_pattern(df)
            if not hour.empty and HAS_PLOTLY:
                fig = px.bar(
                    hour, x="hora", y="faturamento",
                    color="participacao_pct", color_continuous_scale="Blues",
                    labels={"faturamento": "R$", "hora": "Hora", "participacao_pct": "%"},
                    text=hour["participacao_pct"].apply(lambda v: f"{v:.1f}%"),
                    height=300,
                )
                fig.update_traces(textposition="outside")
                fig.update_layout(coloraxis_showscale=False, margin=dict(t=10, b=10))
                st.plotly_chart(fig, use_container_width=True)
            elif not hour.empty:
                st.bar_chart(hour.set_index("hora")["faturamento"])

            top3_h = hour.nsmallest(3, "rank")
            if not top3_h.empty:
                horas_str = ", ".join(f"{int(h)}h" for h in top3_h["hora"])
                st.caption(f"🕐 Horários mais fortes: **{horas_str}**")

        with col2:
            st.markdown("**Faturamento por dia da semana**")
            weekday = get_weekday_pattern(df)
            if not weekday.empty and HAS_PLOTLY:
                fig = px.bar(
                    weekday, x="dia_semana", y="faturamento",
                    color="participacao_pct", color_continuous_scale="Greens",
                    labels={"faturamento": "R$", "dia_semana": "", "participacao_pct": "%"},
                    text=weekday["participacao_pct"].apply(lambda v: f"{v:.1f}%"),
                    height=300,
                )
                fig.update_traces(textposition="outside")
                fig.update_layout(coloraxis_showscale=False, margin=dict(t=10, b=10))
                st.plotly_chart(fig, use_container_width=True)
            elif not weekday.empty:
                st.bar_chart(weekday.set_index("dia_semana")["faturamento"])

            top1_d = weekday[weekday["rank"] == 1]
            if not top1_d.empty:
                st.caption(f"📅 Dia mais forte: **{top1_d.iloc[0]['dia_semana'].title()}**")

    # --- Tab 3: Anomalias ---
    with tab_anom:
        if n_dias < 3:
            st.info("Mínimo de 3 dias para detecção de anomalias.")
        else:
            anomalias = detect_anomalies(df)
            if not anomalias:
                st.success(f"Nenhum dia anômalo detectado nos {n_dias} dias analisados.")
            else:
                st.markdown(f"**{len(anomalias)} dia(s) com comportamento fora do padrão:**")
                for a in anomalias:
                    fat_brl = _brl(a["faturamento"])
                    esp_brl = _brl(a["esperado"])
                    if a["tipo"] == "queda":
                        st.error(
                            f"📉 **{a['data']}** — {fat_brl} "
                            f"(esperado: {esp_brl}, z={a['zscore']:+.1f}) → **queda**"
                        )
                    else:
                        st.warning(
                            f"📈 **{a['data']}** — {fat_brl} "
                            f"(esperado: {esp_brl}, z={a['zscore']:+.1f}) → **pico**"
                        )

            if HAS_PLOTLY:
                daily = df.groupby("data")["valor_total"].sum().reset_index()
                daily["data"] = daily["data"].astype(str)
                anom_datas = {str(a["data"]) for a in anomalias}
                daily["is_anomalia"] = daily["data"].isin(anom_datas)
                fig = go.Figure()
                fig.add_trace(go.Bar(
                    x=daily["data"], y=daily["valor_total"],
                    marker_color=["#ff4b4b" if a else "#1565c0" for a in daily["is_anomalia"]],
                    name="Faturamento",
                ))
                if daily["valor_total"].std() > 0:
                    mean_val = daily["valor_total"].mean()
                    std_val  = daily["valor_total"].std()
                    fig.add_hline(y=mean_val, line_dash="dash", line_color="green",
                                  annotation_text="Média")
                    fig.add_hline(y=mean_val + 2 * std_val, line_dash="dot",
                                  line_color="orange", annotation_text="+2σ")
                    fig.add_hline(y=max(0, mean_val - 2 * std_val), line_dash="dot",
                                  line_color="orange", annotation_text="-2σ")
                fig.update_layout(height=300, showlegend=False, margin=dict(t=10, b=10))
                st.plotly_chart(fig, use_container_width=True)

    # --- Tab 4: Previsão ---
    with tab_prev:
        fc = forecast_next_days(df, days=7)
        if fc["previsao"].empty:
            st.warning("Dados insuficientes para previsão (mínimo 3 dias).")
        else:
            total_prev = fc["previsao"]["faturamento_previsto"].sum()
            st.info(
                f"🔮 **Projeção 7 dias: {_brl(total_prev)}** — "
                f"Média {_brl(fc['media_diaria'])}/dia · "
                f"Slope {fc['slope_diario']:+.2f} R$/dia  \n"
                f"⚠️ {fc['aviso']}"
            )
            c1, c2, c3 = st.columns(3)
            c1.metric("Previsão 7 dias", _brl(total_prev))
            c2.metric("Média diária prevista", _brl(fc["media_diaria"]))
            c3.metric("Tendência base",
                      f"R$ {fc['slope_diario']:+,.2f}/dia".replace(",", "X").replace(".", ",").replace("X", "."))

            if HAS_PLOTLY:
                # Histórico + previsão no mesmo gráfico
                hist = df.groupby("data")["valor_total"].sum().reset_index()
                hist.columns = ["data", "faturamento"]
                hist["data"] = hist["data"].astype(str)

                prev_df = fc["previsao"].copy()
                prev_df["data_prevista"] = prev_df["data_prevista"].astype(str)

                fig = go.Figure()
                fig.add_trace(go.Bar(
                    x=hist["data"], y=hist["faturamento"],
                    name="Histórico", marker_color="#1565c0", opacity=0.8,
                ))
                fig.add_trace(go.Scatter(
                    x=prev_df["data_prevista"], y=prev_df["faturamento_previsto"],
                    name="Previsão", line=dict(color="#ffa500", width=2.5, dash="dash"),
                    mode="lines+markers",
                ))
                fig.add_trace(go.Scatter(
                    x=prev_df["data_prevista"].tolist() + prev_df["data_prevista"].tolist()[::-1],
                    y=prev_df["limite_superior"].tolist() + prev_df["limite_inferior"].tolist()[::-1],
                    fill="toself", fillcolor="rgba(255,165,0,0.15)",
                    line=dict(color="rgba(0,0,0,0)"), name="IC 87%", showlegend=True,
                ))
                fig.update_layout(
                    height=420,
                    title=dict(
                        text="Histórico real + projeção com intervalo de confiança (~87%)",
                        font=dict(size=13, color="#64748b"),
                        x=0,
                    ),
                    showlegend=True,
                    legend=dict(orientation="h", y=1.08),
                    margin=dict(t=40, b=10),
                    yaxis_title="Faturamento (R$)",
                    plot_bgcolor="#f8fafc",
                    paper_bgcolor="#f8fafc",
                )
                st.plotly_chart(fig, use_container_width=True)

            st.caption("📋 Tabela de projeção — valores estimados com base na regressão linear dos dias históricos")
            st.dataframe(
                fc["previsao"].rename(columns={
                    "data_prevista":        "Data",
                    "faturamento_previsto": "Previsto (R$)",
                    "limite_inferior":      "Limite Inf. (R$)",
                    "limite_superior":      "Limite Sup. (R$)",
                }),
                use_container_width=True, hide_index=True,
            )


# ---------------------------------------------------------------------------
# Bloco: Financeiro
# ---------------------------------------------------------------------------
def _render_financeiro(df: pd.DataFrame) -> None:
    st.markdown("### 💰 Análise Financeira")

    cobertura = get_cobertura_custo(df)

    if cobertura == 0:
        st.warning(
            "**Analise financeira indisponivel** — nenhum produto com custo cadastrado.  \n"
            "Preencha `app/data/custos.xlsx` com as colunas `produto_id` e `custo_unitario`."
        )
        return

    if cobertura < 100:
        st.warning(
            f"**Analise financeira parcial** — {cobertura:.1f}% dos produtos possuem custo cadastrado.  \n"
            "Metricas abaixo refletem apenas os produtos com custo disponivel."
        )
    else:
        st.success(f"Cobertura de custo: {cobertura:.1f}% — analise financeira completa.")

    lucro_total  = get_total_profit(df)
    margem_media = get_margin(df)

    c1, c2, c3 = st.columns(3)
    c1.metric(
        "💰 Lucro Total",
        _brl(lucro_total) if lucro_total is not None else "N/D",
    )
    c2.metric(
        "📊 Margem Media",
        _pct(margem_media) if margem_media is not None else "N/D",
    )
    c3.metric("🧾 Cobertura Custo", _pct(cobertura))

    tab_prod, tab_uni, tab_sim = st.tabs(["Por Produto", "Por Unidade", "Simulacoes"])

    with tab_prod:
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Top 10 — Maior Lucro**")
            top = get_top_profit_products(df, n=10)
            if not top.empty:
                try:
                    import plotly.express as px
                    fig = px.bar(
                        top.head(10), x="lucro", y="produto", orientation="h",
                        color="margem_pct", color_continuous_scale="Greens",
                        labels={"lucro": "Lucro (R$)", "produto": "", "margem_pct": "Margem %"},
                        height=320,
                    )
                    fig.update_layout(margin=dict(t=10, b=10, l=10, r=10))
                    st.plotly_chart(fig, use_container_width=True)
                except ImportError:
                    pass
                d = top[["produto", "faturamento", "lucro", "margem_pct"]].copy()
                d.columns = ["Produto", "Faturamento", "Lucro", "Margem"]
                d["Faturamento"] = d["Faturamento"].apply(_brl)
                d["Lucro"]       = d["Lucro"].apply(_brl)
                d["Margem"]      = d["Margem"].apply(_pct)
                st.dataframe(d, use_container_width=True, hide_index=True)

        with col2:
            st.markdown("**Bottom 5 — Menor Lucro (prejuizo)**")
            worst = get_worst_profit_products(df, n=5)
            if not worst.empty:
                try:
                    import plotly.express as px
                    fig = px.bar(
                        worst, x="lucro", y="produto", orientation="h",
                        color="margem_pct", color_continuous_scale="Reds_r",
                        labels={"lucro": "Lucro (R$)", "produto": "", "margem_pct": "Margem %"},
                        height=220,
                    )
                    fig.add_vline(x=0, line_dash="dash", line_color="gray")
                    fig.update_layout(margin=dict(t=10, b=10, l=10, r=10))
                    st.plotly_chart(fig, use_container_width=True)
                except ImportError:
                    pass
                d = worst[["produto", "faturamento", "lucro", "margem_pct"]].copy()
                d.columns = ["Produto", "Faturamento", "Lucro", "Margem"]
                d["Faturamento"] = d["Faturamento"].apply(_brl)
                d["Lucro"]       = d["Lucro"].apply(_brl)
                d["Margem"]      = d["Margem"].apply(_pct)
                st.dataframe(d, use_container_width=True, hide_index=True)

    with tab_uni:
        unit_profit = get_profit_by_unit(df)
        if unit_profit.empty:
            st.info("Sem dados financeiros para as unidades no periodo selecionado.")
        else:
            try:
                import plotly.express as px
                fig = px.bar(
                    unit_profit, x="cliente", y="lucro",
                    color="margem_pct", color_continuous_scale="RdYlGn",
                    labels={"lucro": "Lucro (R$)", "cliente": "", "margem_pct": "Margem %"},
                    text=[f"{v:.1f}%" for v in unit_profit["margem_pct"]],
                    height=320,
                )
                fig.add_hline(y=0, line_dash="dash", line_color="red", line_width=1)
                fig.update_traces(textposition="outside")
                fig.update_layout(margin=dict(t=10, b=10))
                st.plotly_chart(fig, use_container_width=True)
            except ImportError:
                pass
            d = unit_profit[["cliente", "faturamento", "custo_total", "lucro", "margem_pct"]].copy()
            d.columns = ["Unidade", "Faturamento", "Custo Total", "Lucro", "Margem"]
            for col in ["Faturamento", "Custo Total", "Lucro"]:
                d[col] = d[col].apply(_brl)
            d["Margem"] = d["Margem"].apply(_pct)
            st.dataframe(d, use_container_width=True, hide_index=True)

    with tab_sim:
        produtos_com_custo = (
            df.dropna(subset=["custo_unitario_real"])["produto"].unique().tolist()
            if "custo_unitario_real" in df.columns else []
        )
        if not produtos_com_custo:
            st.info("Nenhum produto com custo cadastrado para simular.")
        else:
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**Simular ajuste de preco**")
                prod_preco = st.selectbox("Produto", produtos_com_custo, key="fin_sim_prod_preco")
                aumento    = st.slider("Variacao de preco (%)", -30, 50, 10, key="fin_sim_aumento")
                res_preco  = simular_ajuste_preco(df, prod_preco, aumento_pct=float(aumento))
                _render_sim_result(res_preco)
            with col2:
                st.markdown("**Simular reducao de custo**")
                prod_custo = st.selectbox("Produto", produtos_com_custo, key="fin_sim_prod_custo")
                reducao    = st.slider("Reducao de custo (%)", 1, 50, 10, key="fin_sim_reducao")
                res_custo  = simular_reducao_custo(df, prod_custo, reducao_pct=float(reducao))
                _render_sim_result(res_custo)


# ---------------------------------------------------------------------------
# Bloco: Exportação
# ---------------------------------------------------------------------------
def _render_exportacao(df: pd.DataFrame) -> None:
    st.markdown("### 💾 Exportar Dados")
    col1, col2, col3 = st.columns(3)

    with col1:
        csv_data = export_filtered_csv(df)
        st.download_button(
            label="⬇️ Baixar CSV",
            data=csv_data,
            file_name=csv_filename(),
            mime="text/csv",
            use_container_width=True,
        )

    with col2:
        xlsx_data = export_filtered_excel(df)
        st.download_button(
            label="⬇️ Baixar Excel",
            data=xlsx_data,
            file_name=excel_filename(),
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )

    with col3:
        n = len(df)
        fat = df["valor_total"].sum()
        st.info(f"**{n:,}** linhas · **{_brl(fat)}** no período filtrado")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def render() -> None:
    require_login()

    df_full = load_data()
    df      = _render_filtros(df_full)

    st.title("📊 Dashboard Analítico — Mercadinhos")

    # ── [1] CONTEXTO ────────────────────────────────────────────────────────
    n_filtrado = len(df)
    n_total    = len(df_full)
    n_dias     = df["data"].nunique() if not df.empty else 0

    if n_filtrado < n_total:
        st.caption(
            f"🔍 Filtro ativo · {n_filtrado:,} de {n_total:,} transações · {n_dias} dia(s) selecionado(s)."
        )
    else:
        st.caption(f"📋 Base completa · {n_total:,} transações · {n_dias} dia(s).")

    if df.empty:
        st.warning("Nenhum dado encontrado para os filtros selecionados.")
        return

    if n_dias < SMALL_BASE_THRESHOLD_DAYS:
        st.warning(
            f"**Base de análise: {n_dias} dia(s)**  \n"
            "✅ **Operacional:** confiável.  "
            "⚠️ **Estratégico:** limitado — menos de 15 dias pode não capturar sazonalidade."
        )

    # ── [2] HEADLINE — KPIs ─────────────────────────────────────────────────
    kpis = _render_kpis(df)
    st.markdown("---")

    # ── [3] DIAGNÓSTICO — Inteligência ──────────────────────────────────────
    _render_inteligencia(df)
    st.markdown("---")

    # ── [4] ALERTAS ─────────────────────────────────────────────────────────
    alertas = _render_alertas(df)
    st.markdown("---")

    # ── [5] OPORTUNIDADES — Recomendações ───────────────────────────────────
    with st.expander("📌 Recomendações do Sistema", expanded=True):
        _render_recomendacoes(df, kpis, alertas)
    st.markdown("---")

    # ── [6] DETALHE — Clientes / Categorias / Produtos / Temporal / Pgtos ──
    _render_clientes(df)
    st.markdown("---")
    _render_categorias(df)
    st.markdown("---")
    _render_produtos(df)
    st.markdown("---")
    _render_temporal(df)
    st.markdown("---")
    _render_pagamentos(df)
    st.markdown("---")

    # Financeiro (depende de custo cadastrado — detalhe complementar)
    with st.expander("💰 Análise Financeira", expanded=get_cobertura_custo(df) > 0):
        _render_financeiro(df)
    st.markdown("---")

    # ── [7] AÇÃO — Simulações / Comparativos / Exportação ───────────────────
    with st.expander("🧮 Simulações Financeiras", expanded=False):
        _render_simulacoes(df)
    st.markdown("---")

    with st.expander("🔀 Comparativos", expanded=False):
        _render_comparativos(df)
    st.markdown("---")

    _render_exportacao(df)


# Executado apenas quando o Streamlit roda este arquivo diretamente como página nativa.
# Quando importado por main.py, __name__ != "__main__" e render() NÃO é chamado aqui.
if __name__ == "__main__":
    render()
