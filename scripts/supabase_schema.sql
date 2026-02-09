-- ============================================================
-- 📦 SQL Schema para Supabase - DataHub App
-- Execute este script no SQL Editor do Supabase
-- ============================================================

-- ============================================================
-- 🔹 TABELA: usuarios
-- Usuários do sistema com preferências de tema
-- ============================================================
CREATE TABLE IF NOT EXISTS tab_app_usuarios (
    id SERIAL PRIMARY KEY,
    nm_usuario VARCHAR(255) NOT NULL UNIQUE,
    nm_usuario_label VARCHAR(255),
    tp_tema VARCHAR(20) DEFAULT 'light',
    email VARCHAR(255),
    sn_ativo BOOLEAN DEFAULT TRUE,
    dt_criacao TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    dt_atualizacao TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Índice para busca por usuário
CREATE INDEX IF NOT EXISTS idx_usuarios_nm_usuario ON tab_app_usuarios(nm_usuario);

-- ============================================================
-- 🔹 TABELA: menu_app
-- Páginas dinâmicas do menu (permissões por usuário)
-- ============================================================
CREATE TABLE IF NOT EXISTS tab_app_menu_app (
    id SERIAL PRIMARY KEY,
    nm_pagina VARCHAR(255) NOT NULL,
    ds_label VARCHAR(255),
    ds_icone VARCHAR(50) DEFAULT '📁',
    ds_modulo VARCHAR(255) NOT NULL,
    nm_funcao VARCHAR(255) NOT NULL,
    nr_ordem INTEGER DEFAULT 0,
    sn_ativo BOOLEAN DEFAULT TRUE,
    nm_usuario VARCHAR(255) NOT NULL,
    dt_criacao TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Índices para busca
CREATE INDEX IF NOT EXISTS idx_menu_app_usuario ON tab_app_menu_app(nm_usuario);
CREATE INDEX IF NOT EXISTS idx_menu_app_ativo ON tab_app_menu_app(sn_ativo);

-- -- ============================================================
-- -- 🔹 TABELA: auditoria_eventos
-- -- Log de auditoria de todas as operações
-- -- ============================================================
-- CREATE TABLE IF NOT EXISTS auditoria_eventos (
--     id SERIAL PRIMARY KEY,
--     dt_evento TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
--     tp_evento VARCHAR(50) NOT NULL,
--     nm_tela VARCHAR(255),
--     nm_usuario VARCHAR(255),
--     nm_tabela_afetada VARCHAR(255),
--     nm_arquivo VARCHAR(255),
--     ds_acao TEXT,
--     ds_parametros JSONB,
--     ds_dados_antigos JSONB,
--     ds_dados_novos JSONB,
--     ds_status VARCHAR(50) DEFAULT 'SUCESSO',
--     ds_mensagem TEXT,
--     nm_origem VARCHAR(50) DEFAULT 'STREAMLIT',
--     id_referencia VARCHAR(255)
-- );

-- -- Índices para consultas de auditoria
-- CREATE INDEX IF NOT EXISTS idx_auditoria_dt_evento ON auditoria_eventos(dt_evento);
-- CREATE INDEX IF NOT EXISTS idx_auditoria_usuario ON auditoria_eventos(nm_usuario);
-- CREATE INDEX IF NOT EXISTS idx_auditoria_tabela ON auditoria_eventos(nm_tabela_afetada);


-- ============================================================
-- 🔹 TABELA: grupos
-- Grupos de acesso
-- ============================================================
CREATE TABLE IF NOT EXISTS tab_app_grupos (
    id SERIAL PRIMARY KEY,
    nm_grupo VARCHAR(255) NOT NULL UNIQUE,
    ds_grupo TEXT,
    sn_ativo BOOLEAN DEFAULT TRUE,
    dt_criacao TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================================
-- 🔹 TABELA: paginas
-- Páginas do sistema
-- ============================================================
CREATE TABLE IF NOT EXISTS tab_app_paginas (
    id SERIAL PRIMARY KEY,
    nm_pagina VARCHAR(255) NOT NULL UNIQUE,
    ds_pagina TEXT,
    ds_rota VARCHAR(255),
    sn_ativo BOOLEAN DEFAULT TRUE,
    dt_criacao TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================================
-- 🔹 TABELA: usuario_grupo
-- Relação N:N entre usuários e grupos
-- ============================================================
CREATE TABLE IF NOT EXISTS tab_app_usuario_grupo (
    id SERIAL PRIMARY KEY,
    id_usuario INTEGER REFERENCES tab_app_usuarios(id),
    id_grupo INTEGER REFERENCES tab_app_grupos(id),
    sn_ativo BOOLEAN DEFAULT TRUE,
    dt_criacao TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(id_usuario, id_grupo)
);

-- ============================================================
-- 🔹 TABELA: grupo_pagina
-- Relação N:N entre grupos e páginas
-- ============================================================
CREATE TABLE IF NOT EXISTS tab_app_grupo_pagina (
    id SERIAL PRIMARY KEY,
    id_grupo INTEGER REFERENCES tab_app_grupos(id),
    id_pagina INTEGER REFERENCES tab_app_paginas(id),
    sn_ativo BOOLEAN DEFAULT TRUE,
    dt_criacao TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(id_grupo, id_pagina)
);

-- ============================================================
-- 🔹 TABELA: clientes
-- Clientes cadastrados
-- ============================================================
CREATE TABLE IF NOT EXISTS tab_app_clientes (
    id SERIAL PRIMARY KEY,
    nm_cliente VARCHAR(255) NOT NULL,
    ds_cliente TEXT,
    sn_ativo BOOLEAN DEFAULT TRUE,
    dt_criacao TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================================
-- 🔹 TABELA: dashboards
-- Dashboards Power BI
-- ============================================================
CREATE TABLE IF NOT EXISTS tab_app_dashboards (
    id SERIAL PRIMARY KEY,
    nm_dashboard VARCHAR(255) NOT NULL,
    ds_dashboard TEXT,
    url_embed TEXT,
    id_cliente INTEGER REFERENCES tab_app_clientes(id),
    sn_ativo BOOLEAN DEFAULT TRUE,
    dt_criacao TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================================
-- 📦 Tabela de Variáveis (Dimensões)
-- ============================================================
CREATE TABLE tab_app_variaveis (
  id_variavel BIGSERIAL PRIMARY KEY,
  grupo_destino VARCHAR(255) NOT NULL,
  uso VARCHAR(255) NOT NULL UNIQUE,
  valor TEXT NOT NULL,
  dt_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  dt_atualizacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- 📚 Tabela de Estudos (com FK para Variáveis)
-- ============================================================
CREATE TABLE tab_app_estudos (
  id_estudo BIGSERIAL PRIMARY KEY,
  estudo VARCHAR(255) NOT NULL UNIQUE,
  cod_estudo VARCHAR(255),
  centro VARCHAR(255),  -- Virá de tab_app_variaveis (uso='centro')
  id_centro BIGINT,
  disciplina VARCHAR(255),  -- Virá de tab_app_variaveis (uso='disciplina')
  coordenacao VARCHAR(255),  -- Virá de tab_app_variaveis (uso='coordenacao')
  coordenador VARCHAR(255),
  pi VARCHAR(255),
  patrocinador VARCHAR(255),  -- Virá de tab_app_variaveis (uso='patrocinador')
  entrada_dados_modelo VARCHAR(255),  -- Virá de tab_app_variaveis (uso='entrada_dados_modelo')
  entrada_dados_dias VARCHAR(255),
  resolucao_modelo VARCHAR(255),  -- Virá de tab_app_variaveis (uso='resolucao_modelo')
  resolucao_dias VARCHAR(255),
  sn_ativo BOOLEAN DEFAULT TRUE,
  dt_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  dt_atualizacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Índices para melhorar performance
CREATE INDEX idx_estudos_ativo ON tab_app_estudos(sn_ativo);
CREATE INDEX idx_variaveis_uso ON tab_app_variaveis(uso);


-- ============================================================
-- 📋 DADOS INICIAIS (opcional - para testes)
-- ============================================================

-- Usuário de teste
-- Usuário padrão (senha: admin123)
-- Hash de "admin123": 240be518fabd2724ddb6f04eeb1da5967448d7e831c08c8fa822809f74c720a9
INSERT INTO tab_app_usuarios (nm_usuario, nm_usuario_label, ds_email, ds_senha, sn_ativo)
VALUES (
  'admin', 
  'Administrador', 
  'admin@datahub.local', 
  '240be518fabd2724ddb6f04eeb1da5967448d7e831c08c8fa822809f74c720a9',  -- ✅ Hash correto
  TRUE
);

-- Menu inicial para admin
INSERT INTO tab_app_menu_app (nm_pagina, ds_label, ds_icone, ds_modulo, nm_funcao, nr_ordem, nm_usuario, sn_ativo)
VALUES 
    ('Home', 'Início', '🏠', 'home', 'page_home', 1, 'admin', TRUE),
    ('Pipelines', 'Pipelines', '🔧', 'pipelines', 'page_pipelines', 2, 'admin', TRUE),
    ('Settings', 'Configurações', '⚙️', 'settings', 'page_settings', 10, 'admin', TRUE)
ON CONFLICT DO NOTHING;

-- Dados iniciais da tab_variaveis
INSERT INTO tab_app_variaveis (grupo_destino, uso, valor) VALUES
('Campos Estudo', 'centro', 'CEMEC\nCPAM'),
('Campos Estudo', 'disciplina', 'Cardiologia\nEndocrinologia\nNeurologia\nOncologia'),
('Campos Estudo', 'coordenacao', 'Coordenacao 1\nCoordenacao 2\nCoordenacao 3'),
('Campos Estudo', 'patrocinador', 'N/A'),
('Campos Estudo', 'entrada_dados_modelo', 'Corridos\nÚteis'),
('Campos Estudo', 'resolucao_modelo', 'Corridos\nÚteis')
ON CONFLICT (uso) DO NOTHING;

-- ============================================================
-- ✅ FIM DO SCRIPT
-- ============================================================
