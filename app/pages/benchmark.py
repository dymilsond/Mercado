from __future__ import annotations

import streamlit as st

from auth.auth_service import require_login
from services.benchmark import (
    get_comparative_alerts,
    get_unit_benchmark,
    get_unit_payment_comparison,
    get_unit_profile,
    get_unit_ranking,
    get_unit_time_comparison,
    get_unit_vs_average,
)
from services.data_loader import load_data


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _brl(v: float) -> str:
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _pct(v: float) -> str:
    return f"{v:.1f}%"


def _delta_badge(val: float) -> str:
    if val >= 10:
        return f"<span style='color:#2e7d32; font-weight:700;'>▲ {val:+.1f}%</span>"
    if val <= -10:
        return f"<span style='color:#c62828; font-weight:700;'>▼ {val:+.1f}%</span>"
    return f"<span style='color:#888;'>~ {val:+.1f}%</span>"


# ---------------------------------------------------------------------------
# Bloco 1 — Ranking
# ---------------------------------------------------------------------------
def _render_ranking(df) -> None:
    st.markdown("### 🏆 Ranking de Unidades")
    rank = get_unit_ranking(df)

    try:
        import plotly.express as px

        fig = px.bar(
            rank,
            x="cliente",
            y="faturamento",
            color="faturamento",
            color_continuous_scale="Blues",
            text="participacao_pct",
            labels={"faturamento": "Faturamento (R$)", "cliente": ""},
            height=320,
        )
        fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
        fig.update_layout(coloraxis_showscale=False, margin=dict(t=10, b=10))
        st.plotly_chart(fig, use_container_width=True)
    except ImportError:
        pass

    display = rank[[
        "ranking", "cliente", "faturamento", "participacao_pct",
        "transacoes", "ticket_medio", "n_produtos", "itens_por_trans",
    ]].copy()
    display.columns = [
        "#", "Unidade", "Faturamento (R$)", "% Total",
        "Transações", "Ticket Médio", "Produtos", "Itens/Trans",
    ]
    display["Faturamento (R$)"] = display["Faturamento (R$)"].apply(_brl)
    display["% Total"]          = display["% Total"].apply(_pct)
    display["Ticket Médio"]     = display["Ticket Médio"].apply(_brl)
    st.dataframe(display, use_container_width=True, hide_index=True)


# ---------------------------------------------------------------------------
# Bloco 2 — Gap vs média
# ---------------------------------------------------------------------------
def _render_gap_vs_media(df) -> None:
    st.markdown("### 📊 Gap vs Média do Grupo")
    gap = get_unit_vs_average(df)

    media_fat    = gap["faturamento"].mean()
    media_ticket = gap["ticket_medio"].mean()

    st.caption(
        f"Média do grupo — Faturamento: {_brl(media_fat)} · "
        f"Ticket Médio: {_brl(media_ticket)}"
    )

    try:
        import plotly.express as px
        import plotly.graph_objects as go

        fig = go.Figure()
        cores = [
            "#2e7d32" if v >= 10 else ("#c62828" if v <= -10 else "#1565c0")
            for v in gap["gap_fat_pct"]
        ]
        fig.add_trace(go.Bar(
            x=gap["cliente"],
            y=gap["gap_fat_pct"],
            marker_color=cores,
            text=[f"{v:+.1f}%" for v in gap["gap_fat_pct"]],
            textposition="outside",
        ))
        fig.add_hline(y=0, line_dash="dash", line_color="gray", line_width=1)
        fig.update_layout(
            title="Desvio do faturamento vs média (%)",
            xaxis_title="",
            yaxis_title="% vs média",
            height=300,
            margin=dict(t=40, b=10),
        )
        st.plotly_chart(fig, use_container_width=True)
    except ImportError:
        pass

    # Tabela
    rows = []
    for _, r in gap.iterrows():
        rows.append({
            "Unidade":           r["cliente"],
            "Status":            {"acima": "✅ Acima", "abaixo": "⚠️ Abaixo", "na_media": "➡️ Na média"}.get(r["status"], ""),
            "Faturamento":       _brl(r["faturamento"]),
            "Gap Fat (R$)":      f'{r["gap_fat_abs"]:+,.2f}',
            "Gap Fat (%)":       f'{r["gap_fat_pct"]:+.1f}%',
            "Ticket Médio":      _brl(r["ticket_medio"]),
            "Gap Ticket (%)":    f'{r["gap_ticket_pct"]:+.1f}%',
        })
    import pandas as pd
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


