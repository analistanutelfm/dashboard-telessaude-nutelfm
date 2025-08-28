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

# --- 2. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(layout="wide", page_title="Dashboard de Teleconsultorias")
st.title("Dashboard de Gestão e Análise de Teleconsultorias")

# --- 3. FUNÇÕES AUXILIARES ---

# ### ALTERAÇÃO: A função format_number agora usa f-string ###
def format_number(n):
    """Formata um número com ponto como separador de milhar."""
    if pd.isna(n):
        return 'N/D'
    try:
        # Usa uma f-string para formatar com vírgulas e depois substitui por pontos.
        # Isso funciona em qualquer sistema, sem depender do locale.
        return f"{int(n):,}".replace(',', '.')
    except (ValueError, TypeError):
        return str(n)

@st.cache_data
def load_excel_upload(file):
    try: return pd.read_excel(file)
    except Exception as e: st.error(f"Erro ao ler arquivo Excel do upload: {e}"); return None
@st.cache_data
def load_local_data(path):
    if not os.path.exists(path): st.error(f"ERRO: Arquivo '{path}' não encontrado."); return None
    try: return pd.read_excel(path)
    except Exception as e: st.error(f"Erro ao ler arquivo local '{path}': {e}"); return None
def find_existing(col_list, df_cols):
    for candidate in col_list:
        for c in df_cols:
            if str(c).strip().lower() == str(candidate).strip().lower(): return c
    return None
def get_filter_options(df, col):
    if col in df.columns: return sorted(df[col].dropna().unique())
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
            for idx, col in enumerate(df_sheet.columns):
                series = df_sheet[col]
                if not series.empty:
                    max_len = max(series.astype(str).map(len).max(), len(str(col))) + 2
                    worksheet.set_column(idx, idx, max_len)
    return output.getvalue()

# --- 4. CARREGAMENTO E PREPARAÇÃO DOS DADOS ---
df_condicoes_raw = load_local_data('condicoes.xlsx')
df_estabelecimentos_raw = load_local_data('estabelecimentos.xlsx')
df_categoria_raw = load_local_data('categoria.xlsx')
uploaded_file = st.file_uploader("Faça upload do arquivo Excel principal de teleconsultorias (xls/xlsx):", type=["xls", "xlsx"])

if uploaded_file is None or df_condicoes_raw is None or df_estabelecimentos_raw is None or df_categoria_raw is None:
    st.warning("Por favor, faça o upload do arquivo principal e verifique se os arquivos de apoio (condicoes, estabelecimentos, categoria) estão na mesma pasta.")
    st.stop()

df_raw = load_excel_upload(uploaded_file)
if df_raw is None:
    st.stop()

col_map_full = {'Municipio Solicitante': ['Municipio Solicitante', 'Município Solicitante', 'Municipio'], 'Estabelecimento': ['Estabelecimento', 'Estabelecimento do Solicitante', 'Estabelecimento Solicitante', 'Unidade de Saúde'], 'Especialidade': ['Especialidade', 'Especialty', 'Specialty'], 'SolicitanteNome': ['Solicitante', 'Nome do Solicitante', 'Profissional Solicitante'], 'NomeEspecialista': ['Nome do Especialista', 'Nome do Especialista Teleconsultor', 'Especialista'], 'CBP': ['CBP', 'cbo'], 'Conduta': ['Conduta'], 'Inten.Encaminhamento': ['Inten.Encaminhamento'], 'Concluida?': ['Concluída?', 'Concluida?'], 'Data_Solicitacao': ['Data Solicitação', 'Data Solicitacao', 'Data_Solicitacao', 'Dt.Criação'], 'Data_Resposta': ['Data Resposta', 'Data_Resposta', 'Dt.1ª resposta'], 'Situação': ['Situação', 'Situacao', 'Status']}
mapped = {canonical: find_existing(candidates, df_raw.columns) for canonical, candidates in col_map_full.items()}
df = df_raw.rename(columns={v: k for k, v in mapped.items() if v})

