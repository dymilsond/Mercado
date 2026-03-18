"""Página de Abastecimento — consumo por cliente/produto no período selecionado."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import streamlit as st

from domain.design_tokens import CHART_PALETTE_CATEGORICAL, COLORS
from services.data_loader import load_data

try:
    import plotly.express as px
    import plotly.graph_objects as go
    HAS_PLOTLY = True
except ImportError:
    HAS_PLOTLY = False

_brl = lambda v: f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
_int = lambda v: f"{int(v):,}".replace(",", ".")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _default_weekend(df: pd.DataFrame) -> tuple[pd.Timestamp, pd.Timestamp]:
    """Retorna o último sábado+domingo disponível nos dados."""
    datas = pd.to_datetime(df["data"]).dt.normalize().unique()
    sab = sorted([d for d in datas if d.dayofweek == 5], reverse=True)
    dom = sorted([d for d in datas if d.dayofweek == 6], reverse=True)

    if sab and dom:
        # Par mais recente
        ultimo_sab = sab[0]
        ultimo_dom = [d for d in dom if d >= ultimo_sab]
        if ultimo_dom:
            return ultimo_sab, ultimo_dom[0]
        return ultimo_sab, ultimo_sab
    if sab:
        return sab[0], sab[0]
    if dom:
        return dom[0], dom[0]
    # Fallback: últimos 2 dias de dados
    datas_sorted = sorted(datas, reverse=True)
    return datas_sorted[-1], datas_sorted[0]


def _consumo_cliente(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Retorna {cliente: DataFrame(produto, categoria, quantidade, faturamento)}."""
    grp = (
        df.groupby(["cliente", "produto", "categoria"])
        .agg(
            quantidade=("quantidade", "sum"),
            faturamento=("valor_total", "sum"),
        )
        .reset_index()
    )
    result = {}
    for cliente, sub in grp.groupby("cliente"):
        result[str(cliente)] = (
            sub.drop(columns="cliente")
            .sort_values("quantidade", ascending=False)
            .reset_index(drop=True)
        )
    return result


# ---------------------------------------------------------------------------
# Render principal
# ---------------------------------------------------------------------------

