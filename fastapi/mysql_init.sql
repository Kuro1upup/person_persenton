-- MySQL建表脚本
-- 数据库名称: compare-slides

-- 创建presentations表
CREATE TABLE presentations (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(255) NULL,
    content LONGTEXT NOT NULL,
    n_slides INT NOT NULL,
    language VARCHAR(100) NOT NULL,
    title VARCHAR(255) NULL,
    file_paths JSON NULL,
    outlines JSON NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    layout JSON NULL,
    structure JSON NULL,
    instructions TEXT NULL,
    tone VARCHAR(100) NULL,
    verbosity VARCHAR(100) NULL,
    include_table_of_contents BOOLEAN NOT NULL DEFAULT FALSE,
    include_title_slide BOOLEAN NOT NULL DEFAULT TRUE,
    web_search BOOLEAN NOT NULL DEFAULT FALSE,
    outline_model JSON NULL,
    presentation_model JSON NULL,
    image_model JSON NULL,
    tavily_search_results_json JSON NULL,
    reference_markers JSON NULL,
    INDEX idx_presentations_user_id (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 创建slides表
CREATE TABLE slides (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(255) NULL,
    presentation VARCHAR(36) NOT NULL,
    layout_group VARCHAR(255) NOT NULL,
    layout VARCHAR(255) NOT NULL,
    `index` INT NOT NULL,
    content JSON NOT NULL,
    html_content TEXT NULL,
    speaker_note LONGTEXT NULL,
    properties JSON NULL,
    INDEX idx_slides_user_id (user_id),
    INDEX idx_slides_presentation (presentation),
    FOREIGN KEY (presentation) REFERENCES presentations(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 创建key_value表
CREATE TABLE key_value (
    id VARCHAR(36) PRIMARY KEY,
    `key` VARCHAR(255) NOT NULL,
    value JSON NOT NULL,
    INDEX idx_key_value_key (`key`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 创建image_assets表
CREATE TABLE image_assets (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(255) NULL,
    created_at DATETIME NOT NULL,
    is_uploaded BOOLEAN NOT NULL DEFAULT FALSE,
    path VARCHAR(255) NOT NULL,
    extras JSON NULL,
    INDEX idx_image_assets_user_id (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 创建presentation_layout_codes表
CREATE TABLE presentation_layout_codes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id VARCHAR(255) NULL,
    presentation VARCHAR(36) NOT NULL,
    layout_id VARCHAR(255) NOT NULL,
    layout_name VARCHAR(255) NOT NULL,
    layout_code TEXT NOT NULL,
    fonts JSON NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    INDEX idx_presentation_layout_codes_user_id (user_id),
    INDEX idx_presentation_layout_codes_presentation (presentation)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 创建templates表
CREATE TABLE templates (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(255) NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT NULL,
    created_at DATETIME NOT NULL,
    INDEX idx_templates_user_id (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 创建webhook_subscriptions表
CREATE TABLE webhook_subscriptions (
    id VARCHAR(255) PRIMARY KEY,
    user_id VARCHAR(255) NULL,
    created_at DATETIME NOT NULL,
    url TEXT NOT NULL,
    secret TEXT NULL,
    event VARCHAR(255) NOT NULL,
    INDEX idx_webhook_subscriptions_user_id (user_id),
    INDEX idx_webhook_subscriptions_event (event)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 创建async_presentation_generation_tasks表
CREATE TABLE async_presentation_generation_tasks (
    id VARCHAR(255) PRIMARY KEY,
    user_id VARCHAR(255) NULL,
    status VARCHAR(100) NOT NULL,
    message TEXT NULL,
    error JSON NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    data JSON NULL,
    INDEX idx_async_tasks_user_id (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 创建ollama_pull_status表
CREATE TABLE ollama_pull_status (
    id VARCHAR(255) PRIMARY KEY,
    last_updated DATETIME NOT NULL,
    status JSON NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

ALTER TABLE presentation_layout_codes
MODIFY COLUMN id INT AUTO_INCREMENT PRIMARY KEY;