for dcol in ['Data_Solicitacao', 'Data_Resposta']:
    if dcol in df.columns:
        df[dcol] = pd.to_datetime(df[dcol], errors='coerce', dayfirst=True)
if 'Concluida?' in df.columns:
    df['Concluida?'] = df['Concluida?'].astype(str).str.lower().str.strip()

col_map_categoria = {'CBO': ['CBO'], 'Categoria': ['Categoria']}
mapped_cat = {canonical: find_existing(candidates, df_categoria_raw.columns) for canonical, candidates in col_map_categoria.items()}
df_categoria = df_categoria_raw.rename(columns={v: k for k, v in mapped_cat.items() if v})
df_categoria['CBO'] = df_categoria['CBO'].astype(str).str.replace(r'\.0$', '', regex=True)
cbo_to_categoria_map = df_categoria.set_index('CBO')['Categoria'].to_dict()
if 'CBP' in df.columns:
    df['CBP'] = df['CBP'].astype(str).str.replace(r'\.0$', '', regex=True)
    df['Categoria Profissional'] = df['CBP'].map(cbo_to_categoria_map).fillna('Não Mapeado')

col_map_condicoes = {'Municipio Solicitante': ['MUNICÍPIOS', 'Municipio Solicitante'], 'CotaTotal': ['Cota total', 'Cota Total'], 'Monitor': ['Monitor(a) de Campo Responsável', 'Monitor'], 'Macrorregiao': ['Macrorregião de Saúde'], 'Microrregiao': ['Microrregião de Saúde']}
mapped_cond = {canonical: find_existing(candidates, df_condicoes_raw.columns) for canonical, candidates in col_map_condicoes.items()}
df_condicoes = df_condicoes_raw.rename(columns={v: k for k, v in mapped_cond.items() if v})

col_map_estab = {'Municipio Solicitante': ['Município', 'Municipio Solicitante'], 'Estabelecimento': ['Unidade de Saúde', 'Estabelecimento']}
mapped_estab = {canonical: find_existing(candidates, df_estabelecimentos_raw.columns) for canonical, candidates in col_map_estab.items()}
df_estabelecimentos = df_estabelecimentos_raw.rename(columns={v: k for k, v in mapped_estab.items() if v})

df_estabelecimentos = pd.merge(df_estabelecimentos, df_condicoes[['Municipio Solicitante', 'CotaTotal']], on='Municipio Solicitante', how='left').fillna({'CotaTotal': 0})

ano_referencia = 2024
df_ano_ref = df[(df['Data_Solicitacao'].dt.year == ano_referencia) & (~df['Situação'].str.lower().str.contains('cancelad', na=False))].copy()
realizado_ano_ref = df_ano_ref.groupby('Municipio Solicitante').size().reset_index(name='Realizado_AnoRef')

df_estabelecimentos['Num_Estabelecimentos'] = df_estabelecimentos.groupby('Municipio Solicitante')['Estabelecimento'].transform('count')
df_estabelecimentos = pd.merge(df_estabelecimentos, realizado_ano_ref, on='Municipio Solicitante', how='left').fillna({'Realizado_AnoRef': 0})
df_estabelecimentos['Realizado_AnoRef'] = df_estabelecimentos['Realizado_AnoRef'].astype(int)
df_estabelecimentos['CotaMensal_Estabelecimento'] = ((df_estabelecimentos['CotaTotal'] - df_estabelecimentos['Realizado_AnoRef']) / 12 / df_estabelecimentos['Num_Estabelecimentos']).where(df_estabelecimentos['Num_Estabelecimentos'] > 0, 0).round(2)
df_estabelecimentos['CotaMensal_Estabelecimento'] = df_estabelecimentos['CotaMensal_Estabelecimento'].apply(lambda x: max(x, 0))

cols_to_merge_final = [col for col in ['Municipio Solicitante', 'Monitor', 'Macrorregiao', 'Microrregiao'] if col in df_condicoes.columns]
df = pd.merge(df, df_condicoes[cols_to_merge_final], on='Municipio Solicitante', how='left')

# --- 5. BARRA LATERAL DE FILTROS ---
st.sidebar.header("Filtros")