def render() -> None:
    st.title("🚚 Abastecimento")
    st.caption("Veja o que cada mercadinho consumiu no período para planejar a reposição.")

    df_full = load_data()

    # ── Filtro de datas ──────────────────────────────────────────────────────
    data_min = pd.to_datetime(df_full["data"]).min().date()
    data_max = pd.to_datetime(df_full["data"]).max().date()
    def_ini, def_fim = _default_weekend(df_full)

    with st.container():
        col_ini, col_fim, col_btn = st.columns([1, 1, 1])
        with col_ini:
            ini = st.date_input(
                "📅 De",
                value=def_ini.date(),
                min_value=data_min,
                max_value=data_max,
                key="abast_ini",
            )
        with col_fim:
            fim = st.date_input(
                "📅 Até",
                value=def_fim.date(),
                min_value=data_min,
                max_value=data_max,
                key="abast_fim",
            )
        with col_btn:
            st.markdown("<br>", unsafe_allow_html=True)
            resetar = st.button("↩ Fim de semana", use_container_width=True)
            if resetar:
                st.session_state["abast_ini"] = def_ini.date()
                st.session_state["abast_fim"] = def_fim.date()
                st.rerun()

    if ini > fim:
        st.warning("⚠️ A data inicial deve ser anterior à data final.")
        return

    # ── Filtrar dados ────────────────────────────────────────────────────────
    mask = (pd.to_datetime(df_full["data"]).dt.date >= ini) & \
           (pd.to_datetime(df_full["data"]).dt.date <= fim)
    df = df_full[mask].copy()

    if df.empty:
        st.info("Sem dados para o período selecionado.")
        return

    # ── Banner de contexto ───────────────────────────────────────────────────
    n_dias = (fim - ini).days + 1
    label_periodo = (
        f"{ini.strftime('%d/%m')} – {fim.strftime('%d/%m/%Y')}"
        if ini != fim else ini.strftime("%d/%m/%Y")
    )
    fat_total = df["valor_total"].sum()
    itens_total = int(df["quantidade"].sum())
    n_produtos_total = df["produto"].nunique()
    n_clientes = df["cliente"].nunique()

    st.markdown(
        f"""
        <div style="
            background:{COLORS['primary_pale']};
            border-left:4px solid {COLORS['primary']};
            padding:12px 18px; border-radius:8px; margin-bottom:1rem;
        ">
            <span style="font-size:.85rem;color:{COLORS['text_secondary']};font-weight:600;">
                📦 {label_periodo} &nbsp;·&nbsp; {n_dias} dia(s) &nbsp;·&nbsp;
                {n_clientes} mercadinhos &nbsp;·&nbsp;
                {_int(itens_total)} itens consumidos &nbsp;·&nbsp;
                {n_produtos_total} produtos distintos &nbsp;·&nbsp;
                {_brl(fat_total)} em vendas
            </span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Totais por cliente (resumo rápido) ───────────────────────────────────
    st.subheader("📊 Resumo por mercadinho")
    st.caption("Total consumido no período — clique no gráfico para ver detalhes abaixo.")

    resumo = (
        df.groupby("cliente")
        .agg(itens=("quantidade", "sum"), faturamento=("valor_total", "sum"))
        .reset_index()
        .sort_values("itens", ascending=False)
    )

    if HAS_PLOTLY:
        fig_resumo = px.bar(
            resumo,
            x="itens",
            y="cliente",
            orientation="h",
            color="faturamento",
            color_continuous_scale="Blues",
            text="itens",
            custom_data=["faturamento"],
        )
        fig_resumo.update_traces(
            texttemplate="%{x} itens",
            textposition="outside",
            hovertemplate=(
                "<b>%{y}</b><br>"
                "Itens: %{x}<br>"
                "Faturamento: R$ %{customdata[0]:,.2f}<extra></extra>"
            ),
        )
        fig_resumo.update_layout(
            coloraxis_showscale=False,
            showlegend=False,
            height=max(220, len(resumo) * 36),
            margin=dict(t=10, b=10, l=10, r=120),
            yaxis=dict(autorange="reversed"),
            plot_bgcolor=COLORS["surface"],
            paper_bgcolor=COLORS["surface"],
            font=dict(family="sans-serif", size=12, color=COLORS["text_primary"]),
            xaxis_title="",
            yaxis_title="",
        )
        st.plotly_chart(fig_resumo, use_container_width=True)
    else:
        st.bar_chart(resumo.set_index("cliente")["itens"])

    top_cliente = resumo.iloc[0]
    st.caption(
        f"💡 **{top_cliente['cliente']}** foi o maior consumidor: "
        f"{_int(top_cliente['itens'])} itens ({_brl(top_cliente['faturamento'])})."
    )

    st.markdown("---")

    # ── Gráfico por cliente ──────────────────────────────────────────────────
    st.subheader("🏪 Consumo detalhado por mercadinho")
    st.caption("Produtos consumidos no período, ordenados por quantidade. Use para montar o pedido de reposição.")

    consumo = _consumo_cliente(df)

    # Ordem: maior consumidor primeiro
    ordem_clientes = resumo["cliente"].tolist()

    for cliente in ordem_clientes:
        if cliente not in consumo:
            continue
        df_c = consumo[cliente]
        itens_c = int(df_c["quantidade"].sum())
        fat_c = df_c["faturamento"].sum()
        n_prod_c = len(df_c)

        with st.container():
            st.markdown(
                f"""
                <div style="
                    background:{COLORS['neutral_light']};
                    border-left:3px solid {COLORS['primary']};
                    padding:8px 14px; border-radius:6px; margin-bottom:4px;
                ">
                    <span style="font-weight:700;color:{COLORS['primary']};font-size:1rem;">
                        🏪 {cliente}
                    </span>
                    &nbsp;
                    <span style="color:{COLORS['text_secondary']};font-size:.85rem;">
                        {n_prod_c} produtos &nbsp;·&nbsp; {_int(itens_c)} itens &nbsp;·&nbsp; {_brl(fat_c)}
                    </span>
                </div>
                """,
                unsafe_allow_html=True,
            )

            if HAS_PLOTLY:
                # Top 25 produtos por quantidade (se tiver mais)
                df_plot = df_c.head(25).copy()

                # Cor por categoria
                categorias = df_plot["categoria"].unique().tolist()
                cat_color = {c: CHART_PALETTE_CATEGORICAL[i % len(CHART_PALETTE_CATEGORICAL)]
                             for i, c in enumerate(categorias)}
                df_plot["cor"] = df_plot["categoria"].map(cat_color)

                fig = go.Figure()
                for cat in categorias:
                    sub = df_plot[df_plot["categoria"] == cat]
                    fig.add_trace(go.Bar(
                        x=sub["quantidade"],
                        y=sub["produto"],
                        orientation="h",
                        name=cat,
                        marker_color=cat_color[cat],
                        text=sub["quantidade"],
                        textposition="outside",
                        customdata=sub[["faturamento"]].values,
                        hovertemplate=(
                            "<b>%{y}</b><br>"
                            "Qtd: %{x}<br>"
                            "Faturamento: R$ %{customdata[0]:,.2f}<extra></extra>"
                        ),
                    ))

                altura = max(280, len(df_plot) * 28)
                fig.update_layout(
                    barmode="stack",
                    height=altura,
                    showlegend=len(categorias) > 1,
                    legend=dict(
                        orientation="h",
                        yanchor="bottom", y=1.02,
                        xanchor="left", x=0,
                        font=dict(size=10),
                    ),
                    margin=dict(t=30, b=10, l=10, r=80),
                    yaxis=dict(autorange="reversed"),
                    plot_bgcolor=COLORS["surface"],
                    paper_bgcolor=COLORS["surface"],
                    font=dict(family="sans-serif", size=11, color=COLORS["text_primary"]),
                    xaxis_title="Quantidade consumida",
                    yaxis_title="",
                )
                st.plotly_chart(fig, use_container_width=True)

            else:
                st.bar_chart(df_c.set_index("produto")["quantidade"])

            # Insight automático
            top_prod = df_c.iloc[0]
            st.caption(
                f"🔝 **{top_prod['produto']}** foi o mais consumido: "
                f"{_int(top_prod['quantidade'])} unid. — "
                f"garantir estoque para segunda."
            )

            # Tabela compacta em expander
            with st.expander(f"📋 Lista completa — {cliente} ({n_prod_c} produtos)"):
                df_tabela = df_c.copy()
                df_tabela.columns = ["Produto", "Categoria", "Qtd", "Faturamento (R$)"]
                df_tabela["Faturamento (R$)"] = df_tabela["Faturamento (R$)"].apply(
                    lambda v: _brl(v)
                )
                st.dataframe(df_tabela, hide_index=True, use_container_width=True)

            st.markdown("")  # espaço entre clientes
