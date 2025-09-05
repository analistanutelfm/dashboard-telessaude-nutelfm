# --- 1. IMPORTAÇÃO DAS BIBLIOTECAS ---
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import io
from datetime import datetime
import os
import locale
import base64
from weasyprint import HTML, CSS
from openpyxl import load_workbook

# --- 2. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(layout="wide", page_title="Dashboard de Teleconsultorias")

# --- 3. FUNÇÕES AUXILIARES ---
@st.cache_data
def load_excel_upload(uploaded_file):
    """Lê um arquivo Excel a partir de um upload, tratando .xls e .xlsx."""
    try:
        file_name = uploaded_file.name
        engine = 'openpyxl' if file_name.endswith('.xlsx') else 'xlrd'
        df = pd.read_excel(uploaded_file, engine=engine)
        return df
    except Exception as e:
        st.error(f"Erro ao ler arquivo Excel do upload: {e}")
        return None

@st.cache_data
def load_local_data(path):
    if not os.path.exists(path):
        st.error(f"ERRO: Arquivo '{path}' não encontrado.")
        return None
    try:
        return pd.read_excel(path)
    except Exception as e:
        st.error(f"Erro ao ler arquivo local '{path}': {e}")
        return None

def find_existing(col_list, df_cols):
    for candidate in col_list:
        for c in df_cols:
            if str(c).strip().lower() == str(candidate).strip().lower():
                return c
    return None

def get_filter_options(df, col):
    if col in df.columns:
        return sorted(df[col].dropna().unique())
    return []

def to_excel_bytes_generic(df_export):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df_export.to_excel(writer, index=False, sheet_name='Dados Filtrados')
    return output.getvalue()

def to_excel_report_bytes(df_summary, df_details):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df_summary.to_excel(writer, index=False, sheet_name='Resumo_Performance')
        df_details.to_excel(writer, index=False, sheet_name='Detalhes_Consultorias')
        for sheet_name, df_sheet in [('Resumo_Performance', df_summary), ('Detalhes_Consultorias', df_details)]:
            worksheet = writer.sheets[sheet_name]
            if not df_sheet.empty:
                for idx, col in enumerate(df_sheet.columns):
                    series = df_sheet[col]
                    max_len = max(series.astype(str).map(len).max(), len(str(col))) + 2
                    worksheet.set_column(idx, idx, max_len)
    return output.getvalue()

def format_number(n):
    if pd.isna(n): return 'N/D'
    try:
        return locale.format_string("%d", int(n), grouping=True)
    except (ValueError, TypeError):
        return n

# --- RENDERIZAÇÃO PRINCIPAL ---
st.title("Dashboard de Gestão e Análise de Teleconsultorias")

try:
    locale.setlocale(locale.LC_ALL, 'pt_BR.UTF-8')
except locale.Error:
    st.warning("Locale 'pt_BR.UTF-8' não encontrado. A formatação de números pode não estar correta.")
    try:
        locale.setlocale(locale.LC_ALL, '')
    except locale.Error:
        st.warning("Não foi possível definir um locale padrão.")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
df_condicoes_raw = load_local_data(os.path.join(BASE_DIR, 'condicoes.xlsx'))
df_estabelecimentos_raw = load_local_data(os.path.join(BASE_DIR, 'estabelecimentos.xlsx'))
df_categoria_raw = load_local_data(os.path.join(BASE_DIR, 'categoria.xlsx'))

uploaded_file = st.file_uploader("Faça upload do arquivo Excel principal de teleconsultorias (xls/xlsx):", type=["xls", "xlsx"])

if uploaded_file is None:
    st.info("Por favor, faça o upload do relatório de teleconsultorias para começar a análise.")
    st.stop()

df_raw = load_excel_upload(uploaded_file)
if df_raw is None or df_condicoes_raw is None or df_estabelecimentos_raw is None or df_categoria_raw is None:
    st.error("Falha ao carregar um ou mais arquivos de dados.")
    st.stop()

