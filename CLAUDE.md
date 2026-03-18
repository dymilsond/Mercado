# Design System Rules — Mercadinhos Analytics
> Python 3.13 · Streamlit 1.35+ · Plotly Express + Graph Objects

---

## 1. PALETA DE CORES OFICIAL

### Cores Semânticas (usar SEMPRE estas — nunca hardcode fora desta lista)

```python
# cores.py → importar de domain/design_tokens.py (criar se não existir)
COLORS = {
    # Primárias
    "primary":        "#1565c0",   # Azul principal — dados neutros, faturamento
    "primary_light":  "#1e88e5",   # Azul médio — variações, hover
    "primary_pale":   "#e8f0fe",   # Azul muito claro — backgrounds de destaque

    # Acento
    "teal":           "#00897b",   # Teal — segunda dimensão (ex: comparativo)
    "teal_light":     "#4db6ac",   # Teal claro

    # Semânticas
    "success":        "#2e7d32",   # Verde — crescimento, lucro, positivo
    "success_light":  "#a5d6a7",   # Verde claro — fundo de badges positivas
    "warning":        "#f57c00",   # Laranja — atenção, estável, neutro relevante
    "warning_light":  "#ffe0b2",   # Laranja claro
    "danger":         "#c62828",   # Vermelho — queda, prejuízo, crítico
    "danger_light":   "#ffcdd2",   # Vermelho claro
    "info":           "#0277bd",   # Azul info — dicas, avisos informativos
    "info_light":     "#e1f5fe",   # Azul info claro

    # Neutros
    "neutral":        "#546e7a",   # Blue Grey — texto secundário, bordas
    "neutral_light":  "#eceff1",   # Blue Grey muito claro — fundo de cards neutros
    "text_primary":   "#1a1a2e",   # Texto principal
    "text_secondary": "#546e7a",   # Texto secundário / captions
    "surface":        "#f8fafc",   # Background de gráficos
    "white":          "#ffffff",
}

# Sequências para gráficos (ordem harmônica)
CHART_PALETTE_CATEGORICAL = [
    "#1565c0",   # primary
    "#00897b",   # teal
    "#f57c00",   # warning/orange
    "#7b1fa2",   # roxo (4ª categoria)
    "#c62828",   # danger (5ª)
    "#546e7a",   # neutral (6ª+)
]

CHART_PALETTE_SEQUENTIAL = "Blues"       # Para valores contínuos positivos
CHART_PALETTE_DIVERGING  = "RdYlGn"     # Para valores com positivo/negativo
```

---

## 2. REGRAS DE GRÁFICOS — OBRIGATÓRIO

### 2.1 Gráfico de Pizza vs. Barra
```
SE número de categorias <= 4 → USAR px.pie() com hole=0.4 (rosca)
SE número de categorias  > 4 → USAR px.bar() horizontal (orientation="h")

NUNCA criar pizza com mais de 4 fatias — fica ilegível.
```

### 2.2 Configuração Padrão de Pizza (≤ 4 fatias)
```python
fig = px.pie(
    df, names=col_label, values=col_value,
    hole=0.4,
    color_discrete_sequence=CHART_PALETTE_CATEGORICAL,
)
fig.update_traces(
    textposition="outside",
    textinfo="percent+label",
    textfont_size=12,
    pull=[0.03] * len(df),          # leve separação nas fatias
)
fig.update_layout(
    showlegend=False,                # label já aparece no gráfico
    margin=dict(t=20, b=20, l=10, r=10),
    height=280,
    paper_bgcolor=COLORS["surface"],
)
```

### 2.3 Configuração Padrão de Barra (> 4 itens ou ranking)
```python
# Horizontal (rankings, produtos, clientes)
fig = px.bar(
    df, x=col_value, y=col_label,
    orientation="h",
    color=col_value,
    color_continuous_scale="Blues",
    text=col_value,                  # valor no final da barra
)
fig.update_traces(
    texttemplate="R$ %{x:,.0f}",
    textposition="outside",
)
fig.update_layout(
    coloraxis_showscale=False,
    showlegend=False,
    margin=dict(t=20, b=20, l=10, r=10),
    height=max(280, len(df) * 32),   # altura dinâmica: 32px por item
    yaxis=dict(autorange="reversed"),
    plot_bgcolor=COLORS["surface"],
    paper_bgcolor=COLORS["surface"],
    xaxis_title="",
    yaxis_title="",
)
```

