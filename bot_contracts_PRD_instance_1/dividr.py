import pandas as pd

# Carregar sua base de dados (agora usando read_excel para arquivos .xlsx)
df = pd.read_excel(r'D:\Meus Documentos\Documentos\Contratos - Extração\bot_contracts_PRD_instance_3\input\Base Pós GO LIVE.xlsx')

# Verificar se há Contract_ID único
if 'Contract_ID' not in df.columns:
    raise ValueError("A coluna 'Contract_ID' não foi encontrada no DataFrame")

# Dividir os Contract_ID em 3 grupos
unique_ids = df['Contract_ID'].unique()
n = len(unique_ids)
part_size = n // 3

# Criar 3 DataFrames separados
df1_ids = unique_ids[:part_size]
df2_ids = unique_ids[part_size:2*part_size]
df3_ids = unique_ids[2*part_size:]

df1 = df[df['Contract_ID'].isin(df1_ids)]
df2 = df[df['Contract_ID'].isin(df2_ids)]
df3 = df[df['Contract_ID'].isin(df3_ids)]

# Salvar os resultados (agora usando to_excel para manter formato .xlsx)
df1.to_excel('parte_1.xlsx', index=False)
df2.to_excel('parte_2.xlsx', index=False)
df3.to_excel('parte_3.xlsx', index=False)

print(f"Base dividida em 3 partes com aproximadamente {len(df1)} registros cada.")