# Filtro de Data Principal
st.sidebar.markdown("##### Período Principal de Análise")
min_date_val, max_date_val = (df['Data_Solicitacao'].dropna().min(), df['Data_Solicitacao'].dropna().max())
start_default, end_default = (min_date_val.date(), max_date_val.date()) if pd.notna(min_date_val) else (datetime.today().date(), datetime.today().date())
col_data_inicio, col_data_fim = st.sidebar.columns(2)
with col_data_inicio:
    start_date = st.date_input("Data de Início", value=start_default, min_value=start_default, max_value=end_default, key="start_date")
with col_data_fim:
    end_date = st.date_input("Data de Fim", value=end_default, min_value=start_date, max_value=end_default, key="end_date")

# Aplica todos os filtros dinâmicos primeiro
st.sidebar.markdown("---")
df_base_filtrado = df.copy() # Começa com o dataframe completo e vai aplicando os filtros
status_selecionado = []
if 'Situação' in df.columns:
    todos_status = sorted(df['Situação'].dropna().unique())
    status_selecionado = st.sidebar.multiselect("Status", options=todos_status, placeholder="Filtrar por status")
    if status_selecionado:
        df_base_filtrado = df_base_filtrado[df_base_filtrado['Situação'].isin(status_selecionado)]
st.sidebar.markdown("---")
filters_config = [{'column': 'Monitor', 'label': 'Monitor de Campo'}, {'column': 'Macrorregiao', 'label': 'Macrorregião de Saúde'}, {'column': 'Microrregiao', 'label': 'Microrregião de Saúde'}, {'column': 'Municipio Solicitante', 'label': 'Município'}, {'column': 'Estabelecimento', 'label': 'Estabelecimento'}, {'column': 'Especialidade', 'label': 'Especialidade'}, {'column': 'Categoria Profissional', 'label': 'Categoria Profissional'}, {'column': 'SolicitanteNome', 'label': 'Nome do Solicitante'}, {'column': 'NomeEspecialista', 'label': 'Nome do Especialista'}]
for f in filters_config:
    if f['column'] in df_base_filtrado.columns:
        options = get_filter_options(df_base_filtrado, f['column'])
        if options:
            selection = st.sidebar.multiselect(f['label'], options=options, key=f['column'], placeholder="Selecione as opções")
            if selection:
                df_base_filtrado = df_base_filtrado[df_base_filtrado[f['column']].isin(selection)]

# Cria o dataframe final para o dashboard principal, aplicando o filtro de data principal
start_date_dt = pd.to_datetime(start_date)
end_date_dt = pd.to_datetime(end_date)
df_filtered_final = df_base_filtrado[df_base_filtrado['Data_Solicitacao'].between(start_date_dt, end_date_dt)].copy()


# --- 6. CORPO PRINCIPAL DO DASHBOARD ---
fig_perf, fig_ts, fig_pie, fig_cat, fig_sol = None, None, None, None, None
df_tabela_perf, df_especialidade_tabela = pd.DataFrame(), pd.DataFrame()
municipios_visiveis = df_filtered_final['Municipio Solicitante'].unique()
estabelecimentos_visiveis_df = df_estabelecimentos[df_estabelecimentos['Municipio Solicitante'].isin(municipios_visiveis)]
total_estabelecimentos_visiveis = estabelecimentos_visiveis_df['Estabelecimento'].nunique()

st.subheader("Indicadores Chave de Operação (KPIs)")
col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Total de Teleconsultorias", format_number(len(df_filtered_final)))
if 'Data_Resposta' in df_filtered_final.columns and not df_filtered_final['Data_Resposta'].dropna().empty:
    df_filtered_final['Tempo_Resposta_Horas'] = (df_filtered_final['Data_Resposta'] - df_filtered_final['Data_Solicitacao']).dt.total_seconds() / 3600
    col2.metric("Média (horas) resposta", f"{df_filtered_final['Tempo_Resposta_Horas'].mean():.1f}")
else:
    col2.metric("Média (horas) resposta", "N/D")