### 2.4 Layout Padrão Para Todos os Gráficos
```python
# Aplicar SEMPRE
fig.update_layout(
    font=dict(family="sans-serif", size=12, color=COLORS["text_primary"]),
    plot_bgcolor=COLORS["surface"],
    paper_bgcolor=COLORS["surface"],
    margin=dict(t=32, b=16, l=10, r=10),
    legend=dict(
        orientation="h",
        yanchor="bottom", y=1.02,
        xanchor="left", x=0,
        font=dict(size=11),
    ),
)
```

### 2.5 Cores Semânticas em Gráficos
```python
# SEMPRE usar estas cores para significados específicos
cor_positivo  = COLORS["success"]    # crescimento, lucro, acima da média
cor_negativo  = COLORS["danger"]     # queda, prejuízo, abaixo da média
cor_neutro    = COLORS["primary"]    # valor padrão sem conotação
cor_anomalia  = COLORS["warning"]    # picos ou quedas anômalas
cor_previsao  = COLORS["warning"]    # linha de projeção futura
```

---

## 3. HISTORY TELLING — FLUXO NARRATIVO

O dashboard deve contar uma história. Cada página segue esta ordem obrigatória:

```
[1] CONTEXTO       → Período e filtros aplicados (o que estamos vendo?)
[2] HEADLINE       → KPIs mais importantes em destaque (qual foi o resultado?)
[3] DIAGNÓSTICO    → Inteligência analítica: tendência, anomalias (o que aconteceu?)
[4] ALERTAS        → Problemas que precisam de ação imediata (o que preocupa?)
[5] OPORTUNIDADES  → Recomendações (o que fazer?)
[6] DETALHE        → Drill-down por dimensão (por quê / quem / quando?)
[7] AÇÃO           → Simulações e exportação (o que vou fazer?)
```

### Implementação no Dashboard:
```
render()
 ├── banner de contexto (período, n_dias, filtros ativos)
 ├── _render_kpis()              → [2] HEADLINE
 ├── _render_inteligencia()      → [3] DIAGNÓSTICO  ← sempre visível
 ├── _render_alertas()           → [4] ALERTAS
 ├── _render_recomendacoes()     → [5] OPORTUNIDADES
 ├── _render_clientes()          → [6] DETALHE — por cliente
 ├── _render_categorias()        → [6] DETALHE — por categoria
 ├── _render_produtos()          → [6] DETALHE — por produto
 ├── _render_temporal()          → [6] DETALHE — por tempo
 ├── _render_pagamentos()        → [6] DETALHE — por pagamento
 ├── _render_financeiro()        → [6] DETALHE — margem/lucro
 └── _render_exportacao()        → [7] AÇÃO
```

### Transições entre seções (usar dividers com label):
```python
st.markdown("---")
# OU usar seção com header visível e caption explicativa
st.subheader("📦 Produtos")
st.caption("Ranking por faturamento, análise de Pareto e itens de baixa saída.")
```

---

## 4. COMPONENTES DE UI — PADRÕES

### 4.1 KPI Card (métrica em destaque)
```python
# Padrão: st.metric() dentro de st.columns()
# SEMPRE usar emoji + label claro + valor formatado
col.metric(label="💰 Faturamento", value="R$ 13.060,19", delta="+12%")

# Para KPI principal (destaque isolado)
st.markdown(f"""
<div style="
    background:{COLORS['primary_pale']};
    border-left:4px solid {COLORS['primary']};
    padding:16px 20px; border-radius:8px;
">
    <div style="font-size:.8rem;color:{COLORS['text_secondary']};text-transform:uppercase;letter-spacing:.05em;">
        {label}
    </div>
    <div style="font-size:1.8rem;font-weight:700;color:{COLORS['primary']};">
        {value}
    </div>
</div>
""", unsafe_allow_html=True)
```

### 4.2 Badge Semântico (status, tendência)
```python
# Verde/Vermelho/Laranja com ícone
def badge(text, color, bg_color):
    return f"""<span style="
        background:{bg_color}; color:{color};
        padding:3px 10px; border-radius:20px;
        font-size:.8rem; font-weight:600;
    ">{text}</span>"""

# Uso:
# badge("↑ Crescendo", COLORS["success"], COLORS["success_light"])
# badge("↓ Queda",     COLORS["danger"],  COLORS["danger_light"])
# badge("→ Estável",   COLORS["warning"], COLORS["warning_light"])
```

### 4.3 Insight Card (narrativa de dado)
```python
# Para destacar um insight importante junto a um gráfico
st.info("💡 **Heineken Longneck** responde por 7,1% do faturamento — "
        "maior produto individual. Garantir estoque prioritário.")
```