col_map_full = {'Municipio Solicitante': ['Municipio Solicitante', 'Município Solicitante', 'Municipio'], 'Estabelecimento': ['Estabelecimento', 'Estabelecimento do Solicitante', 'Estabelecimento Solicitante', 'Unidade de Saúde'], 'Especialidade': ['Especialidade', 'Especialty', 'Specialty'], 'SolicitanteNome': ['Solicitante', 'Nome do Solicitante', 'Profissional Solicitante'], 'NomeEspecialista': ['Nome do Especialista', 'Nome do Especialista Teleconsultor', 'Especialista'], 'CBP': ['CBP', 'cbo'], 'Conduta': ['Conduta'], 'Inten.Encaminhamento': ['Inten.Encaminhamento'], 'Concluida?': ['Concluída?', 'Concluida?'], 'Data_Solicitacao': ['Data Solicitação', 'Data Solicitacao', 'Data_Solicitacao', 'Dt.Criação'], 'Data_Resposta': ['Data Resposta', 'Data_Resposta', 'Dt.1ª resposta'], 'Situação': ['Situação', 'Situacao', 'Status']}
mapped = {canonical: find_existing(candidates, df_raw.columns) for canonical, candidates in col_map_full.items()}
df = df_raw.rename(columns={v: k for k, v in mapped.items() if v})

for dcol in ['Data_Solicitacao', 'Data_Resposta']:
    if dcol in df.columns:
        df[dcol] = pd.to_datetime(df[dcol], errors='coerce', dayfirst=True)
if 'Concluida?' in df.columns:
    df['Concluida?'] = df['Concluida?'].astype(str).str.lower().str.strip()

if df_categoria_raw is not None:
    col_map_categoria = {'CBO': ['CBO'], 'Categoria': ['Categoria']}
    mapped_cat = {canonical: find_existing(candidates, df_categoria_raw.columns) for canonical, candidates in col_map_categoria.items()}
    df_categoria = df_categoria_raw.rename(columns={v: k for k, v in mapped_cat.items() if v})
    if 'CBO' in df_categoria.columns and 'CBP' in df.columns:
        df_categoria['CBO'] = df_categoria['CBO'].astype(str).str.replace(r'\.0$', '', regex=True)
        cbo_to_categoria_map = df_categoria.set_index('CBO')['Categoria'].to_dict()
        df['CBP'] = df['CBP'].astype(str).str.replace(r'\.0$', '', regex=True)
        df['Categoria Profissional'] = df['CBP'].map(cbo_to_categoria_map).fillna('Não Mapeado')

df_condicoes = df_condicoes_raw.copy()
df_estabelecimentos = df_estabelecimentos_raw.copy()

if 'Municipio Solicitante' in df_estabelecimentos.columns and 'Municipio Solicitante' in df_condicoes.columns:
    df_estabelecimentos = pd.merge(df_estabelecimentos, df_condicoes[['Municipio Solicitante', 'CotaTotal']], on='Municipio Solicitante', how='left').fillna({'CotaTotal': 0})

ano_referencia = datetime.now().year
if 'Data_Solicitacao' in df.columns and 'Situação' in df.columns:
    df_ano_ref = df[(df['Data_Solicitacao'].dt.year == ano_referencia) & (~df['Situação'].str.lower().str.contains('cancelad', na=False))].copy()
    realizado_ano_ref = df_ano_ref.groupby('Municipio Solicitante').size().reset_index(name='Realizado_AnoRef')
    df_estabelecimentos['Num_Estabelecimentos'] = df_estabelecimentos.groupby('Municipio Solicitante')['Estabelecimento'].transform('count')
    df_estabelecimentos = pd.merge(df_estabelecimentos, realizado_ano_ref, on='Municipio Solicitante', how='left').fillna({'Realizado_AnoRef': 0})
    df_estabelecimentos['Realizado_AnoRef'] = df_estabelecimentos['Realizado_AnoRef'].astype(int)
    if 'CotaTotal' in df_estabelecimentos.columns and 'Num_Estabelecimentos' in df_estabelecimentos.columns:
        df_estabelecimentos['CotaMensal_Estabelecimento'] = ((df_estabelecimentos['CotaTotal'] - df_estabelecimentos['Realizado_AnoRef']) / 12 / df_estabelecimentos['Num_Estabelecimentos']).where(df_estabelecimentos['Num_Estabelecimentos'] > 0, 0).round(2)
        df_estabelecimentos['CotaMensal_Estabelecimento'] = df_estabelecimentos['CotaMensal_Estabelecimento'].apply(lambda x: max(x, 0))