if 'Concluida?' in df_filtered_final.columns and not df_filtered_final.empty:
    concluido = df_filtered_final['Concluida?'].str.contains('sim', na=False).sum()
    percentual = (concluido / len(df_filtered_final) * 100) if len(df_filtered_final) > 0 else 0
    col3.metric("Concluídas", f"{format_number(concluido)} ({percentual:.1f}%)")
else:
    col3.metric("Concluídas", "N/D")
col4.metric("Municípios Atendidos", df_filtered_final['Municipio Solicitante'].nunique())
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
        col_ubs.metric("Casos Mantidos na UBS", f"{casos_ubs} ({perc_ubs:.1f}%)")
        col_enc.metric("Casos Encaminhados", f"{total_encaminhados} ({perc_enc:.1f}%)")
    else:
        col_ubs.metric("Casos Mantidos na UBS", "0 (0.0%)"); col_enc.metric("Casos Encaminhados", "0 (0.0%)")
    intencao_encaminhar = df_filtered_final['Inten.Encaminhamento'].astype(str).str.lower().str.strip().isin(['sim']).sum()
    if intencao_encaminhar > 0:
        evitados = intencao_encaminhar - total_encaminhados
        perc_evitados = (evitados / intencao_encaminhar) * 100
        col_evit.metric("Encaminhamentos Evitados", f"{evitados} ({perc_evitados:.1f}%)")
    else:
        col_evit.metric("Encaminhamentos Evitados", "N/D")
else:
    st.warning("A Análise de Fluxo não pode ser exibida. Verifique se as colunas 'Conduta' e 'Inten.Encaminhamento' existem no arquivo carregado.")

st.markdown("---")
st.header("Análise de Performance de Metas")
if 'CotaMensal_Estabelecimento' in df_estabelecimentos.columns:
    municipios_filtrados = df_filtered_final['Municipio Solicitante'].unique()
    estabelecimentos_base_df = df_estabelecimentos[df_estabelecimentos['Municipio Solicitante'].isin(municipios_filtrados)]
    realizado_estab = df_filtered_final.groupby('Estabelecimento').size().reset_index(name='Realizado_Periodo')
    df_performance_estab_filtrado = pd.merge(estabelecimentos_base_df, realizado_estab, on='Estabelecimento', how='left').fillna({'Realizado_Periodo': 0})
    df_performance_estab_filtrado['Realizado_Periodo'] = df_performance_estab_filtrado['Realizado_Periodo'].astype(int)
    st.subheader("Gráfico Realizado vs. Meta por Estabelecimento")
    if not df_performance_estab_filtrado.empty:
        fig_perf = go.Figure()
        fig_perf.add_trace(go.Bar(name='Realizado no Período', x=df_performance_estab_filtrado['Estabelecimento'], y=df_performance_estab_filtrado['Realizado_Periodo'], marker_color='#0d6efd'))
        fig_perf.add_trace(go.Bar(name='Cota Mensal', x=df_performance_estab_filtrado['Estabelecimento'], y=df_performance_estab_filtrado['CotaMensal_Estabelecimento'], marker_color='#adb5bd'))
        fig_perf.update_layout(barmode='group', xaxis_tickangle=-45, title_text='Comparativo de Realizado vs. Meta por Estabelecimento')
        st.plotly_chart(fig_perf, use_container_width=True)
    else:
        st.info("Nenhum estabelecimento encontrado para os filtros selecionados.")
    st.subheader("Tabela de Performance por Estabelecimento")
    df_performance_estab_filtrado['Percentual Atingido'] = (df_performance_estab_filtrado['Realizado_Periodo'] / df_performance_estab_filtrado['CotaMensal_Estabelecimento'] * 100).where(df_performance_estab_filtrado['CotaMensal_Estabelecimento'] > 0, 0)
    def style_performance(v):
        if pd.isna(v): return ''
        return 'background-color: #f8d7da; color: #721c24;' if v < 50 else ('background-color: #fff3cd; color: #856404;' if v < 90 else 'background-color: #d4edda; color: #155724;')
    cols_perf = ['Municipio Solicitante', 'Estabelecimento', 'CotaMensal_Estabelecimento', 'Realizado_Periodo', 'Percentual Atingido']
    df_tabela_perf = df_performance_estab_filtrado[cols_perf].copy()
    df_tabela_perf.reset_index(drop=True, inplace=True)
    df_tabela_perf.index += 1
    st.dataframe(df_tabela_perf.style.applymap(style_performance, subset=['Percentual Atingido']).format({'Percentual Atingido': '{:.1f}%', 'CotaMensal_Estabelecimento': '{:.2f}'}), use_container_width=True)