# ---------------------------------------------------------------------------
# Bloco 3 — Comparação lado a lado
# ---------------------------------------------------------------------------
def _render_comparacao(df) -> None:
    st.markdown("### 🔀 Comparação A vs B")
    unidades = sorted(df["cliente"].unique().tolist())
    if len(unidades) < 2:
        st.info("Necessário pelo menos 2 unidades para comparação.")
        return

    col1, col2 = st.columns(2)
    uni_a = col1.selectbox("Unidade A", unidades, index=0, key="bench_a")
    uni_b = col2.selectbox("Unidade B", unidades, index=min(1, len(unidades)-1), key="bench_b")

    if uni_a == uni_b:
        st.warning("Selecione unidades diferentes para comparar.")
        return

    pa = get_unit_profile(df, uni_a)
    pb = get_unit_profile(df, uni_b)

    st.markdown("---")
    cols = st.columns(5)
    kpis = [
        ("Faturamento",  _brl(pa["faturamento"]),      _brl(pb["faturamento"])),
        ("Ticket Médio", _brl(pa["ticket_medio"]),     _brl(pb["ticket_medio"])),
        ("Transações",   str(pa["n_transacoes"]),      str(pb["n_transacoes"])),
        ("Produtos",     str(pa["n_produtos"]),         str(pb["n_produtos"])),
        ("PIX %",        _pct(pa["pix_pct"]),           _pct(pb["pix_pct"])),
    ]
    for col, (label, va, vb) in zip(cols, kpis):
        col.markdown(
            f"""
            <div style="border:1px solid #e0e0e0; border-radius:8px; padding:10px; margin-bottom:6px;">
                <div style="font-size:0.78rem; color:#888; margin-bottom:4px;">{label}</div>
                <div style="font-size:0.9rem;"><strong style="color:#1565c0;">{uni_a[:12]}</strong><br>{va}</div>
                <div style="font-size:0.9rem; margin-top:4px;"><strong style="color:#c62828;">{uni_b[:12]}</strong><br>{vb}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Top produtos comparados
    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"**Top produtos — {uni_a}**")
        if not pa["top_produtos"].empty:
            d = pa["top_produtos"].copy()
            d["faturamento"] = d["faturamento"].apply(_brl)
            d["pct"] = d["pct"].apply(_pct)
            st.dataframe(d, use_container_width=True, hide_index=True)

    with col2:
        st.markdown(f"**Top produtos — {uni_b}**")
        if not pb["top_produtos"].empty:
            d = pb["top_produtos"].copy()
            d["faturamento"] = d["faturamento"].apply(_brl)
            d["pct"] = d["pct"].apply(_pct)
            st.dataframe(d, use_container_width=True, hide_index=True)


# ---------------------------------------------------------------------------
# Bloco 4 — Perfil individual
# ---------------------------------------------------------------------------
def _render_perfil_unidade(df) -> None:
    st.markdown("### 🔎 Perfil por Unidade")
    unidades = sorted(df["cliente"].unique().tolist())
    unidade  = st.selectbox("Selecione a unidade", unidades, key="bench_perfil")
    perfil   = get_unit_profile(df, unidade)

    if not perfil:
        st.warning("Sem dados para essa unidade.")
        return

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Faturamento",   _brl(perfil["faturamento"]))
    col2.metric("Ticket Médio",  _brl(perfil["ticket_medio"]))
    col3.metric("Transações",    str(perfil["n_transacoes"]))
    col4.metric("Produtos",      str(perfil["n_produtos"]))
    col5.metric("PIX",           _pct(perfil["pix_pct"]))

    st.markdown(f"**Hora de pico:** {perfil['hora_pico']}h · "
                f"**Categorias:** {perfil['n_categorias']} · "
                f"**Concentração top produto:** {_pct(perfil['concentracao_top1_pct'])}")

    try:
        import plotly.express as px
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("**Categorias**")
            fig = px.pie(
                perfil["categorias"],
                names="categoria",
                values="faturamento",
                hole=0.35,
                height=280,
            )
            fig.update_layout(showlegend=True, margin=dict(t=10, b=10, l=10, r=10))
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            st.markdown("**Períodos do dia**")
            fig = px.bar(
                perfil["periodos"],
                x="periodo",
                y="valor_total",
                color="periodo",
                text="pct",
                labels={"valor_total": "R$", "periodo": ""},
                height=280,
            )
            fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
            fig.update_layout(showlegend=False, margin=dict(t=10, b=10))
            st.plotly_chart(fig, use_container_width=True)

    except ImportError:
        st.dataframe(perfil["categorias"], use_container_width=True, hide_index=True)


# ---------------------------------------------------------------------------
# Bloco 5 — Comparação de pagamentos
# ---------------------------------------------------------------------------
def _render_pagamentos_comparativos(df) -> None:
    st.markdown("### 💳 Pagamentos por Unidade")
    pgto = get_unit_payment_comparison(df)

    try:
        import plotly.express as px
        metodos = [c for c in pgto.columns if c != "unidade"]
        import pandas as pd
        melted = pgto.melt(id_vars="unidade", value_vars=metodos,
                           var_name="Método", value_name="% Transações")
        fig = px.bar(
            melted,
            x="unidade",
            y="% Transações",
            color="Método",
            barmode="stack",
            labels={"unidade": ""},
            height=320,
            color_discrete_sequence=["#1565c0", "#0288d1", "#26a69a", "#ef9a9a"],
        )
        fig.update_layout(margin=dict(t=10, b=10))
        st.plotly_chart(fig, use_container_width=True)
    except ImportError:
        pass

    # Destaque de PIX por unidade
    if "PIX" in pgto.columns:
        media_pix = pgto["PIX"].mean()
        st.caption(f"Média de PIX no grupo: {media_pix:.1f}%")
        for _, r in pgto.iterrows():
            pix_u = r["PIX"]
            diff  = pix_u - media_pix
            badge = "✅" if diff >= 0 else "⚠️"
            st.markdown(
                f"{badge} **{r['unidade']}**: PIX {_pct(pix_u)} "
                f"({diff:+.1f}pp vs média)",
                unsafe_allow_html=False,
            )


# ---------------------------------------------------------------------------
# Bloco 6 — Comparação de horários
# ---------------------------------------------------------------------------
def _render_horarios_comparativos(df) -> None:
    st.markdown("### 🕐 Distribuição de Horários por Unidade")
    tempo = get_unit_time_comparison(df)
    periodos_cols = [c for c in tempo.columns if c != "unidade"]

    try:
        import plotly.express as px
        import pandas as pd
        melted = tempo.melt(id_vars="unidade", value_vars=periodos_cols,
                            var_name="Período", value_name="% Faturamento")
        fig = px.bar(
            melted,
            x="unidade",
            y="% Faturamento",
            color="Período",
            barmode="stack",
            labels={"unidade": ""},
            height=320,
            color_discrete_sequence=["#1a237e", "#1565c0", "#1e88e5", "#64b5f6"],
        )
        fig.update_layout(margin=dict(t=10, b=10))
        st.plotly_chart(fig, use_container_width=True)
    except ImportError:
        st.dataframe(tempo, use_container_width=True, hide_index=True)


# ---------------------------------------------------------------------------
# Bloco 7 — Alertas comparativos
# ---------------------------------------------------------------------------
def _render_alertas_comparativos(df) -> None:
    alertas = get_comparative_alerts(df)
    if not alertas:
        st.success("Nenhum desvio comparativo crítico identificado.")
        return

    st.markdown(f"**{len(alertas)} desvio(s) comparativo(s) detectado(s)**")
    for a in alertas:
        msg = f"[{a['unidade']}] {a['mensagem']}"
        if a["severidade"] == "error":
            st.error(msg)
        elif a["severidade"] == "warning":
            st.warning(msg)
        else:
            st.info(msg)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def render() -> None:
    require_login()

    df = load_data()
    n_unidades = df["cliente"].nunique()
    n_dias     = df["data"].nunique()

    st.title("🏁 Benchmark de Unidades")
    st.caption(
        f"{n_unidades} unidade(s) · {n_dias} dia(s) analisado(s) · "
        "Cada 'Cliente' representa uma unidade operacional (mercadinho)."
    )

    if n_unidades < 2:
        st.warning("Necessário pelo menos 2 unidades para análise de benchmark.")
        return

    # Alertas comparativos no topo
    with st.expander("⚠️ Alertas Comparativos", expanded=True):
        _render_alertas_comparativos(df)

    st.markdown("---")
    _render_ranking(df)
    st.markdown("---")
    _render_gap_vs_media(df)
    st.markdown("---")
    _render_comparacao(df)
    st.markdown("---")
    _render_perfil_unidade(df)
    st.markdown("---")

    tab_pgto, tab_hora = st.tabs(["💳 Pagamentos", "🕐 Horários"])
    with tab_pgto:
        _render_pagamentos_comparativos(df)
    with tab_hora:
        _render_horarios_comparativos(df)


if __name__ == "__main__":
    render()
