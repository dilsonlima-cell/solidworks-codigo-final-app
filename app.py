import streamlit as st
import pandas as pd
import json
import os
from collections import defaultdict

# Nome do arquivo de contador persistente
CONTADOR_FILE = "contador.json"

# Carregar ou criar o contador de códigos por grupo
def load_contador():
    if os.path.exists(CONTADOR_FILE):
        with open(CONTADOR_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    else:
        return defaultdict(int)

# Salvar o contador atualizado
def save_contador(contador):
    with open(CONTADOR_FILE, 'w', encoding='utf-8') as f:
        json.dump(dict(contador), f, indent=2, ensure_ascii=False)

# Função para extrair os 3 dígitos do grupo (ex: "100 - Mecânico" → "100")
def extrair_codigo_grupo(grupo_str):
    if not isinstance(grupo_str, str) or not grupo_str.strip():
        return None
    partes = grupo_str.split(' - ')
    cod = partes[0].strip()
    if len(cod) == 3 and cod.isdigit():
        return cod
    return None

# Função para validar se o código já é válido (formatos aceitos)
def eh_codigo_valido(codigo):
    if not codigo or pd.isna(codigo):
        return False
    codigo = str(codigo).strip()
    # Formato YY-NNNN-XXXX-RR (ex: 10-3608-0100-00)
    if len(codigo) == 14 and codigo.count('-') == 3:
        parts = codigo.split('-')
        if len(parts) == 4 and all(p.isdigit() for p in parts) and len(parts[0]) == 2 and len(parts[1]) == 4 and len(parts[2]) == 4 and len(parts[3]) == 2:
            return True
    # Formato XXX-NNNN (ex: 100-0001)
    if len(codigo) == 8 and codigo.count('-') == 1:
        parts = codigo.split('-')
        if len(parts) == 2 and len(parts[0]) == 3 and len(parts[1]) == 4 and parts[0].isdigit() and parts[1].isdigit():
            return True
    return False

# Título do app
st.title("🔧 Gerador de Código Final - SolidWorks → ERP")
st.write("Faça upload do arquivo exportado do SolidWorks (formato TXT)")

# Upload do arquivo
uploaded_file = st.file_uploader("Escolha seu arquivo .txt", type=["txt"])

if uploaded_file:
    try:
        # Ler todo o conteúdo do arquivo como texto
        content = uploaded_file.getvalue().decode('utf-8').splitlines()

        # Lista de possíveis nomes de colunas que indicam o cabeçalho
        header_keywords = [
            'Nº DO ITEM', 'Nº DA PEÇA', 'TÍTULO', 'MATERIAL', 
            'GRUPO DE PRODUTO', 'PROCESSO', 'REVEST.', 'PESO', 
            'AREA TOTAL', 'REFERENCIA', 'QTD.'
        ]

        # Procurar a linha que contém TODOS os termos principais do cabeçalho
        header_line_index = -1
        header_row = None

        for i, line in enumerate(content):
            if not line.strip():  # Pular linhas vazias
                continue
            # Dividir por tabulação
            cells = [cell.strip() for cell in line.split('\t')]
            # Verificar quantas palavras-chave estão presentes
            found_keywords = sum(1 for kw in header_keywords if kw in cells)
            # Se encontrou pelo menos 7 das 11 palavras-chave, considera como cabeçalho
            if found_keywords >= 7:
                header_line_index = i
                header_row = cells
                break

        # Caso não encontre com a lógica acima, tentar usar a última linha não vazia como cabeçalho
        if header_line_index == -1:
            for i in range(len(content)-1, -1, -1):
                line = content[i].strip()
                if line:
                    header_row = [cell.strip() for cell in line.split('\t')]
                    header_line_index = i
                    break

        # Se ainda não encontrou, erro
        if header_line_index == -1 or not header_row:
            st.error("❌ Não foi possível identificar o cabeçalho do arquivo. Certifique-se de que ele contém colunas como: 'Nº DO ITEM', 'Nº DA PEÇA', 'GRUPO DE PRODUTO', etc.")
            st.stop()

        # Pegar os dados (todas as linhas abaixo do cabeçalho)
        data_lines = content[header_line_index + 1:]

        # Criar DataFrame com os dados
        data = []
        for line in data_lines:
            if line.strip():  # Ignorar linhas vazias
                cells = [cell.strip() for cell in line.split('\t')]
                # Garantir que tenha o mesmo número de colunas que o cabeçalho
                while len(cells) < len(header_row):
                    cells.append('')
                data.append(cells[:len(header_row)])

        df = pd.DataFrame(data, columns=header_row)

        # Renomear colunas para nomes mais simples (ajustados ao seu arquivo)
        df = df.rename(columns={
            'Nº DO ITEM': 'Item',
            'Nº DA PEÇA': 'Codigo_Produto',
            'TÍTULO': 'Descricao',
            'MATERIAL': 'Material',
            'GRUPO DE PRODUTO': 'Grupo',
            'QTD.': 'Quantidade'
        })

        # Inicializar contador
        contador = load_contador()

        # Criar nova coluna "Código Final"
        codigos_finais = []

        for idx, row in df.iterrows():
            codigo_produto = row['Codigo_Produto'] if pd.notna(row['Codigo_Produto']) else ""

            if eh_codigo_valido(codigo_produto):
                codigos_finais.append(codigo_produto)
            else:
                grupo = row['Grupo'] if pd.notna(row['Grupo']) else ""
                cod_grupo = extrair_codigo_grupo(grupo)

                if cod_grupo:
                    contador[cod_grupo] += 1
                    novo_codigo = f"{cod_grupo}-{contador[cod_grupo]:04d}"
                    codigos_finais.append(novo_codigo)
                else:
                    codigos_finais.append("")  # Deixar vazio se não houver grupo válido

        df['Código Final'] = codigos_finais

        # Selecionar e renomear colunas finais (exatamente como pediu)
        df_final = df[['Código Final', 'Codigo_Produto', 'Descricao', 'Grupo', 'Material', 'Quantidade']].copy()
        df_final.columns = ['Código Final', 'Código do produto', 'Descrição', 'Grupo', 'Material', 'Quantidade']

        # Mostrar tabela processada
        st.subheader("✅ Resultado Processado")
        st.dataframe(df_final, use_container_width=True)

        # Botão para download do CSV (UTF-8-SIG para Excel abrir bem)
        csv = df_final.to_csv(index=False, sep=';', encoding='utf-8-sig')
        st.download_button(
            label="📥 Baixar CSV para ERP",
            data=csv,
            file_name="codigo_final_erp.csv",
            mime="text/csv"
        )

        # Salvar contador atualizado
        save_contador(contador)
        st.success("✅ Contador salvo em `contador.json`. Pronto para próxima execução!")

    except Exception as e:
        st.error(f"❌ Erro ao processar o arquivo: {str(e)}")

else:
    st.info("📁 Por favor, faça upload do seu arquivo .txt exportado do SolidWorks.")