else:
    st.warning("A Análise de Performance não pode ser exibida.")

st.markdown("---")
st.header("Análises Descritivas e Distribuições")
st.subheader("Evolução Mensal das Teleconsultorias")

# Novo filtro de data dedicado para o gráfico de evolução
col_evol_1, col_evol_2 = st.columns(2)
with col_evol_1:
    start_date_evol = st.date_input("Data de Início da Evolução", value=start_default, min_value=start_default, max_value=end_default, key="start_date_evol")
with col_evol_2:
    end_date_evol = st.date_input("Data de Fim da Evolução", value=end_default, min_value=start_date_evol, max_value=end_default, key="end_date_evol")

start_date_evol_dt = pd.to_datetime(start_date_evol)
end_date_evol_dt = pd.to_datetime(end_date_evol)
df_evolucao = df_base_filtrado[df_base_filtrado['Data_Solicitacao'].between(start_date_evol_dt, end_date_evol_dt)].copy()

if not df_evolucao.empty:
    date_range_full = pd.date_range(start=start_date_evol_dt, end=end_date_evol_dt, freq='MS')
    df_ts = df_evolucao.set_index('Data_Solicitacao').resample('MS').size().reindex(date_range_full, fill_value=0).reset_index(name='Quantidade')
    df_ts.rename(columns={'index': 'Data_Solicitacao'}, inplace=True)
    df_ts['Mês'] = df_ts['Data_Solicitacao'].dt.strftime('%Y-%m')
    fig_ts = px.line(df_ts, x='Mês', y='Quantidade', text='Quantidade', title='Evolução Mensal das Teleconsultorias', markers=True, color_discrete_sequence=['#fd7e14'])
    fig_ts.update_traces(textposition='top center')
    st.plotly_chart(fig_ts, use_container_width=True)
else:
    st.info("Sem dados de evolução para o período e filtros selecionados.")

st.subheader("Distribuição por Especialidade")
if 'Especialidade' in df_filtered_final.columns and not df_filtered_final.empty:
    esp_count = df_filtered_final['Especialidade'].value_counts().reset_index(name='count')
    df_pie_data = esp_count
    if 'Tempo_Resposta_Horas' in df_filtered_final.columns:
        avg_resp = df_filtered_final.groupby('Especialidade')['Tempo_Resposta_Horas'].mean().round(1).reset_index(name='avg_resp_horas')
        df_pie_data = pd.merge(esp_count, avg_resp, on='Especialidade')
        df_pie_data['label'] = df_pie_data.apply(lambda row: f"{row['Especialidade']} ({row['avg_resp_horas']}h)", axis=1)
    else:
        df_pie_data['label'] = df_pie_data['Especialidade']
    fig_pie = px.pie(df_pie_data, names='label', values='count', title='Distribuição por Especialidade e Média de Resposta (horas)', hole=0.3, color_discrete_sequence=px.colors.qualitative.Pastel)
    fig_pie.update_traces(textposition='inside', textinfo='percent')
    st.plotly_chart(fig_pie, use_container_width=True)
    df_especialidade_tabela = df_pie_data.copy()
    df_especialidade_tabela.reset_index(drop=True, inplace=True)
    df_especialidade_tabela.index += 1
    st.dataframe(df_especialidade_tabela[['label', 'count']].rename(columns={'label': 'Especialidade (Média de Resposta)', 'count': 'Quantidade'}), use_container_width=True)
