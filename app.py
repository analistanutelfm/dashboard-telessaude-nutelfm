# --- 1. IMPORTAÇÃO DAS BIBLIOTECAS ---
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import io
from datetime import datetime
import os
import locale
from fpdf import FPDF
import matplotlib
matplotlib.use('Agg') # Usa um backend não interativo, essencial para servidores
import matplotlib.pyplot as plt

# Definir locale para formatação de números em português
try:
    locale.setlocale(locale.LC_ALL, 'pt_BR.UTF-8')
except locale.Error:
    st.warning("Locale 'pt_BR.UTF-8' não encontrado.")
    locale.setlocale(locale.LC_ALL, '')


# --- 2. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(layout="wide", page_title="Dashboard de Teleconsultorias")
st.title("Dashboard de Gestão e Análise de Teleconsultorias")

# --- 3. FUNÇÕES AUXILIARES E CLASSE PDF ---

class PDFReport(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 15)
        self.cell(0, 10, 'Relatório de Análise de Teleconsultorias', 0, 1, 'C')
        self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        hoje = datetime.now().strftime('%d/%m/%Y às %H:%M:%S')
        self.cell(0, 10, f'Página {self.page_no()} | Gerado em: {hoje}', 0, 0, 'C')

    def chapter_title(self, title):
        self.set_font('Arial', 'B', 12)
        self.cell(0, 10, title, 0, 1, 'L')
        self.ln(4)

    def write_pandas_table(self, df_table, col_widths):
        self.set_fill_color(224, 235, 255) # Cor de fundo azul claro para o cabeçalho
        self.set_font('Arial', 'B', 8)
        for i, header in enumerate(df_table.columns):
            self.cell(col_widths[i], 7, str(header), 1, 0, 'C', 1)
        self.ln()
        self.set_font('Arial', '', 7)
        for index, row in df_table.iterrows():
            if self.get_y() > 270: # Adiciona nova página se a tabela for muito longa
                self.add_page()
            for i, item in enumerate(row):
                self.cell(col_widths[i], 6, str(item), 1)
            self.ln()
        self.ln(8)

def fig_to_bytes(fig):
    """Converte uma figura Matplotlib para bytes em memória."""
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=150, bbox_inches='tight')
    plt.close(fig)
    buf.seek(0)
    return buf

# ### NOVAS FUNÇÕES PARA GERAR GRÁFICOS ESTÁTICOS PARA O PDF ###
def gerar_grafico_performance_matplotlib(df_perf):
    fig, ax = plt.subplots(figsize=(10, 7)) # Aumenta a altura para mais espaço
    bar_width = 0.4
    index = range(len(df_perf))
    
    ax.bar(index, df_perf['Realizado_Periodo'], bar_width, label='Realizado no Período', color='#0d6efd')
    ax.bar([i + bar_width for i in index], df_perf['CotaMensal_Estabelecimento'], bar_width, label='Cota Mensal', color='#adb5bd')
    
    ax.set_ylabel('Quantidade')
    ax.set_title('Comparativo de Realizado vs. Meta por Estabelecimento')
    ax.set_xticks([i + bar_width / 2 for i in index])
    ax.set_xticklabels(df_perf['Estabelecimento'], rotation=90, ha="right")
    ax.legend()
    ax.grid(axis='y', linestyle='--', alpha=0.7)
    fig.tight_layout() # Ajuste automático de layout
    return fig_to_bytes(fig)

def gerar_grafico_evolucao_matplotlib(df_ts):
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(df_ts['Mês'], df_ts['Quantidade'], marker='o', linestyle='-', color='#fd7e14')
    for i, txt in enumerate(df_ts['Quantidade']):
        ax.annotate(txt, (df_ts['Mês'][i], df_ts['Quantidade'][i]), textcoords="offset points", xytext=(0,5), ha='center')
    ax.set_ylabel('Quantidade')
    ax.set_title('Evolução Mensal das Teleconsultorias')
    plt.xticks(rotation=45, ha="right")
    ax.grid(True, linestyle='--', alpha=0.6)
    fig.tight_layout()
    return fig_to_bytes(fig)

def gerar_grafico_pizza_matplotlib(df_pie):
    fig, ax = plt.subplots(figsize=(10, 7))
    wedges, texts, autotexts = ax.pie(df_pie['count'], autopct='%1.1f%%', startangle=90, colors=plt.cm.Pastel1.colors)
    ax.axis('equal')
    ax.legend(wedges, df_pie['label'], title="Especialidades", loc="center left", bbox_to_anchor=(1, 0, 0.5, 1))
    ax.set_title('Distribuição por Especialidade e Média de Resposta (h)')
    return fig_to_bytes(fig)

def gerar_grafico_barras_matplotlib(df_data, col_x, col_y, title, color):
    fig, ax = plt.subplots(figsize=(10, 7))
    ax.bar(df_data[col_x], df_data[col_y], color=color)
    ax.set_ylabel('Quantidade')
    ax.set_title(title)
    plt.xticks(rotation=90, ha="right")
    ax.grid(axis='y', linestyle='--', alpha=0.7)
    fig.tight_layout()
    return fig_to_bytes(fig)

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
def format_number(n):
    if pd.isna(n): return 'N/D'
    try: return locale.format_string("%d", int(n), grouping=True)
    except (ValueError, TypeError): return n