### 4.4 Seção com Header Consistente
```python
def section_header(emoji, title, subtitle=None):
    st.markdown(f"### {emoji} {title}")
    if subtitle:
        st.caption(subtitle)
```

---

## 5. LAYOUT E ESPAÇAMENTO

### 5.1 Colunas por contexto
```python
# KPIs principais         → st.columns(6)  ou columns([1,1,1,1,1,1])
# KPIs + gráfico          → st.columns([1.2, 2])
# Gráfico + tabela        → st.columns([1.5, 1])  ou [2, 1]
# Pizza + tabela          → st.columns([1, 1.4])
# Dois gráficos lado a lado → st.columns(2)
```

### 5.2 Hierarquia de títulos
```python
st.title("📊 Dashboard Analítico — Mercadinhos")   # 1 por página
st.subheader("### 🏢 Clientes")                     # por seção
st.caption("Ranking por faturamento")               # subtítulo de seção
# NÃO usar st.header() — hierarquia fica estranha com o tema atual
```

### 5.3 Expanders — quando usar
```python
# Usar expander para: informações secundárias, detalhes técnicos, exportação
# NÃO usar expander para: conteúdo principal do story telling
# Financeiro, Simulações, Recomendações → OK em expander
# KPIs, Inteligência, Alertas → NUNCA em expander
```

### 5.4 Tabs — quando usar
```python
# Usar tabs para: múltiplas perspectivas do MESMO dado
# Ex: Temporal → Diário | Dia Semana | Por Hora | Heatmap
# Máximo 5 tabs por bloco
# Labels: curtos + emoji  ex: "📅 Diário", "🕐 Hora"
```

---

## 6. CONVENÇÕES DE CÓDIGO

### 6.1 Formatos de valor
```python
_brl = lambda v: f"R$ {v:,.2f}".replace(",","X").replace(".",",").replace("X",".")
_pct = lambda v: f"{v:.1f}%"
_int = lambda v: f"{v:,}".replace(",",".")
```

### 6.2 Verificação Plotly
```python
try:
    import plotly.express as px
    import plotly.graph_objects as go
    HAS_PLOTLY = True
except ImportError:
    HAS_PLOTLY = False
# Sempre usar fallback st.bar_chart() / st.line_chart() se HAS_PLOTLY=False
```

### 6.3 Proteção de dados vazios
```python
# SEMPRE verificar antes de criar gráfico
if df.empty or len(df) == 0:
    st.info("Sem dados para exibir.")
    return
```

### 6.4 Insigths automáticos (regra de ouro)
```python
# Após CADA gráfico principal, adicionar 1 insight textual automático
# Formato: st.caption() ou st.info() com texto gerado do dado
top = df.iloc[0]
st.caption(f"💡 **{top['cliente']}** lidera com "
           f"{_brl(top['faturamento'])} ({top['pct']:.1f}% do total).")
```

---

## 7. REGRAS DE ACESSIBILIDADE E UX

- **Nunca** depender só de cor para transmitir significado — usar ícone + cor
- **Sempre** ter título descritivo no gráfico (via `st.caption()` acima ou abaixo)
- **Gráficos interativos**: usar `use_container_width=True` sempre
- **Tabelas**: usar `hide_index=True` e renomear colunas para português
- **Números**: sempre formatar (R$ e vírgula decimal para BRL, ponto para milhar)
- **Loading**: dados pesados dentro de `@st.cache_data(ttl=300)`

---

## 8. ESTRUTURA DE ARQUIVOS

```
app/
├── domain/
│   ├── design_tokens.py    ← CRIAR: cores, paletas, constantes visuais
│   ├── contracts.py
│   ├── enums.py
│   └── models.py
├── pages/
│   ├── dashboard.py        ← layout principal (history telling)
│   ├── executive_summary.py
│   ├── benchmark.py
│   └── admin.py
├── services/               ← lógica de negócio pura (sem Streamlit)
└── main.py                 ← autenticação, sidebar, roteamento
```

---

## 9. CHECKLIST PARA NOVA SEÇÃO/GRÁFICO

Antes de adicionar qualquer bloco visual novo:

- [ ] O conteúdo encaixa no fluxo de history telling?
- [ ] Se tem > 4 categorias, usar barra (não pizza)?
- [ ] Cores estão na paleta oficial `COLORS`?
- [ ] Tem `st.caption()` explicativo antes ou depois?
- [ ] Tem fallback para dados vazios?
- [ ] Tem insight textual automático do dado principal?
- [ ] Largura: `use_container_width=True`?
- [ ] Tabela: `hide_index=True` + colunas em português?
- [ ] Altura do gráfico proporcional ao conteúdo (não fixo 350 para tudo)?