else:
    st.info("Sem dados de Especialidade para exibir.")

col_desc1, col_desc2 = st.columns(2)
with col_desc1:
    st.subheader("Distribuição por Categoria Profissional")
    if 'Categoria Profissional' in df_filtered_final.columns and not df_filtered_final['Categoria Profissional'].dropna().empty:
        cat_count = df_filtered_final['Categoria Profissional'].value_counts().reset_index()
        fig_cat = px.bar(cat_count, x='Categoria Profissional', y='count', title='Teleconsultorias por Categoria', labels={'count':'Quantidade'}, color_discrete_sequence=['#198754'])
        st.plotly_chart(fig_cat, use_container_width=True)
    else:
        st.info("Sem dados de Categoria Profissional para exibir.")
with col_desc2:
    st.subheader("Distribuição por Solicitante")
    if 'SolicitanteNome' in df_filtered_final.columns and not df_filtered_final['SolicitanteNome'].dropna().empty:
        solicitante_count = df_filtered_final['SolicitanteNome'].value_counts().reset_index()
        fig_sol = px.bar(solicitante_count, x='SolicitanteNome', y='count', title='Teleconsultorias por Solicitante', labels={'count':'Quantidade', 'SolicitanteNome': 'Nome do Solicitante'}, color_discrete_sequence=['#6f42c1'])
        st.plotly_chart(fig_sol, use_container_width=True)
    else:
        st.info("Sem dados de Solicitantes para exibir.")

# --- 7. DETALHAMENTO E EXPORTAÇÃO DE DADOS ---
st.markdown("---")
st.header("Detalhamento e Exportação de Dados")
st.subheader("Gerador de Relatórios por Município")
municipios_disponiveis = sorted(df_filtered_final['Municipio Solicitante'].unique())
if not municipios_disponiveis:
    st.info("Nenhum município com dados no período selecionado para gerar relatório.")
else:
    municipio_relatorio = st.selectbox("Selecione um município para o relatório detalhado:", options=municipios_disponiveis, index=None, placeholder="Escolha um município")
    if municipio_relatorio:
        df_sumario_relatorio = df_performance_estab_filtrado[df_performance_estab_filtrado['Municipio Solicitante'] == municipio_relatorio].copy()
        df_detalhes_relatorio = df_filtered_final[df_filtered_final['Municipio Solicitante'] == municipio_relatorio].copy()
        cols_summary = [col for col in ['Municipio Solicitante', 'Estabelecimento', 'CotaMensal_Estabelecimento', 'Realizado_Periodo', 'Percentual Atingido'] if col in df_sumario_relatorio.columns]
        df_sumario_relatorio = df_sumario_relatorio[cols_summary]
        cols_details = [col for col in ['Data_Solicitacao', 'Municipio Solicitante', 'Estabelecimento', 'Especialidade', 'SolicitanteNome', 'Categoria Profissional', 'Situação', 'Monitor', 'Conduta', 'Inten.Encaminhamento'] if col in df_detalhes_relatorio.columns]
        df_detalhes_relatorio = df_detalhes_relatorio[cols_details]
        excel_bytes = to_excel_report_bytes(df_sumario_relatorio, df_detalhes_relatorio)
        st.download_button(label=f"📥 Download Relatório de {municipio_relatorio}", data=excel_bytes, file_name=f"Relatorio_{municipio_relatorio.replace(' ', '_')}.xlsx", mime="application/vnd.openxmlformats-officedocument.sheet", use_container_width=True)

st.subheader("Detalhamento Geral das Teleconsultorias Filtradas")
cols_show = [col for col in ['Data_Solicitacao', 'Municipio Solicitante', 'Estabelecimento', 'Especialidade', 'SolicitanteNome', 'Categoria Profissional', 'Situação', 'Monitor'] if col in df_filtered_final.columns]
if not df_filtered_final.empty:
    df_detalhe_geral = df_filtered_final[cols_show].copy()
    df_detalhe_geral.reset_index(drop=True, inplace=True)
    df_detalhe_geral.index += 1
    st.dataframe(df_detalhe_geral, use_container_width=True)
    st.download_button(label="📥 Download dos Dados Filtrados (Geral)", data=to_excel_bytes_generic(df_detalhe_geral), file_name="Relatorio_Geral_Teleconsultorias.xlsx", mime="application/vnd.openxmlformats-officedocument.sheet")