# --- 4. CARREGAMENTO E PREPARAÇÃO DOS DADOS ---
df_condicoes_raw = load_local_data('condicoes.xlsx')
df_estabelecimentos_raw = load_local_data('estabelecimentos.xlsx')
df_categoria_raw = load_local_data('categoria.xlsx')
uploaded_file = st.file_uploader("Faça upload do arquivo Excel principal de teleconsultorias (xls/xlsx):", type=["xls", "xlsx"])
if uploaded_file is None or df_condicoes_raw is None or df_estabelecimentos_raw is None or df_categoria_raw is None:
    st.warning("Por favor, faça o upload do arquivo principal e verifique se os arquivos de apoio estão na mesma pasta.")
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

# ### SEÇÃO DE EXPORTAÇÃO DE PDF COM MATPLOTLIB ###
st.markdown("---")
st.header("Exportar Relatório em PDF")

if st.button("Gerar Relatório PDF"):
    if df_filtered_final.empty:
        st.warning("Não há dados filtrados para gerar o relatório PDF.")
    else:
        try:
            with st.spinner("Gerando seu relatório PDF, por favor aguarde..."):
                pdf = PDFReport()
                pdf.add_page()
                pdf.chapter_title(f"Relatório do Período: {start_date.strftime('%d/%m/%Y')} a {end_date.strftime('%d/%m/%Y')}")

                if not df_tabela_perf.empty:
                    pdf.chapter_title("Tabela de Performance por Estabelecimento")
                    df_tabela_perf_pdf = df_tabela_perf.copy()
                    df_tabela_perf_pdf.index.name = '#'
                    df_tabela_perf_pdf.reset_index(inplace=True)
                    df_tabela_perf_pdf['Percentual Atingido'] = df_tabela_perf_pdf['Percentual Atingido'].apply(lambda x: f"{x:.1f}%")
                    df_tabela_perf_pdf.rename(columns={'index': '#', 'Municipio Solicitante': 'Município', 'CotaMensal_Estabelecimento': 'Cota Mensal', 'Realizado_Periodo': 'Realizado', 'Percentual Atingido': '% Atingido'}, inplace=True)
                    cols_pdf = ['#', 'Município', 'Estabelecimento', 'Cota Mensal', 'Realizado', '% Atingido']
                    col_widths_pdf = [8, 32, 70, 20, 20, 25] 
                    pdf.write_pandas_table(df_tabela_perf_pdf[cols_pdf].head(35), col_widths=col_widths_pdf)

                if fig_perf is not None:
                    if pdf.get_y() > 180: pdf.add_page() # Adiciona nova página se não houver espaço
                    pdf.chapter_title("Comparativo de Realizado vs. Meta por Estabelecimento")
                    img_bytes = gerar_grafico_performance_matplotlib(df_performance_estab_filtrado)
                    pdf.image(img_bytes, w=190)

                if fig_ts is not None:
                    if pdf.get_y() > 180: pdf.add_page()
                    pdf.chapter_title("Evolução Mensal das Teleconsultorias")
                    img_bytes = gerar_grafico_evolucao_matplotlib(df_ts)
                    pdf.image(img_bytes, w=190)
                
                if fig_pie is not None:
                    if pdf.get_y() > 180: pdf.add_page()
                    pdf.chapter_title("Distribuição por Especialidade")
                    img_bytes = gerar_grafico_pizza_matplotlib(df_pie_data)
                    pdf.image(img_bytes, w=180)
                    pdf.ln(5)
                    # Adiciona a tabela de especialidade ao PDF
                    df_especialidade_tabela_pdf = df_especialidade_tabela.copy()
                    df_especialidade_tabela_pdf.index.name = '#'
                    df_especialidade_tabela_pdf.reset_index(inplace=True)
                    df_especialidade_tabela_pdf.rename(columns={'index': '#', 'label': 'Especialidade (Média Resp. h)', 'count': 'Qtde'}, inplace=True)
                    pdf.write_pandas_table(df_especialidade_tabela_pdf, col_widths=[10, 100, 20])

                if fig_cat is not None:
                    pdf.add_page()
                    pdf.chapter_title("Distribuição por Categoria Profissional")
                    cat_count = df_filtered_final['Categoria Profissional'].value_counts().reset_index().head(30)
                    img_bytes = gerar_grafico_barras_matplotlib(cat_count, 'Categoria Profissional', 'count', '', '#198754')
                    pdf.image(img_bytes, w=190)

                if fig_sol is not None:
                    pdf.add_page()
                    pdf.chapter_title("Distribuição por Solicitante")
                    solicitante_count = df_filtered_final['SolicitanteNome'].value_counts().reset_index().head(30)
                    img_bytes = gerar_grafico_barras_matplotlib(solicitante_count, 'SolicitanteNome', 'count', '', '#6f42c1')
                    pdf.image(img_bytes, w=190)

                pdf_bytes = pdf.output(dest='S').encode('latin-1')
                
                st.download_button(
                    label="📥 Download do Relatório PDF Final",
                    data=pdf_bytes,
                    file_name=f"Relatorio_Final_{datetime.now().strftime('%Y%m%d')}.pdf",
                    mime="application/pdf"
                )

        except Exception as e:
            st.error(f"Ocorreu um erro ao gerar o PDF. Verifique se a biblioteca 'matplotlib' está instalada. Erro: {e}")

st.markdown("---")
st.caption(f"Dashboard atualizado em {datetime.now().strftime('%d/%m/%Y às %H:%M:%S')}")