cols_to_merge_final = [col for col in ['Municipio Solicitante', 'Monitor', 'Macrorregiao', 'Microrregiao'] if col in df_condicoes.columns]
if 'Municipio Solicitante' in df.columns and 'Municipio Solicitante' in df_condicoes.columns:
    df = pd.merge(df, df_condicoes[cols_to_merge_final], on='Municipio Solicitante', how='left')

# --- BARRA LATERAL DE FILTROS ---
st.sidebar.header("Filtros")
if 'Data_Solicitacao' in df.columns and not df['Data_Solicitacao'].dropna().empty:
    min_date_val = df['Data_Solicitacao'].dropna().min().date()
    max_date_val = df['Data_Solicitacao'].dropna().max().date()
    
    start_date = st.sidebar.date_input("Data de Início", min_date_val, min_value=min_date_val, max_value=max_date_val)
    end_date = st.sidebar.date_input("Data de Fim", max_date_val, min_value=start_date, max_value=max_date_val)
    
    start_date_dt = pd.to_datetime(start_date)
    end_date_dt = pd.to_datetime(end_date)
    
    df_filtered_final = df[df['Data_Solicitacao'].between(start_date_dt, end_date_dt)].copy()

    filters_config = [{'column': 'Situação', 'label': 'Status'}, {'column': 'Monitor', 'label': 'Monitor de Campo'}, {'column': 'Macrorregiao', 'label': 'Macrorregião'}, {'column': 'Microrregiao', 'label': 'Microrregião'}, {'column': 'Municipio Solicitante', 'label': 'Município'}, {'column': 'Estabelecimento', 'label': 'Estabelecimento'}, {'column': 'Especialidade', 'label': 'Especialidade'}, {'column': 'Categoria Profissional', 'label': 'Categoria Profissional'}, {'column': 'SolicitanteNome', 'label': 'Solicitante'}, {'column': 'NomeEspecialista', 'label': 'Especialista'}]
    for f in filters_config:
        if f['column'] in df_filtered_final.columns:
            options = get_filter_options(df_filtered_final, f['column'])
            if options:
                selection = st.sidebar.multiselect(f['label'], options=options, key=f['column'], placeholder=f"Filtrar por {f['label']}...")
                if selection:
                    df_filtered_final = df_filtered_final[df_filtered_final[f['column']].isin(selection)]
else:
    df_filtered_final = df.copy()

# --- CORPO PRINCIPAL DO DASHBOARD ---
fig_perf, fig_ts, fig_pie, fig_cat, fig_sol = None, None, None, None, None
df_tabela_perf, df_especialidade_tabela = pd.DataFrame(), pd.DataFrame()
concluido, percentual = 0, 0.0
casos_ubs, total_encaminhados, evitados, intencao_encaminhar = 0, 0, 0, 0
perc_ubs, perc_enc, perc_evitados = 0.0, 0.0, 0.0
df_performance_estab_filtrado = pd.DataFrame()
municipios_atendidos = 0
total_estabelecimentos_visiveis = 0