st.markdown("---")
st.header("Exportar Relatório em PDF")

def generate_html_for_pdf(start_date, end_date, kpis, df_perf, figures, df_spec):
    """Gera uma string HTML completa para o relatório PDF."""
    def fig_to_base64(fig):
        if fig is None: return None
        try:
            img_bytes = fig.to_image(format="png", width=800, height=450, engine="kaleido")
            return base64.b64encode(img_bytes).decode()
        except Exception as e:
            st.warning(f"Não foi possível converter um gráfico para o PDF. Erro: {e}")
            return None
    df_perf_formatted = df_perf.copy()
    if 'Percentual Atingido' in df_perf_formatted.columns:
        df_perf_formatted['Percentual Atingido'] = df_perf_formatted['Percentual Atingido'].map('{:.1f}%'.format)
    df_perf_html = df_perf_formatted.to_html(index=True, classes='styled-table', border=0)
    df_spec_html = df_spec.to_html(index=True, classes='styled-table', border=0) if df_spec is not None and not df_spec.empty else ""
    html = f"""
    <html><head><meta charset="UTF-8">
        <style>
            @page {{ size: A4 portrait; margin: 1.0cm; }}
            body {{ font-family: 'Helvetica', sans-serif; color: #333; font-size: 10px;}}
            h1 {{ text-align: center; color: #0056b3; font-size: 20px;}}
            h2 {{ color: #0056b3; border-bottom: 1px solid #0056b3; padding-bottom: 5px; margin-top: 25px; font-size: 14px;}}
            .periodo {{ text-align: center; font-style: italic; color: #555; }}
            .kpi-container {{ display: flex; justify-content: space-around; padding: 10px; background-color: #f8f9fa; border-radius: 5px; margin-bottom: 20px; border: 1px solid #dee2e6; }}
            .kpi {{ text-align: center; }}
            .kpi-value {{ font-size: 18px; font-weight: bold; }}
            .kpi-label {{ font-size: 10px; color: #6c757d; }}
            .styled-table {{ border-collapse: collapse; margin: 15px 0; font-size: 8px; width: 100%; table-layout: fixed; }}
            .styled-table thead tr {{ background-color: #0056b3; color: #ffffff; text-align: center; }}
            .styled-table th, .styled-table td {{ padding: 6px 8px; border: 1px solid #ddd; word-wrap: break-word; text-align: left; }}
            .styled-table td:nth-child(n+3) {{ text-align: center; }}
            .styled-table tbody tr:nth-of-type(even) {{ background-color: #f3f3f3; }}
            .chart-container {{ page-break-before: always; text-align: center; margin-top: 20px; }}
            img {{ max-width: 100%; height: auto; }}
        </style>
    </head><body>
        <h1>Relatório de Análise de Teleconsultorias</h1>
        <p class="periodo">Período: {start_date.strftime('%d/%m/%Y')} a {end_date.strftime('%d/%m/%Y')}</p>
        <h2>Indicadores Chave de Operação</h2>
        <div class="kpi-container">{''.join([f'<div class="kpi"><div class="kpi-value">{v}</div><div class="kpi-label">{k}</div></div>' for k, v in kpis.items()])}</div>
        <h2>Performance por Estabelecimento</h2>
        {df_perf_html}
    """
    charts_html = ""
    for title, fig_data in figures.items():
        if fig_data is not None and fig_data.get('fig') is not None:
            fig = fig_data['fig']
            df_table = fig_data.get('table')
            img_b64 = fig_to_base64(fig)
            if img_b64:
                charts_html += f'<div class="chart-container"><h2>{title}</h2><img src="data:image/png;base64,{img_b64}">'
                if df_table is not None and not df_table.empty:
                    charts_html += df_table.to_html(index=True, classes='styled-table', border=0)
                charts_html += '</div>'
    html += charts_html
    html += "</body></html>"
    return html

