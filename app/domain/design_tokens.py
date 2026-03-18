"""
Design tokens — Mercadinhos Analytics
Paleta oficial, sequências de cores e constantes visuais.
Importar SEMPRE daqui — nunca hardcode fora desta lista.
"""
from __future__ import annotations

COLORS: dict[str, str] = {
    # Primárias
    "primary":        "#1565c0",   # Azul principal — dados neutros, faturamento
    "primary_light":  "#1e88e5",   # Azul médio — variações, hover
    "primary_pale":   "#e8f0fe",   # Azul muito claro — backgrounds de destaque
    # Acento
    "teal":           "#00897b",   # Teal — segunda dimensão (comparativo)
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

# Sequência categórica (ordem harmônica — usar para gráficos com múltiplas séries)
CHART_PALETTE_CATEGORICAL: list[str] = [
    "#1565c0",   # primary
    "#00897b",   # teal
    "#f57c00",   # warning/orange
    "#7b1fa2",   # roxo (4ª categoria)
    "#c62828",   # danger (5ª)
    "#546e7a",   # neutral (6ª+)
]

CHART_PALETTE_SEQUENTIAL = "Blues"    # Valores contínuos positivos
CHART_PALETTE_DIVERGING  = "RdYlGn"  # Valores com positivo/negativo
