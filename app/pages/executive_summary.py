from __future__ import annotations

import streamlit as st

from auth.auth_service import require_login
from domain.contracts import SMALL_BASE_THRESHOLD_DAYS
from domain.enums import AlertSeverity, Priority
from services.actions_log import get_all
from services.alerts import gerar_alertas
from services.data_loader import load_data
from services.exporter import export_executive_summary_text, summary_txt_filename
from services.finance import (
    get_cobertura_custo,
    get_margin,
    get_products_with_loss,
    get_top_profit_products,
    get_total_profit,
)
from services.intelligence import (
    detect_anomalies,
    forecast_next_days,
    get_revenue_trend,
)
from services.metrics import kpis_gerais
from services.recommendations import generate_recommendations
from services.simulator import simular_pix, simular_projecao_mensal


def _brl(v: float) -> str:
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


# ---------------------------------------------------------------------------
# Banner de limitação de base
# ---------------------------------------------------------------------------
def _render_banner_base(n_dias: int) -> None:
    if n_dias < SMALL_BASE_THRESHOLD_DAYS:
        st.warning(
            f"**Base de análise: {n_dias} dia(s)**  \n"
            "✅ **Leitura operacional:** confiável para tendências do período.  \n"
            "⚠️ **Leitura estratégica:** limitada — base inferior a 15 dias pode não representar padrões sazonais."
        )
    else:
        st.success(f"Base de análise: {n_dias} dia(s) — suficiente para leitura estratégica.")


# ---------------------------------------------------------------------------
# Bloco 1 — Resumo do período
# ---------------------------------------------------------------------------
def _render_resumo(kpis: dict, n_dias: int) -> None:
    st.markdown("### 📋 Resumo do Período")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("💰 Faturamento",   _brl(kpis["faturamento"]))
    c2.metric("🎫 Ticket Médio",  _brl(kpis["ticket_medio"]))
    c3.metric("🏢 Clientes",      str(kpis["n_clientes"]))
    c4.metric("🧾 Transações",    f'{kpis["n_transacoes"]:,}')
    c5.metric("📅 Dias analisados", str(n_dias))


# ---------------------------------------------------------------------------
# Bloco 2 — Riscos
# ---------------------------------------------------------------------------
def _render_riscos(alertas: list) -> None:
    st.markdown("### 🚨 Principais Riscos")
    erros    = [a for a in alertas if a.severity == AlertSeverity.error]
    warnings = [a for a in alertas if a.severity == AlertSeverity.warning]

    if not erros and not warnings:
        st.success("Nenhum risco crítico identificado no período.")
        return

    for a in erros:
        st.error(f"**{a.titulo}**  \n{a.mensagem}  \n*Ação imediata:* {a.acao}")
    for a in warnings:
        st.warning(f"**{a.titulo}**  \n{a.mensagem}  \n*Ação:* {a.acao}")


