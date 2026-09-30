# Case Técnico Dadosfera

Repositório do case técnico de Engenharia de Dados. Os dados gerados são sintéticos e destinados a demonstrar ingestão, qualidade, modelagem e consumo analítico.

## Governança do projeto

O planejamento segue conceitos do PMBOK. A WBS (Work Breakdown Structure) decompõe o escopo em entregas verificáveis, da preparação dos dados à apresentação executiva. A gestão de riscos identifica eventos que podem afetar prazo, qualidade ou acesso e define respostas antes da execução. O caminho crítico é a sequência de atividades dependentes que determina a duração mínima do projeto; atrasos nessa sequência afetam a data final.

### Matriz de riscos

| Risco | Categoria | Impacto | Probabilidade | Mitigação |
|---|---|---|---|---|
| Acesso à plataforma ou permissões indisponíveis | Operacional | Alto | Média | Solicitar acessos no início e manter instruções reproduzíveis para execução manual. |
| Dados sintéticos não representarem os casos esperados | Dados | Médio | Média | Validar distribuições, chaves, nulos e cenários de status antes da ingestão. |
| Datas inválidas ou inconsistentes na ingestão | Qualidade | Alto | Média | Padronizar timestamps na origem e validar tipos e intervalos após a carga. |
| Extração de atributos por LLM produzir conteúdo incorreto | Tecnologia | Alto | Média | Validar saídas com regras, amostras revisadas e rastreabilidade do prompt/modelo. |
| Atraso em tarefas dependentes do caminho crítico | Prazo | Alto | Média | Acompanhar marcos, dependências e bloqueios; priorizar atividades críticas. |

### Cronograma

```mermaid
gantt
title Planejamento e Execução do Case Técnico Dadosfera
dateFormat YYYY-MM-DD
section Fase 1: Planejamento
Agilidade e Escopo (Item 0) :a1, 2026-09-01, 2d
Seleção da Base de Dados (Item 1) :a2, after a1, 1d
section Fase 2: Ingestão & Qualidade
Ingestão no Módulo Integrar (Item 2.1) :b1, after a2, 2d
Catalogação e Zonas Medallion (Item 3) :b2, after b1, 2d
Data Quality com Great Expectations (Item 4) :b3, after b2, 2d
section Fase 3: IA & Modelagem
Extração de Features com LLM (Item 5) :c1, after b3, 3d
Modelagem Dimensional Kimball (Item 6) :c2, after c1, 2d
section Fase 4: Entrega de Valor
Dashboards e Análises Metabase (Item 7) :d1, after c2, 2d
Pipelines e Stepsfera (Item 8) :d2, after d1, 2d
Data App Streamlit (Item 9) :d3, after d2, 2d
section Fase 5: Defesa
Apresentação Executiva e Pitch (Item 10) :e1, after d3, 2d
```

## Geração dos dados

O notebook [01_data_generation_and_prep.ipynb](notebooks/01_data_generation_and_prep.ipynb) gera três CSVs sintéticos em `data/bronze/`: 100.000 pedidos, 200.000 itens e 5.000 produtos. Os arquivos gerados são locais e ficam fora do controle de versão. Instale as dependências com `pip install -r src/requirements.txt` antes de executar o notebook.

## Ingestão Bronze

No Módulo Integrar da Dadosfera, crie uma conexão para arquivos CSV e carregue `tb_orders.csv`, `tb_order_items.csv` e `tb_products_unstructured.csv`. A consulta de microtransformação solicitada para pedidos está em [clean_orders.sql](pipelines/sql_transformations/clean_orders.sql). Após configurar a conexão e permissões na plataforma, execute a carga e valide o volume e os tipos das colunas.