if not df_filtered_final.empty:
    if 'Municipio Solicitante' in df_filtered_final.columns:
        municipios_visiveis = df_filtered_final['Municipio Solicitante'].unique()
        estabelecimentos_visiveis_df = df_estabelecimentos[df_estabelecimentos['Municipio Solicitante'].isin(municipios_visiveis)]
        total_estabelecimentos_visiveis = estabelecimentos_visiveis_df['Estabelecimento'].nunique()
        municipios_atendidos = len(municipios_visiveis)

    st.subheader("Indicadores Chave de Operação (KPIs)")
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Total de Teleconsultorias", format_number(len(df_filtered_final)))
    if 'Data_Resposta' in df_filtered_final.columns and 'Data_Solicitacao' in df_filtered_final.columns and not df_filtered_final['Data_Resposta'].dropna().empty:
        df_filtered_final['Tempo_Resposta_Horas'] = (df_filtered_final['Data_Resposta'] - df_filtered_final['Data_Solicitacao']).dt.total_seconds() / 3600
        col2.metric("Média (horas) resposta", f"{df_filtered_final['Tempo_Resposta_Horas'].mean():.1f}")
    else:
        col2.metric("Média (horas) resposta", "N/D")
    if 'Concluida?' in df_filtered_final.columns:
        concluido = df_filtered_final['Concluida?'].str.contains('sim', na=False).sum()
        percentual = (concluido / len(df_filtered_final) * 100) if len(df_filtered_final) > 0 else 0
        col3.metric("Concluídas", f"{format_number(concluido)} ({percentual:.1f}%)")
    else:
        col3.metric("Concluídas", "N/D")
    col4.metric("Municípios Atendidos", municipios_atendidos)
    col5.metric("Total de Estabelecimentos", format_number(total_estabelecimentos_visiveis))

    st.markdown("---")
    st.subheader("Análise de Fluxo de Encaminhamentos")
    if 'Conduta' in df_filtered_final.columns and 'Inten.Encaminhamento' in df_filtered_final.columns:
        col_ubs, col_enc, col_evit = st.columns(3)
        df_filtered_final['Conduta'] = df_filtered_final['Conduta'].astype(str).str.lower()
        casos_ubs = df_filtered_final['Conduta'].str.contains('manter na unidade', na=False).sum()
        casos_enc_sec = df_filtered_final['Conduta'].str.contains('encaminhar niveis secundarios', na=False).sum()
        casos_enc_ter = df_filtered_final['Conduta'].str.contains('encaminhar niveis terciarios', na=False).sum()
        total_encaminhados = casos_enc_sec + casos_enc_ter
        total_conduta = casos_ubs + total_encaminhados
        if total_conduta > 0:
            perc_ubs, perc_enc = (casos_ubs / total_conduta * 100), (total_encaminhados / total_conduta * 100)
        col_ubs.metric("Casos Mantidos na UBS", f"{format_number(casos_ubs)} ({perc_ubs:.1f}%)")
        col_enc.metric("Casos Encaminhados", f"{format_number(total_encaminhados)} ({perc_enc:.1f}%)")
        intencao_encaminhar = df_filtered_final['Inten.Encaminhamento'].astype(str).str.lower().str.strip().isin(['sim']).sum()
        if intencao_encaminhar > 0:
            evitados = intencao_encaminhar - total_encaminhados
            perc_evitados = (evitados / intencao_encaminhar) * 100
            col_evit.metric("Encaminhamentos Evitados", f"{format_number(evitados)} ({perc_evitados:.1f}%)")
        else:
            col_evit.metric("Encaminhamentos Evitados", "N/D")
    else:
        st.warning("Colunas 'Conduta' e 'Inten.Encaminhamento' não encontradas para análise de fluxo.")

    st.markdown("---")
    st.header("Análise de Performance de Metas")
    if 'CotaMensal_Estabelecimento' in df_estabelecimentos.columns and 'Municipio Solicitante' in df_filtered_final.columns:
        realizado_estab = df_filtered_final.groupby('Estabelecimento').size().reset_index(name='Realizado_Periodo')
        df_performance_estab_filtrado = pd.merge(df_estabelecimentos, realizado_estab, on='Estabelecimento', how='left').fillna({'Realizado_Periodo': 0})
        df_performance_estab_filtrado = df_performance_estab_filtrado[df_performance_estab_filtrado['Municipio Solicitante'].isin(municipios_visiveis)]
        df_performance_estab_filtrado['Realizado_Periodo'] = df_performance_estab_filtrado['Realizado_Periodo'].astype(int)
        st.subheader("Gráfico Realizado vs. Meta por Estabelecimento")
        if not df_performance_estab_filtrado.empty:
            fig_perf = px.bar(df_performance_estab_filtrado, x='Estabelecimento', y=['Realizado_Periodo', 'CotaMensal_Estabelecimento'], title='Comparativo de Realizado vs. Meta por Estabelecimento', barmode='group')
            st.plotly_chart(fig_perf, use_container_width=True)
        st.subheader("Tabela de Performance por Estabelecimento")
        if 'CotaMensal_Estabelecimento' in df_performance_estab_filtrado.columns and df_performance_estab_filtrado['CotaMensal_Estabelecimento'].sum() > 0:
             df_performance_estab_filtrado['Percentual Atingido'] = (df_performance_estab_filtrado['Realizado_Periodo'] / df_performance_estab_filtrado['CotaMensal_Estabelecimento'] * 100).fillna(0)
        else:
             df_performance_estab_filtrado['Percentual Atingido'] = 0.0
        def style_performance(v):
            if pd.isna(v): return ''
            return 'background-color: #f8d7da;' if v < 50 else ('background-color: #fff3cd;' if v < 90 else 'background-color: #d4edda;')
        cols_perf = ['Municipio Solicitante', 'Estabelecimento', 'CotaMensal_Estabelecimento', 'Realizado_Periodo', 'Percentual Atingido']
        df_tabela_perf = df_performance_estab_filtrado[cols_perf].copy()
        st.dataframe(df_tabela_perf.style.map(style_performance, subset=['Percentual Atingido']).format({'Percentual Atingido': '{:.1f}%', 'CotaMensal_Estabelecimento': '{:.2f}'}), use_container_width=True)

    st.markdown("---")
    st.header("Análises Descritivas")
    st.subheader("Evolução Mensal")
    df_ts = df_filtered_final.set_index('Data_Solicitacao').resample('MS').size().reset_index(name='Quantidade')
    df_ts['Mês'] = df_ts['Data_Solicitacao'].dt.strftime('%b/%Y')
    fig_ts = px.line(df_ts, x='Mês', y='Quantidade', title='Evolução Mensal', markers=True, text='Quantidade')
    fig_ts.update_traces(textposition='top center')
    st.plotly_chart(fig_ts, use_container_width=True)

    st.subheader("Distribuição por Especialidade")
    if 'Especialidade' in df_filtered_final.columns:
        esp_count = df_filtered_final['Especialidade'].value_counts().reset_index(name='Quantidade')
        esp_count = esp_count.rename(columns={'index': 'Especialidade'})
        fig_pie = px.pie(esp_count, names='Especialidade', values='Quantidade', title='Distribuição por Especialidade', hole=0.3)
        st.plotly_chart(fig_pie, use_container_width=True)
        df_especialidade_tabela = esp_count.copy()

    col_desc1, col_desc2 = st.columns(2)
    with col_desc1:
        st.subheader("Distribuição por Categoria Profissional")
        if 'Categoria Profissional' in df_filtered_final.columns:
            cat_count = df_filtered_final['Categoria Profissional'].value_counts().reset_index(name='Quantidade')
            cat_count = cat_count.rename(columns={'index': 'Categoria Profissional'})
            fig_cat = px.bar(cat_count, x='Categoria Profissional', y='Quantidade', title='Por Categoria', text_auto=True)
            st.plotly_chart(fig_cat, use_container_width=True)
    with col_desc2:
        st.subheader("Distribuição por Solicitante")
        if 'SolicitanteNome' in df_filtered_final.columns:
            solicitante_count = df_filtered_final['SolicitanteNome'].value_counts().nlargest(20).reset_index(name='Quantidade')
            solicitante_count = solicitante_count.rename(columns={'index': 'SolicitanteNome'})
            fig_sol = px.bar(solicitante_count, x='SolicitanteNome', y='Quantidade', title='Top 20 Solicitantes', text_auto=True)
            st.plotly_chart(fig_sol, use_container_width=True)

    st.markdown("---")
    st.header("Detalhamento e Exportação")
    if 'Municipio Solicitante' in df_filtered_final.columns:
        st.subheader("Gerador de Relatórios por Município")
        municipio_relatorio = st.selectbox(
            "Selecione um município para o relatório detalhado:",
            options=sorted(df_filtered_final['Municipio Solicitante'].unique()),
            index=None,
            placeholder="Escolha um município..."
        )
        if municipio_relatorio:
            df_sumario = df_performance_estab_filtrado[df_performance_estab_filtrado['Municipio Solicitante'] == municipio_relatorio]
            df_detalhes = df_filtered_final[df_filtered_final['Municipio Solicitante'] == municipio_relatorio]
            st.download_button(
                label=f"📥 Download Relatório de {municipio_relatorio}",
                data=to_excel_report_bytes(df_sumario, df_detalhes),
                file_name=f"Relatorio_{municipio_relatorio.replace(' ', '_')}.xlsx",
                use_container_width=True
            )

    st.subheader("Dados Gerais Filtrados")
    cols_show = [col for col in ['Data_Solicitacao', 'Municipio Solicitante', 'Estabelecimento', 'Especialidade', 'SolicitanteNome', 'Categoria Profissional', 'Situação', 'Monitor'] if col in df_filtered_final.columns]
    st.dataframe(df_filtered_final[cols_show], use_container_width=True)
    st.download_button(label="📥 Download Dados Filtrados", data=to_excel_bytes_generic(df_filtered_final[cols_show]), file_name="Relatorio_Geral.xlsx", use_container_width=True)

    st.markdown("---")
    st.header("Exportar Relatório em PDF")

    def generate_html_for_pdf(start_date, end_date, kpis_dict, observacao_fluxo, df_perf, figures):
        def fig_to_base64(fig):
            if fig is None: return None
            try:
                engine_config = {'chromium_args': ['--no-sandbox', '--headless', '--disable-gpu', '--disable-dev-shm-usage']}
                img_bytes = fig.to_image(format="png", width=900, scale=1.5, engine_config=engine_config)
                return base64.b64encode(img_bytes).decode()
            except Exception as e:
                st.error(f"Erro ao converter gráfico para o PDF: {e}")
                return None
        
        df_perf_html = df_perf.to_html(index=False, classes='styled-table', border=0)
        
        kpi_html = '<div class="kpi-container">'
        for k, v in kpis_dict.items():
            kpi_html += f'<div class="kpi"><div class="kpi-value">{v}</div><div class.kpi-label">{k}</div></div>'
        kpi_html += '</div>'
        if observacao_fluxo:
            kpi_html += f'<div class="observacao">{observacao_fluxo}</div>'

        html = f"""
        <html><head><meta charset="UTF-8">
            <style>
                /* Estilos melhorados para o PDF */
                body {{ font-family: 'Helvetica', sans-serif; font-size: 10px; }}
                h1 {{ text-align: center; color: #33ac47; }}
                h2 {{ color: #33ac47; border-bottom: 1px solid #ddd; padding-bottom: 5px; margin-top: 20px;}}
                .styled-table {{ border-collapse: collapse; width: 100%; font-size: 9px; margin-bottom: 20px;}}
                .styled-table th, .styled-table td {{ border: 1px solid #ddd; padding: 6px; text-align: left;}}
                .styled-table th {{ background-color: #f2f2f2; }}
                .chart-container {{ page-break-inside: avoid; text-align: center; margin-top: 25px; }}
                img {{ max-width: 100%; }}
            </style>
        </head><body>
            <h1>Relatório de Teleconsultorias</h1>
            <p>Período: {start_date.strftime('%d/%m/%Y')} a {end_date.strftime('%d/%m/%Y')}</p>
            <h2>Indicadores Chave</h2>{kpi_html}
            <h2>Performance por Estabelecimento</h2>{df_perf_html}
        """
        charts_html = ""
        for title, fig in figures.items():
            img_b64 = fig_to_base64(fig)
            if img_b64:
                charts_html += f'<div class="chart-container"><h2>{title}</h2><img src="data:image/png;base64,{img_b64}"></div>'
        html += charts_html
        html += "</body></html>"
        return html

    if st.button("Gerar Relatório PDF"):
        with st.spinner("Gerando PDF..."):
            kpis = {
                "Total de Consultorias": format_number(len(df_filtered_final)),
                "Média Resp. (h)": f"{df_filtered_final['Tempo_Resposta_Horas'].mean():.1f}" if 'Tempo_Resposta_Horas' in df_filtered_final else "N/D",
                "Concluídas": f"{format_number(concluido)} ({percentual:.1f}%)",
                "Municípios Atendidos": municipios_atendidos
            }
            obs = f"De {format_number(intencao_encaminhar)} intenções, {format_number(evitados)} encaminhamentos foram evitados." if intencao_encaminhar > 0 else ""
            
            figures_for_pdf = {
                "Comparativo de Realizado vs. Meta": fig_perf,
                "Evolução Mensal": fig_ts,
                "Distribuição por Especialidade": fig_pie,
                "Distribuição por Categoria": fig_cat,
                "Top 20 Solicitantes": fig_sol
            }

            html_content = generate_html_for_pdf(start_date_dt, end_date_dt, kpis, obs, df_tabela_perf, figures_for_pdf)
            pdf_bytes = HTML(string=html_content).write_pdf()
            
            st.download_button(
                label="📥 Download do Relatório PDF",
                data=pdf_bytes,
                file_name=f"Relatorio_{datetime.now().strftime('%Y%m%d')}.pdf",
                mime="application/pdf",
                use_container_width=True
            )

st.caption(f"Atualizado em {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")