if st.button("Gerar Relatório PDF"):
    if df_filtered_final.empty:
        st.warning("Não há dados filtrados para gerar o relatório PDF.")
    else:
        try:
            with st.spinner("Gerando seu relatório PDF, por favor aguarde..."):
                kpis_for_pdf = {
                    "Total de Consultorias": format_number(len(df_filtered_final)),
                    "Média Resp. (h)": f"{df_filtered_final['Tempo_Resposta_Horas'].mean():.1f}" if 'Tempo_Resposta_Horas' in df_filtered_final.columns and not df_filtered_final['Tempo_Resposta_Horas'].dropna().empty else "N/D",
                    "Concluídas (%)": f"{(df_filtered_final['Concluida?'].str.contains('sim', na=False).sum() / len(df_filtered_final) * 100):.1f}%" if 'Concluida?' in df_filtered_final.columns and len(df_filtered_final) > 0 else "0.0%",
                    "Municípios Atendidos": df_filtered_final['Municipio Solicitante'].nunique(),
                    "Estabelecimentos Visíveis": total_estabelecimentos_visiveis
                }
                
                if fig_perf: fig_perf.update_layout(margin=dict(l=60, r=60, t=60, b=180))
                if fig_ts: fig_ts.update_layout(margin=dict(l=60, r=60, t=60, b=180))
                if fig_pie: fig_pie.update_layout(margin=dict(l=20, r=60, t=60, b=180))
                if fig_cat: fig_cat.update_layout(margin=dict(l=60, r=60, t=60, b=180))
                if fig_sol: fig_sol.update_layout(margin=dict(l=60, r=60, t=60, b=180))
                fig_cat_pdf, fig_sol_pdf = fig_cat, fig_sol
                if 'Categoria Profissional' in df_filtered_final.columns and df_filtered_final['Categoria Profissional'].nunique() > 30:
                    cat_count_pdf = df_filtered_final['Categoria Profissional'].value_counts().reset_index().head(30)
                    fig_cat_pdf = px.bar(cat_count_pdf, x='Categoria Profissional', y='count', title='Top 30 Categorias', labels={'count':'Quantidade'}, color_discrete_sequence=['#198754'])
                if 'SolicitanteNome' in df_filtered_final.columns and df_filtered_final['SolicitanteNome'].nunique() > 30:
                    sol_count_pdf = df_filtered_final['SolicitanteNome'].value_counts().reset_index().head(30)
                    fig_sol_pdf = px.bar(sol_count_pdf, x='SolicitanteNome', y='count', title='Top 30 Solicitantes', labels={'count':'Quantidade'}, color_discrete_sequence=['#6f42c1'])

                figures_for_pdf = {
                    "Comparativo de Realizado vs. Meta": {'fig': fig_perf},
                    "Evolução Mensal": {'fig': fig_ts},
                    "Distribuição por Especialidade": {'fig': fig_pie, 'table': df_especialidade_tabela[['label', 'count']]},
                    "Distribuição por Categoria": {'fig': fig_cat_pdf},
                    "Distribuição por Solicitante": {'fig': fig_sol_pdf}
                }

                html_content = generate_html_for_pdf(start_date, end_date, kpis_for_pdf, df_tabela_perf, figures_for_pdf, df_especialidade_tabela)
                pdf_bytes = HTML(string=html_content).write_pdf()

                st.download_button(
                    label="📥 Download do Relatório PDF",
                    data=pdf_bytes,
                    file_name=f"Relatorio_Final_{datetime.now().strftime('%Y%m%d')}.pdf",
                    mime="application/pdf"
                )
        except Exception as e:
            st.error(f"Ocorreu um erro ao gerar o PDF com WeasyPrint. Verifique a instalação (GTK3 no Windows) e as bibliotecas. Erro: {e}")

st.markdown("---")
st.caption(f"Dashboard atualizado em {datetime.now().strftime('%d/%m/%Y às %H:%M:%S')}")