# ---------------------------------------------------------------------------
# Bloco 3 — Oportunidades
# ---------------------------------------------------------------------------
def _render_oportunidades(recs: list) -> None:
    st.markdown("### 💡 Principais Oportunidades")
    oportunidades = [r for r in recs if r.prioridade in (Priority.alta, Priority.media)]

    if not oportunidades:
        st.info("Nenhuma oportunidade identificada com os dados atuais.")
        return

    for rec in oportunidades[:5]:  # top 5 na visão executiva
        cor  = "#ff4b4b" if rec.prioridade == Priority.alta else "#ffa500"
        icone = "🔴" if rec.prioridade == Priority.alta else "🟡"
        st.markdown(
            f"""
            <div style="border-left:4px solid {cor}; padding:8px 12px;
                        background:#fafafa; border-radius:4px; margin-bottom:8px;">
                {icone} <strong>{rec.titulo}</strong><br>
                <span style="font-size:0.88rem; color:#444;">{rec.descricao}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )


# ---------------------------------------------------------------------------
# Bloco 3b — Rentabilidade (custo real)
# ---------------------------------------------------------------------------
def _render_rentabilidade(df) -> None:
    cobertura = get_cobertura_custo(df)
    if cobertura == 0:
        st.info(
            "**Analise de rentabilidade indisponivel** — cadastre custos em `app/data/custos.xlsx`."
        )
        return

    lucro_total  = get_total_profit(df)
    margem_media = get_margin(df)

    st.markdown("### 💰 Rentabilidade")

    if cobertura < 100:
        st.caption(f"Analise parcial — {cobertura:.1f}% dos produtos com custo cadastrado.")

    c1, c2 = st.columns(2)
    c1.metric(
        "Lucro Total (produtos c/ custo)",
        f"R$ {lucro_total:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        if lucro_total is not None else "N/D",
    )
    c2.metric(
        "Margem Media",
        f"{margem_media:.1f}%" if margem_media is not None else "N/D",
    )

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Fontes de lucro (top 5)**")
        top = get_top_profit_products(df, n=5)
        if not top.empty:
            for _, r in top.iterrows():
                sinal = "✅" if r["lucro"] > 0 else "⚠️"
                brl = f"R$ {r['lucro']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                st.markdown(f"{sinal} **{r['produto']}** — {brl} ({r['margem_pct']:.1f}%)")

    with col2:
        st.markdown("**Produtos em prejuizo**")
        loss = get_products_with_loss(df)
        if loss.empty:
            st.success("Nenhum produto em prejuizo.")
        else:
            for _, r in loss.iterrows():
                brl = f"R$ {r['lucro']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                st.error(f"🔴 **{r['produto']}** — {brl} ({r['margem_pct']:.1f}%)")


# ---------------------------------------------------------------------------
# Bloco 3c — Tendência e Previsão
# ---------------------------------------------------------------------------
def _render_tendencia_previsao(df) -> None:
    n_dias = df["data"].nunique() if not df.empty else 0
    if n_dias < 2:
        st.info("Base insuficiente para analise de tendencia (minimo 2 dias).")
        return

    trend    = get_revenue_trend(df)
    forecast = forecast_next_days(df, days=7)
    anomalias = detect_anomalies(df)

    st.markdown("### 🔮 Tendência e Previsão")

    icons = {"subindo": "📈", "caindo": "📉", "estavel": "➡️"}
    icon  = icons.get(trend["direction"], "➡️")

    c1, c2, c3 = st.columns(3)
    c1.metric("Direcao da tendencia", f"{icon} {trend['direction'].title()}")
    c2.metric("Variacao no periodo",  f"{trend['pct_variacao']:+.1f}%")

    previsao_df = forecast["previsao"]
    if not previsao_df.empty:
        total_7d = previsao_df["faturamento_previsto"].sum()
        c3.metric("Projecao proximos 7 dias", _brl(total_7d))

    # Anomalias do período
    if anomalias:
        quedas = [a for a in anomalias if a["tipo"] == "queda"]
        picos  = [a for a in anomalias if a["tipo"] == "pico"]
        if quedas:
            st.error(
                f"🔴 **{len(quedas)} dia(s) com queda anomala** detectado(s): "
                + ", ".join(str(a["data"]) for a in quedas)
            )
        if picos:
            st.warning(
                f"🟡 **{len(picos)} dia(s) com pico anomalo** detectado(s): "
                + ", ".join(str(a["data"]) for a in picos)
            )
    else:
        st.success("Nenhum dia com comportamento anomalo detectado no periodo.")

    # Resumo da previsão
    if not previsao_df.empty:
        with st.expander("Ver previsao dia a dia (proximos 7 dias)", expanded=False):
            st.caption(f"⚠️ {forecast['aviso']}")
            d = previsao_df.rename(columns={
                "data_prevista":        "Data",
                "faturamento_previsto": "Previsto (R$)",
                "limite_inferior":      "Limite Inf.",
                "limite_superior":      "Limite Sup.",
            })
            st.dataframe(d, use_container_width=True, hide_index=True)


# ---------------------------------------------------------------------------
# Bloco 4 — Recomendações prioritárias (alta apenas)
# ---------------------------------------------------------------------------
def _render_recomendacoes_prioritarias(recs: list) -> None:
    st.markdown("### 📌 Ações Prioritárias (Alta)")
    altas = [r for r in recs if r.prioridade == Priority.alta]
    if not altas:
        st.success("Nenhuma ação de alta prioridade pendente.")
        return

    for i, rec in enumerate(altas, 1):
        st.markdown(
            f"**{i}. {rec.titulo}**  \n"
            f"📈 *{rec.impacto_estimado}*"
        )
        st.markdown("---")


# ---------------------------------------------------------------------------
# Bloco 5 — Ações registradas
# ---------------------------------------------------------------------------
def _render_acoes_tomadas() -> None:
    st.markdown("### ✅ Ações Registradas")
    acoes = get_all()
    if not acoes:
        st.info("Nenhuma ação registrada ainda. Use o Dashboard para registrar ações tomadas.")
        return

    total     = len(acoes)
    resolvidas = sum(1 for a in acoes if a.get("resolvido"))
    pendentes  = total - resolvidas

    c1, c2, c3 = st.columns(3)
    c1.metric("Total de ações", total)
    c2.metric("Resolvidas",     resolvidas)
    c3.metric("Pendentes",      pendentes)

    if acoes:
        st.markdown("**Últimas 5 ações:**")
        for a in reversed(acoes[-5:]):
            status = "✅" if a.get("resolvido") else "🕐"
            st.markdown(
                f"{status} `{a['data'][:10]}` — **{a['titulo']}** "
                f"→ _{a['resultado']}_"
            )


# ---------------------------------------------------------------------------
# Bloco 6 — Impacto potencial (simulações resumidas)
# ---------------------------------------------------------------------------
def _render_impacto_potencial(res_pix, res_proj) -> None:
    st.markdown("### 🧮 Impacto Potencial Estimado")

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Se PIX atingir 20%**")
        st.markdown(
            f"""
            <div style="background:#e8f5e9; border-radius:8px; padding:12px; text-align:center;">
                <span style="font-size:1.6rem; font-weight:700; color:#2e7d32;">
                    +{_brl(res_pix.impacto_financeiro)}
                </span><br>
                <span style="font-size:0.8rem; color:#555;">economia em taxas de cartão</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.caption(f"Premissas: {res_pix.premissas}")

    with c2:
        st.markdown("**Projeção para 30 dias**")
        st.markdown(
            f"""
            <div style="background:#e3f2fd; border-radius:8px; padding:12px; text-align:center;">
                <span style="font-size:1.6rem; font-weight:700; color:#1565c0;">
                    {_brl(res_proj.impacto_financeiro)}
                </span><br>
                <span style="font-size:0.8rem; color:#555;">projeção mensal estimada</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.caption(f"Premissas: {res_proj.premissas}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def render() -> None:
    require_login()

    df     = load_data()
    n_dias = df["data"].nunique()
    kpis   = kpis_gerais(df)
    alertas = gerar_alertas(df)
    recs    = generate_recommendations(df, kpis, alertas)

    res_pix  = simular_pix(df, meta_pix_pct=20.0)
    res_proj = simular_projecao_mensal(df)
    periodo_str = f"{df['data'].min()} → {df['data'].max()}"

    # Cabeçalho com exportação
    col_title, col_export = st.columns([3, 1])
    with col_title:
        st.title("📊 Resumo Executivo — Mercadinhos")
        st.caption("Visão de gestão: leitura em 30 segundos.")
    with col_export:
        summary_data = {
            "periodo":        periodo_str,
            "n_dias":         n_dias,
            "faturamento":    kpis["faturamento"],
            "ticket_medio":   kpis["ticket_medio"],
            "n_clientes":     kpis["n_clientes"],
            "n_transacoes":   kpis["n_transacoes"],
            "n_produtos":     kpis["n_produtos"],
            "alertas":        [f"[{a.severity.value.upper()}] {a.titulo}" for a in alertas],
            "recomendacoes":  [f"[{r.prioridade.value.upper()}] {r.titulo}" for r in recs],
            "projecao_mensal":res_proj.impacto_financeiro,
            "economia_pix":   res_pix.impacto_financeiro,
        }
        st.markdown("<div style='padding-top:1.4rem;'></div>", unsafe_allow_html=True)
        st.download_button(
            label="⬇️ Exportar TXT",
            data=export_executive_summary_text(summary_data),
            file_name=summary_txt_filename(),
            mime="text/plain",
            use_container_width=True,
        )

    _render_banner_base(n_dias)
    st.markdown("---")
    _render_resumo(kpis, n_dias)
    st.markdown("---")
    _render_rentabilidade(df)
    st.markdown("---")
    _render_tendencia_previsao(df)
    st.markdown("---")

    col_riscos, col_ops = st.columns(2)
    with col_riscos:
        _render_riscos(alertas)
    with col_ops:
        _render_oportunidades(recs)

    st.markdown("---")
    _render_recomendacoes_prioritarias(recs)
    st.markdown("---")
    _render_acoes_tomadas()
    st.markdown("---")
    _render_impacto_potencial(res_pix, res_proj)


if __name__ == "__main__":
    render()
